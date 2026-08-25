"""Layer 2 — the triage policy (PRD sections 5 & 9).

The agent's real job is deciding which claims deserve attention, not reading
receipts. Most claims should cost nothing.

    expected_value = tax_at_stake * P(recoverable) - cost_to_process
    if expected_value < 0:  auto-approve, spend zero API calls, bother no one

Tiers by tax at stake:
    tier_0  tax < ₹200                     -> auto-approve, 0 live calls
    tier_1  ₹200–₹2,000                     -> cached vendor data only
    tier_2  > ₹2,000                        -> full pipeline, live GSP validation
    tier_3  > ₹2,000 AND p_recoverable<0.5  -> intervene: draft a vendor request
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import settings
from .domain import Tier

# Planned live/model calls per tier — the budget the triage authorises. The
# pipeline reports ACTUAL calls too; the gap is the whole efficiency story.
TIER_CALL_BUDGET = {Tier.TIER_0: 0, Tier.TIER_1: 0, Tier.TIER_2: 2, Tier.TIER_3: 3}


@dataclass
class TriageDecision:
    tier: Tier
    tax_at_stake: float
    p_recoverable: float
    expected_value: float
    call_budget: int
    intervene: bool
    rationale: str


def triage(tax_at_stake: float, p_recoverable: float) -> TriageDecision:
    cost = 0.0  # filled once we know the tier's budget
    if tax_at_stake < settings.tier0_max_tax:
        tier = Tier.TIER_0
        rationale = f"Tax {tax_at_stake:.0f} < ₹{settings.tier0_max_tax:.0f}: auto-approve, 0 calls."
    elif tax_at_stake < settings.tier1_max_tax:
        tier = Tier.TIER_1
        rationale = f"Tax in ₹{settings.tier0_max_tax:.0f}–₹{settings.tier1_max_tax:.0f}: cached vendor data only."
    else:
        if p_recoverable < settings.intervene_p_below:
            tier = Tier.TIER_3
            rationale = (f"Tax > ₹{settings.tier1_max_tax:.0f} and P(recover)="
                         f"{p_recoverable:.2f} < {settings.intervene_p_below}: intervene, chase vendor.")
        else:
            tier = Tier.TIER_2
            rationale = f"Tax > ₹{settings.tier1_max_tax:.0f}: full pipeline, live GSP validation."

    budget = TIER_CALL_BUDGET[tier]
    cost = budget * settings.cost_per_api_call
    ev = round(tax_at_stake * p_recoverable - cost, 2)
    return TriageDecision(
        tier=tier, tax_at_stake=round(tax_at_stake, 2), p_recoverable=round(p_recoverable, 4),
        expected_value=ev, call_budget=budget, intervene=(tier == Tier.TIER_3),
        rationale=rationale,
    )
