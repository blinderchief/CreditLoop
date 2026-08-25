"""P1.2 / P1.3 — the Dynamic Compliance Engine.

    GST source  ->  [Change Detection Agent, Gemini]  ->  structured rule diff
                ->  [Review Queue]  ->  [Human/CA approval]  ->  rule vN+1
                ->  re-evaluate affected history

The LLM's job is *detection and drafting a proposal*, never live application.
That guardrail is the whole point: an LLM auto-applying its reading of a
circular is how you generate wrong ITC at scale. Speed of detection is the win;
autonomy of application is the risk. We separate them.

Works with no key via a fixture advisory + a deterministic proposal.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlmodel import select

from .db import get_session
from .domain import ExpenseCategory
from .llm import client, LLMUnavailable
from .log import banner, console, log, step
from .models import AuditEvent, RuleProposal

# A small corpus of GST source snippets. In production this is a daily RAG over
# CBIC notifications / GSTN advisories; here two fixtures make the flow real.
SOURCES = [
    {
        "title": "GSTN Advisory 2026/14 — hospitality co-working ITC",
        "url": "https://www.gst.gov.in/newsandupdates/read/2026-14",
        "excerpt": ("Advisory clarifies that input tax credit on co-working and shared-office "
                    "membership charges, where used for board/lodging-linked hospitality, is to be "
                    "treated as a blocked credit analogous to Section 17(5)(b) with effect from the "
                    "next return period, pending Council ratification."),
        "hint_category": "coworking",
    },
]


def _fallback_proposal(source: dict) -> dict:
    cat = source.get("hint_category", "coworking")
    return {
        "target_rule_id": "SEC_17_5_B_FOOD_BEVERAGE",
        "action": "add_blocked_category",
        "payload": {"category": cat},
        "rationale": (f"The advisory extends 17(5)-style blocking to '{cat}'. Proposed as a new "
                      f"version of the 17(5) rule; contested/pending Council ratification, so it "
                      f"must be CA-approved before going live."),
    }


def detect_changes() -> list[RuleProposal]:
    """Read the source corpus and draft rule-diff proposals into the review queue."""
    step("Change Detection Agent — scanning GST sources")
    proposals: list[RuleProposal] = []

    with get_session() as s:
        for source in SOURCES:
            # skip if we already have a pending/handled proposal for this source
            existing = s.exec(select(RuleProposal).where(
                RuleProposal.source_title == source["title"])).first()
            if existing:
                continue

            diff = _fallback_proposal(source)
            used = "fixture"
            if client.enabled:
                try:
                    prompt = (
                        "You monitor Indian GST changes. Read this advisory and propose ONE structured "
                        "rule diff for a versioned rule registry. Return strict JSON: "
                        "{target_rule_id, action, payload, rationale}. Valid action for now is "
                        "'add_blocked_category' with payload {category: one of "
                        "hotel|flight|cab|meals|saas|equipment|telecom|coworking}. Be conservative; "
                        "if contested, say so in rationale.\n\nADVISORY:\n" + source["excerpt"]
                    )
                    raw = json.loads(client.complete(prompt, json_out=True, temperature=0.1))
                    if raw.get("payload", {}).get("category") in {c.value for c in ExpenseCategory}:
                        diff = raw
                        used = "gemini"
                except (LLMUnavailable, ValueError, KeyError) as e:
                    log.warning("[loop.risk]Change detection via Gemini failed (%s) — using fixture[/]", e)

            prop = RuleProposal(
                source_title=source["title"], source_excerpt=source["excerpt"],
                source_url=source["url"], target_rule_id=diff["target_rule_id"],
                action=diff["action"], payload=diff["payload"], rationale=diff["rationale"],
                status="pending",
            )
            s.add(prop)
            s.add(AuditEvent(actor="compliance_agent", action="proposal.detected",
                  detail={"source": source["title"], "via": used, "diff": diff}))
            proposals.append(prop)

    banner("Change detection complete", f"{len(proposals)} new proposal(s) in the review queue")
    for p in proposals:
        console.print(f"  [loop.risk]PENDING[/] {p.source_title} → block "
                      f"{p.payload.get('category')} (needs CA approval)")
    return proposals


def approve_proposal(proposal_id: str, reviewer: str = "ca_demo") -> dict:
    """Human-approval gate: apply the diff (rule vN+1), then re-evaluate history."""
    from . import engine, rule_registry
    from .demo import run_full

    with get_session() as s:
        prop = s.get(RuleProposal, proposal_id)
        if not prop or prop.status != "pending":
            return {"ok": False, "error": "proposal not found or already handled"}
        # snapshot old decisions
        from .queries import _latest_verdicts
        old = {cid: v.decision.value for cid, v in _latest_verdicts(s).items()}

    # apply on top of the current baseline
    reg = rule_registry.registry
    added = None
    if prop.action == "add_blocked_category":
        cat = ExpenseCategory(prop.payload["category"])
        engine.BLOCKED_CATEGORIES_17_5.add(cat)
        added = cat.value
        reg.bump(prop.target_rule_id,
                 condition=f"blocked category extended: {added}",
                 approved_by=f"{reviewer} · {prop.source_title}",
                 status=rule_registry.RuleStatus.CONTESTED, confidence="contested")
        reg.save()

    run_full(regenerate=False)

    with get_session() as s:
        from .queries import _latest_verdicts
        new = {cid: v.decision.value for cid, v in _latest_verdicts(s).items()}
        prop = s.get(RuleProposal, proposal_id)
        changed = [cid for cid in new if old.get(cid) != new[cid]]
        prop.status = "approved"
        prop.reviewed_by = reviewer
        prop.reviewed_at = datetime.now(timezone.utc)
        prop.changed_claim_count = len(changed)
        s.add(prop)
        s.add(AuditEvent(actor="ca", action="proposal.approved",
              detail={"proposal": proposal_id, "blocked_category": added,
                      "changed_claims": len(changed)}))

    return {"ok": True, "blocked_category_added": added, "changed_count": len(changed)}


def reject_proposal(proposal_id: str, reviewer: str = "ca_demo") -> dict:
    with get_session() as s:
        prop = s.get(RuleProposal, proposal_id)
        if not prop or prop.status != "pending":
            return {"ok": False, "error": "proposal not found or already handled"}
        prop.status = "rejected"
        prop.reviewed_by = reviewer
        prop.reviewed_at = datetime.now(timezone.utc)
        s.add(prop)
        s.add(AuditEvent(actor="ca", action="proposal.rejected", detail={"proposal": proposal_id}))
    return {"ok": True}


def list_proposals() -> list[dict]:
    with get_session() as s:
        props = s.exec(select(RuleProposal).order_by(RuleProposal.created_at.desc())).all()
    return [{
        "id": p.id, "source_title": p.source_title, "source_excerpt": p.source_excerpt,
        "source_url": p.source_url, "target_rule_id": p.target_rule_id, "action": p.action,
        "payload": p.payload, "rationale": p.rationale, "status": p.status,
        "reviewed_by": p.reviewed_by, "changed_claim_count": p.changed_claim_count,
        "created_at": p.created_at.isoformat(),
    } for p in props]
