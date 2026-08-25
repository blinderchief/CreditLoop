"""FastAPI surface for the dashboard.

The UI stays dead simple; everything below is managed here in the backend. Read
endpoints serve the append-only ledger; a couple of action endpoints re-run the
loop and demonstrate the failure modes and the Dynamic Compliance Engine.
"""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlmodel import select

from . import queries
from .config import settings
from .db import get_session, init_db
from .log import log
from .models import Claim

app = FastAPI(title="CreditLoop API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # local demo
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()
    with get_session() as s:
        has_data = s.exec(select(Claim).limit(1)).first() is not None
    if not has_data:
        log.info("[loop.step]No data yet — running the full loop once to populate…[/]")
        from .demo import run_full
        run_full(regenerate=True)


# --- read endpoints -------------------------------------------------------

@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "creditloop", "version": app.version}


@app.get("/api/summary")
def summary() -> dict:
    return queries.get_summary()


@app.get("/api/claims")
def claims(status: Optional[str] = None, tier: Optional[int] = None,
           decision: Optional[str] = None, q: Optional[str] = None,
           limit: int = Query(500, le=1000)) -> list[dict]:
    return queries.list_claims(status=status, tier=tier, decision=decision, q=q, limit=limit)


@app.get("/api/claims/{claim_id}")
def claim_detail(claim_id: str) -> dict:
    d = queries.get_claim_detail(claim_id)
    if d is None:
        raise HTTPException(404, "claim not found")
    return d


@app.get("/api/exceptions")
def exceptions() -> list[dict]:
    return queries.list_exceptions()


@app.get("/api/vendors")
def vendors() -> list[dict]:
    return queries.list_vendors()


@app.get("/api/metrics")
def metrics() -> dict:
    return queries.get_metrics()


@app.get("/api/audit")
def audit(limit: int = Query(200, le=1000)) -> list[dict]:
    return queries.list_audit(limit=limit)


@app.get("/api/rules")
def rules() -> list[dict]:
    from . import rule_registry
    return [r.model_dump() for r in rule_registry.registry.rules]


@app.get("/api/status")
def status() -> dict:
    """Which integrations are live vs mock — surfaced in the UI honestly."""
    from .llm import llm_status
    return {
        "llm": llm_status(),
        "gsp": {"mode": settings.gsp_mode},
        "razorpay": {"mode": "test" if settings.razorpay_live else "mock",
                     "live": settings.razorpay_live},
    }


@app.get("/api/claims/{claim_id}/draft")
def draft(claim_id: str) -> dict:
    """P1.1 — draft a vendor reissue / filing request for this claim."""
    from sqlmodel import select as _select
    from .drafting import draft_request
    from .models import Invoice, Verdict
    with get_session() as s:
        claim = s.get(Claim, claim_id)
        if not claim:
            raise HTTPException(404, "claim not found")
        inv = s.exec(_select(Invoice).where(Invoice.claim_id == claim_id)).first()
        v = s.exec(_select(Verdict).where(Verdict.claim_id == claim_id)
                   .order_by(Verdict.created_at.desc())).first()
    d = draft_request(claim, inv, v)
    return {"kind": d.kind, "subject": d.subject, "english": d.english,
            "hinglish": d.hinglish, "source": d.source}


# --- Dynamic Compliance Engine (P1.2 / P1.3) -----------------------------

@app.get("/api/compliance/proposals")
def compliance_proposals() -> list[dict]:
    from .compliance import list_proposals
    return list_proposals()


@app.post("/api/compliance/detect")
def compliance_detect() -> dict:
    from .compliance import detect_changes, list_proposals
    detect_changes()
    return {"proposals": list_proposals()}


@app.post("/api/compliance/proposals/{proposal_id}/approve")
def compliance_approve(proposal_id: str) -> dict:
    from .compliance import approve_proposal
    return approve_proposal(proposal_id)


