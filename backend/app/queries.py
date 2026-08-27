"""Read helpers for the API. Money counters are computed live from the
append-only ledger; run-time stats (GSP calls, throughput, match rate) are read
from the run_summary.json the demo writes."""

from __future__ import annotations

import json
from typing import Optional

from sqlmodel import select

from .config import settings
from .db import get_session
from .domain import Decision, DEAD_DECISIONS, RECOVERABLE_DECISIONS
from .models import AuditEvent, Claim, Invoice, Payout, TwoBLine, Vendor, Verdict

RUN_SUMMARY_PATH = settings.db_path.parent / "run_summary.json"
GROUND_TRUTH_PATH = settings.db_path.parent / "ground_truth.json"


def _latest_verdicts(session) -> dict[str, Verdict]:
    """Latest verdict per claim (append-only table => take max created_at)."""
    out: dict[str, Verdict] = {}
    for v in session.exec(select(Verdict).order_by(Verdict.created_at)).all():
        out[v.claim_id] = v  # later rows overwrite -> newest wins
    return out


def _run_summary() -> dict:
    if RUN_SUMMARY_PATH.exists():
        return json.loads(RUN_SUMMARY_PATH.read_text())
    return {}


def _ground_truth() -> dict:
    if GROUND_TRUTH_PATH.exists():
        return {t["claim_id"]: t for t in json.loads(GROUND_TRUTH_PATH.read_text())}
    return {}


def get_summary() -> dict:
    """The counter + headline numbers for the dashboard."""
    with get_session() as s:
        claims = s.exec(select(Claim)).all()
        verdicts = _latest_verdicts(s)
        payouts = {p.claim_id: p for p in s.exec(select(Payout)).all()}
        lines = s.exec(select(TwoBLine)).all()

    n = len(claims)
    # Three fates (PRD v2): recoverable / structurally dead / wrongly claimed.
    money = {"recoverable": 0.0, "structurally_dead": 0.0, "overclaimed": 0.0,
             "at_risk_chase": 0.0, "fixable_wrong_gstin": 0.0, "state_trapped": 0.0,
             "blocked_17_5": 0.0, "lost_wrong_entity": 0.0, "total_gst": 0.0}
    decisions: dict[str, int] = {}
    tiers = {0: 0, 1: 0, 2: 0, 3: 0}
    reissue = 0

    for c in claims:
        v = verdicts.get(c.claim_id)
        tiers[c.tier] = tiers.get(c.tier, 0) + 1
        if not v:
            continue
        decisions[v.decision.value] = decisions.get(v.decision.value, 0) + 1
        tax = v.tax_at_stake
        money["total_gst"] += tax
        if v.decision in RECOVERABLE_DECISIONS:
            money["recoverable"] += tax
            if v.predicted_recoverable_p < settings.intervene_p_below and v.decision != Decision.WRONG_GSTIN_USED:
                money["at_risk_chase"] += tax
            if v.decision == Decision.WRONG_GSTIN_USED:
                money["fixable_wrong_gstin"] += tax
                reissue += 1
        elif v.decision in DEAD_DECISIONS:
            if c.already_claimed:
                money["overclaimed"] += tax          # dead AND already claimed → owe back
            else:
                money["structurally_dead"] += tax    # dead, correctly not claimed
            if v.decision == Decision.STATE_TRAPPED:
                money["state_trapped"] += tax
            elif v.decision == Decision.BLOCKED_17_5:
                money["blocked_17_5"] += tax
            elif v.decision == Decision.UNRECOVERABLE_WRONG_ENTITY:
                money["lost_wrong_entity"] += tax
                reissue += 1

    money = {k: round(val, 2) for k, val in money.items()}
    paid = sum(1 for p in payouts.values() if p.status.value in ("paid", "reconciled"))
    matched = sum(1 for l in lines if l.matched_claim_id)

    overclaim_claims = sum(1 for c in claims
                           if c.already_claimed and verdicts.get(c.claim_id)
                           and verdicts[c.claim_id].decision in DEAD_DECISIONS)

    run = _run_summary()
    return {
        "company": {
            "name": settings.company_name, "gstin": settings.company_gstin,
            "registrations": [{"state_code": r["state_code"], "state_name": r["state_name"],
                               "gstin": r["gstin"]} for r in settings.company_registrations],
        },
        "batch": {
            "claims": n,
            "exceptions": decisions.get("EXCEPTION", 0),
            "paid": paid,
            "overclaim_claims": overclaim_claims,
            "held": sum(1 for c in claims if c.status.value == "exception") - decisions.get("EXCEPTION", 0),
        },
        "money": money,
        "reissue_candidates": reissue,
        "decisions": decisions,
        "tiers": {f"tier_{k}": tiers.get(k, 0) for k in range(4)},
        "match": {"matched": matched, "total_lines": len(lines),
                  "match_rate": round(matched / len(lines), 4) if lines else 0.0},
        "efficiency": run.get("pipeline", {}).get("gsp", {}),
        "gsp_calls_per_claim": run.get("pipeline", {}).get("gsp_calls_per_claim"),
        "throughput": {"claims_per_min": run.get("pipeline", {}).get("claims_per_min"),
                       "elapsed_s": run.get("pipeline", {}).get("elapsed_s")},
        "reconcile": run.get("reconcile", {}),
        "failure_flags": run.get("failure_flags", {}),
        "ran_at": run.get("ran_at"),
    }


