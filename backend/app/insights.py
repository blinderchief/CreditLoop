"""PRD v2 §4 — the three CFO-facing outputs that make this a company, not a
workflow task: the overclaim scanner, the registration ROI report, and the
GSTIN picker. All read-only over the append-only ledger."""

from __future__ import annotations

from sqlmodel import select

from .config import STATE_NAMES, settings
from .db import get_session
from .domain import Decision, POS_BY_CATEGORY, PlaceOfSupply
from .models import Claim, Invoice, Verdict

DEAD = {Decision.STATE_TRAPPED, Decision.BLOCKED_17_5, Decision.UNRECOVERABLE_WRONG_ENTITY}
REG_COST_PER_STATE_YR = 40000.0   # rough compliance cost of an extra registration


def _latest_verdicts(s) -> dict:
    out = {}
    for v in s.exec(select(Verdict).order_by(Verdict.created_at)).all():
        out[v.claim_id] = v
    return out


def _state(code: str | None) -> str:
    return STATE_NAMES.get(code or "", code or "?")


def overclaim_report() -> dict:
    """Dead credit that was already claimed in a filed GSTR-3B → money owed back,
    with 24% p.a. interest. The loudest number in the product."""
    with get_session() as s:
        claims = s.exec(select(Claim)).all()
        invoices = {i.claim_id: i for i in s.exec(select(Invoice)).all()}
        verdicts = _latest_verdicts(s)

    buckets: dict[str, dict] = {}
    total = 0.0
    for c in claims:
        if not c.already_claimed:
            continue
        v = verdicts.get(c.claim_id)
        if not v or v.decision not in DEAD:
            continue
        if v.decision == Decision.BLOCKED_17_5:
            label = "Restaurant / meals claimed despite s.17(5)"
        elif v.decision == Decision.STATE_TRAPPED:
            label = f"Out-of-state {c.category.value} (place of supply not registered)"
        else:
            label = "Invoice in an individual's name"
        b = buckets.setdefault(label, {"label": label, "amount": 0.0, "claims": 0})
        b["amount"] = round(b["amount"] + v.tax_at_stake, 2)
        b["claims"] += 1
        total += v.tax_at_stake

    rows = sorted(buckets.values(), key=lambda r: -r["amount"])
    return {
        "exposure": round(total, 2),
        "interest_24pc_yr": round(total * 0.24, 2),
        "claims": sum(r["claims"] for r in rows),
        "breakdown": rows,
    }


def registration_roi() -> dict:
    """Trapped credit grouped by the state it's stuck in — a registration in a
    state pays for itself once trapped credit there exceeds the compliance cost.
    The decision no Indian CFO currently has the data to make."""
    with get_session() as s:
        claims = s.exec(select(Claim)).all()
        invoices = {i.claim_id: i for i in s.exec(select(Invoice)).all()}
        verdicts = _latest_verdicts(s)

    by_state: dict[str, float] = {}
    for c in claims:
        v = verdicts.get(c.claim_id)
        if not v or v.decision != Decision.STATE_TRAPPED:
            continue
        inv = invoices.get(c.claim_id)
        st = (inv.place_of_supply_state if inv else None) or (inv.supplier_state_code if inv else None)
        by_state[st] = round(by_state.get(st, 0.0) + v.tax_at_stake, 2)

    rows = []
    for st, amt in sorted(by_state.items(), key=lambda kv: -kv[1]):
        rows.append({
            "state_code": st, "state_name": _state(st), "trapped": amt,
            "net_if_registered": round(amt - REG_COST_PER_STATE_YR, 2),
            "worth_it": amt > REG_COST_PER_STATE_YR,
        })
    return {
        "registered_states": [{"code": r["state_code"], "name": r["state_name"]}
                              for r in settings.company_registrations],
        "cost_per_registration_yr": REG_COST_PER_STATE_YR,
        "by_state": rows,
        "total_trapped": round(sum(by_state.values()), 2),
    }


def gstin_picker(destination_state: str, category: str) -> dict:
    """Before booking: which GSTIN should the employee put on the bill?"""
    from .domain import ExpenseCategory
    try:
        cat = ExpenseCategory(category)
    except ValueError:
        return {"ok": False, "error": f"unknown category {category}"}

    pos = POS_BY_CATEGORY[cat]
    ds = destination_state
    if pos == PlaceOfSupply.LOCATION_OF_RECIPIENT:
        return {"ok": True, "advice": "recoverable_anywhere",
                "gstin": settings.company_gstin,
                "message": (f"{cat.value.title()} follows your registered location — use your primary "
                            f"GSTIN {settings.company_gstin}. Interstate is IGST and fully claimable.")}
    # location of supply → trapped in the destination state
    if ds in settings.registered_states:
        g = settings.gstin_for_state(ds)
        return {"ok": True, "advice": "use_state_gstin", "gstin": g, "state": _state(ds),
                "message": (f"Booking {cat.value} in {_state(ds)}? Give them {g} ({_state(ds)}), "
                            f"not another state's — the credit is stuck in {_state(ds)}.")}
    return {"ok": True, "advice": "structurally_dead", "gstin": None, "state": _state(ds),
            "message": (f"You're not registered in {_state(ds)}. GST on {cat.value} there is "
                        f"structurally dead — book it as cost, and do not claim it.")}