@app.post("/api/compliance/proposals/{proposal_id}/reject")
def compliance_reject(proposal_id: str) -> dict:
    from .compliance import reject_proposal
    return reject_proposal(proposal_id)


@app.post("/api/eval/extraction")
def eval_extraction(sample: int = 0) -> dict:
    """Run the real VLM on a sample of receipts and score per-field accuracy."""
    from .extract_eval import run_extraction_eval
    return run_extraction_eval(sample=sample or None)


# --- action endpoints -----------------------------------------------------

class RunRequest(BaseModel):
    fail_payout: bool = False
    gsp_down: bool = False
    regenerate: bool = True


@app.post("/api/run")
def run(req: RunRequest) -> dict:
    """Re-run the whole loop, optionally injecting a failure. Resets the law to
    baseline first so runs are reproducible."""
    from . import engine, rule_registry
    from .demo import run_full
    rule_registry.reset_registry()
    engine.reset_blocked()
    return run_full(fail_payout=req.fail_payout, gsp_down=req.gsp_down, regenerate=req.regenerate)


class BumpRequest(BaseModel):
    rule_id: str = "SEC_17_5_B_FOOD_BEVERAGE"
    block_category: Optional[str] = None   # add a category to a 17(5) block
    note: str = "CA-approved rule change"


@app.post("/api/rules/reevaluate")
def reevaluate(req: BumpRequest) -> dict:
    """The Dynamic Compliance Engine demo: bump a rule to a new version, then
    re-run judgment over history and report exactly which verdicts changed.
    Verdicts are append-only, so the old ones remain for audit."""
    from . import engine, rule_registry
    from .domain import ExpenseCategory

    # snapshot current decisions (the baseline the user is looking at)
    with get_session() as s:
        old = {cid: v.decision.value for cid, v in queries._latest_verdicts(s).items()}

    # start from baseline so the demo is repeatable (always v4 -> v5)
    rule_registry.reset_registry()
    engine.reset_blocked()
    reg = rule_registry.registry
    rule = reg.get(req.rule_id)
    if rule is None:
        raise HTTPException(404, f"unknown rule {req.rule_id}")

    # apply the change: extend the 17(5) blocked-category set
    added = None
    if req.block_category:
        try:
            cat = ExpenseCategory(req.block_category)
        except ValueError:
            raise HTTPException(400, f"unknown category {req.block_category}")
        engine.BLOCKED_CATEGORIES_17_5.add(cat)
        added = cat.value
    new_rule = reg.bump(req.rule_id,
                        condition=rule.condition + f" AND category != '{added}'" if added else rule.condition,
                        approved_by=req.note)
    reg.save()

    # re-run judgment (append-only, so old verdicts remain), reconcile, metrics
    from .demo import run_full
    run_full(regenerate=False)

    with get_session() as s:
        new = {cid: v.decision.value for cid, v in queries._latest_verdicts(s).items()}

    changed = [{"claim_id": cid, "old": old.get(cid), "new": new[cid]}
               for cid in new if old.get(cid) != new[cid]]
    return {
        "rule_id": req.rule_id, "new_version": new_rule.version,
        "blocked_category_added": added,
        "changed_count": len(changed), "changed": changed[:100],
        "summary": queries.get_summary(),
    }


# --- static receipts ------------------------------------------------------
app.mount("/receipts", StaticFiles(directory=str(settings.receipts_dir)), name="receipts")


# --- serve the built frontend (single-service deploy) --------------------
# In dev, Vite serves the SPA on :5173 and proxies here. In production, run
# `npm run build` and this serves the SPA + client-side routes from FastAPI.
_DIST = settings.db_path.parent.parent.parent / "frontend" / "dist"
if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(_DIST / "assets")), name="assets")

    from fastapi.responses import FileResponse

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        # API/receipts are handled above; everything else returns the SPA shell
        # so client-side routes (/, /app) work on refresh.
        candidate = _DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(_DIST / "index.html"))