def list_claims(status: Optional[str] = None, tier: Optional[int] = None,
                decision: Optional[str] = None, q: Optional[str] = None,
                limit: int = 500) -> list[dict]:
    with get_session() as s:
        claims = s.exec(select(Claim).order_by(Claim.seq)).all()
        invoices = {i.claim_id: i for i in s.exec(select(Invoice)).all()}
        verdicts = _latest_verdicts(s)

    rows = []
    for c in claims:
        v = verdicts.get(c.claim_id)
        inv = invoices.get(c.claim_id)
        if status and c.status.value != status:
            continue
        if tier is not None and c.tier != tier:
            continue
        if decision and (not v or v.decision.value != decision):
            continue
        if q:
            hay = f"{c.employee_name} {c.description} {inv.supplier_name if inv else ''}".lower()
            if q.lower() not in hay:
                continue
        rows.append({
            "claim_id": c.claim_id, "seq": c.seq, "employee_name": c.employee_name,
            "category": c.category.value, "amount_gross": c.amount_gross, "status": c.status.value,
            "tier": c.tier, "supplier_name": inv.supplier_name if inv else "",
            "decision": v.decision.value if v else None,
            "reason_code": v.reason_code if v else None,
            "tax_at_stake": v.tax_at_stake if v else 0.0,
            "p_recoverable": v.predicted_recoverable_p if v else 0.0,
        })
    return rows[:limit]


def get_claim_detail(claim_id: str) -> Optional[dict]:
    with get_session() as s:
        claim = s.get(Claim, claim_id)
        if not claim:
            return None
        inv = s.exec(select(Invoice).where(Invoice.claim_id == claim_id)).first()
        verdicts = s.exec(select(Verdict).where(Verdict.claim_id == claim_id)
                          .order_by(Verdict.created_at)).all()
        payout = s.exec(select(Payout).where(Payout.claim_id == claim_id)).first()
        audit = s.exec(select(AuditEvent).where(AuditEvent.claim_id == claim_id)
                       .order_by(AuditEvent.at)).all()
        line = None
        if inv and inv.supplier_gstin and inv.invoice_no:
            line = s.exec(select(TwoBLine).where(TwoBLine.gstin == inv.supplier_gstin,
                          TwoBLine.invoice_no == inv.invoice_no)).first()

    gt = _ground_truth().get(claim_id, {})
    return {
        "claim": {
            "claim_id": claim.claim_id, "seq": claim.seq, "employee_name": claim.employee_name,
            "employee_id": claim.employee_id, "category": claim.category.value,
            "amount_gross": claim.amount_gross, "description": claim.description,
            "status": claim.status.value, "tier": claim.tier,
            "expected_value_score": claim.expected_value_score,
            "receipt_path": claim.receipt_path, "already_claimed": claim.already_claimed,
        },
        "invoice": _invoice_dict(inv) if inv else None,
        "verdicts": [_verdict_dict(v) for v in verdicts],
        "payout": _payout_dict(payout) if payout else None,
        "two_b_line": _line_dict(line) if line else None,
        "audit": [_audit_dict(a) for a in audit],
        "scenario": gt.get("scenario"),  # honest label for the demo
    }


