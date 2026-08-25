"""Layer 2 — LEARNED judgment (the prediction). ADVISORY ONLY.

P(this invoice appears in the current GSTR-2B). This never decides eligibility —
the deterministic engine already did that. It only tells triage where real money
is at risk, so the agent chases the vendors that won't otherwise file.

This is a calibrated heuristic over the vendor's observed filing behaviour — the
honest fallback the PRD names when a trained model isn't warranted. Because the
2B label arrives free every month, this is exactly the slot a real model drops
into later, with calibration measured on the reliability curve.
"""

from __future__ import annotations

from .domain import Decision, ExpenseCategory, FilingFrequency

# Small category priors: pre-planned B2B spend files more reliably than ad-hoc.
_CATEGORY_PRIOR = {
    ExpenseCategory.SAAS: 0.03, ExpenseCategory.TELECOM: 0.03,
    ExpenseCategory.COWORKING: 0.02, ExpenseCategory.FLIGHT: 0.01,
    ExpenseCategory.HOTEL: 0.0, ExpenseCategory.EQUIPMENT: 0.0,
    ExpenseCategory.CAB: -0.02, ExpenseCategory.MEALS: -0.03,
}


def predict_recoverability(
    decision: Decision,
    reliability_score: float,
    filing_frequency: FilingFrequency | None,
    category: ExpenseCategory,
) -> float:
    """Return a calibrated probability in [0, 1]."""
    # If the law already says the money can't come back, P(recover) is ~0.
    if decision in (Decision.UNRECOVERABLE_WRONG_ENTITY, Decision.BLOCKED_17_5, Decision.EXCEPTION):
        return 0.0

    # QRMP suppliers file quarterly — the invoice will not appear in the current
    # monthly 2B pull, so P(appears now) is low even for a reliable vendor.
    if decision == Decision.PENDING_QRMP or filing_frequency == FilingFrequency.QRMP:
        return round(min(0.15, reliability_score * 0.15), 4)

    # Monthly filer: the base rate IS the vendor's reliability, nudged by the
    # category prior, then clamped.
    p = reliability_score + _CATEGORY_PRIOR.get(category, 0.0)
    return round(max(0.0, min(1.0, p)), 4)