def list_exceptions() -> list[dict]:
    """The graded artifact: every claim the agent refused to decide, with a
    machine-readable reason, plus reconciliation attention items."""
    rows = list_claims()
    return [r for r in rows if r["decision"] == "EXCEPTION"]


def list_vendors() -> list[dict]:
    with get_session() as s:
        vendors = s.exec(select(Vendor)).all()
    out = [{
        "gstin": v.gstin, "legal_name": v.legal_name,
        "filing_frequency": v.filing_frequency.value,
        "reliability_score": v.reliability_score, "active": v.active,
        "observation_count": v.observation_count,
    } for v in vendors]
    out.sort(key=lambda x: -x["reliability_score"])
    return out


def get_metrics() -> dict:
    path = settings.db_path.parent / "metrics_report.json"
    return json.loads(path.read_text()) if path.exists() else {}


def list_audit(limit: int = 200) -> list[dict]:
    with get_session() as s:
        events = s.exec(select(AuditEvent).order_by(AuditEvent.at.desc()).limit(limit)).all()
    return [_audit_dict(a) for a in events]


# --- serializers ----------------------------------------------------------

def _invoice_dict(i: Invoice) -> dict:
    from .config import STATE_NAMES
    return {"supplier_gstin": i.supplier_gstin, "supplier_name": i.supplier_name,
            "invoice_no": i.invoice_no, "invoice_date": i.invoice_date,
            "taxable_value": i.taxable_value, "cgst": i.cgst, "sgst": i.sgst, "igst": i.igst,
            "total_tax": i.total_tax, "buyer_gstin": i.buyer_gstin, "buyer_name": i.buyer_name,
            "extraction_confidence": i.extraction_confidence,
            "extraction_method": i.extraction_method.value,
            "supplier_state_code": i.supplier_state_code,
            "supplier_state": STATE_NAMES.get(i.supplier_state_code or "", i.supplier_state_code),
            "place_of_supply_state": i.place_of_supply_state,
            "place_of_supply": STATE_NAMES.get(i.place_of_supply_state or "", i.place_of_supply_state),
            "tax_type": i.tax_type}


def _verdict_dict(v: Verdict) -> dict:
    return {"verdict_id": v.verdict_id, "decision": v.decision.value,
            "rule_ids": v.rule_ids, "rule_versions": v.rule_versions,
            "rules": [f"{r} v{ver}" for r, ver in zip(v.rule_ids, v.rule_versions)],
            "reason_code": v.reason_code, "predicted_recoverable_p": v.predicted_recoverable_p,
            "tax_at_stake": v.tax_at_stake, "reasoning": v.reasoning,
            "provisional": v.provisional, "created_at": v.created_at.isoformat()}


def _payout_dict(p: Payout) -> dict:
    return {"payout_id": p.payout_id, "idempotency_key": p.idempotency_key,
            "razorpay_ref": p.razorpay_ref, "amount": p.amount, "status": p.status.value,
            "rail": p.rail, "settled_at": p.settled_at.isoformat() if p.settled_at else None}


def _line_dict(l: TwoBLine) -> dict:
    return {"gstin": l.gstin, "invoice_no": l.invoice_no, "invoice_date": l.invoice_date,
            "taxable_value": l.taxable_value, "tax": l.tax, "return_period": l.return_period,
            "matched_claim_id": l.matched_claim_id}


def _audit_dict(a: AuditEvent) -> dict:
    return {"id": a.id, "claim_id": a.claim_id, "at": a.at.isoformat(),
            "actor": a.actor, "action": a.action, "detail": a.detail}
