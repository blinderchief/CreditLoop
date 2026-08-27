"""Layer 2 — DETERMINISTIC judgment (the law).

A pure function. No LLM. No DB. No network. Given the facts of a claim and the
versioned rule registry, it returns a verdict citing rule_id + version. This is
the path an LLM may never touch — the moment a model can silently change a tax
verdict, the product becomes unauditable.

Predicates are keyed by the `check` name each rule declares. The engine walks
the live rules in priority order and stops at the first that does not pass.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from . import rule_registry
from .config import settings
from .domain import Decision, ExpenseCategory, ReasonCode, RECOVERABLE_DECISIONS
from .gstin import is_valid_gstin
from .rule_registry import Rule, RuleRegistry

# Blocked-credit categories under s.17(5). Mutable so the Dynamic Compliance
# Engine can extend it on a rule change, and resettable to baseline.
DEFAULT_BLOCKED_17_5 = {ExpenseCategory.MEALS}
BLOCKED_CATEGORIES_17_5 = set(DEFAULT_BLOCKED_17_5)


def reset_blocked() -> None:
    BLOCKED_CATEGORIES_17_5.clear()
    BLOCKED_CATEGORIES_17_5.update(DEFAULT_BLOCKED_17_5)
ARITHMETIC_TOLERANCE_ABS = 1.0     # rupees
ARITHMETIC_TOLERANCE_PCT = 0.005   # 0.5% of gross


@dataclass
class EvalContext:
    """Everything a predicate may inspect. Mutable only via `flags`."""

    amount_gross: float
    category: ExpenseCategory
    taxable_value: float
    cgst: float
    sgst: float
    igst: float
    supplier_gstin: Optional[str]
    buyer_gstin: Optional[str]
    invoice_no: Optional[str]
    extraction_confidence: float
    # vendor_active / filing_frequency are None when the claim was NOT sent to
    # the GSP (a cheap claim triage chose not to validate). None => assume ok.
    vendor_active: Optional[bool]
    vendor_filing_frequency: Optional[str]   # "monthly" | "QRMP" | None
    seen_keys: set[tuple] = field(default_factory=set)
    # True only when a HIGH-VALUE claim needed validation but the GSP was down
    # and the answer wasn't cached -> decide PROVISIONAL, never block the payout.
    gsp_unverified: bool = False
    # Multi-state place-of-supply facts (PRD v2). Default to the configured
    # company so older callers keep working.
    company_gstins: set[str] = field(default_factory=lambda: set(settings.company_gstins))
    registered_states: set[str] = field(default_factory=lambda: set(settings.registered_states))
    pos_location_of_supply: bool = False   # True if this category is trapped in the supply state

    @property
    def total_tax(self) -> float:
        return round(self.cgst + self.sgst + self.igst, 2)

    @property
    def pos_state(self) -> str:
        return (self.supplier_gstin or "")[:2]

    @property
    def buyer_state(self) -> str:
        return (self.buyer_gstin or "")[:2]


@dataclass
class VerdictResult:
    decision: Decision
    rule_ids: list[str]
    rule_versions: list[int]
    reason_code: Optional[str]
    reasoning: str
    tax_at_stake: float
    provisional: bool = False


# --- Predicates: return True if the rule PASSES (claim survives this check) ---

def _extraction_confident(ctx: EvalContext) -> bool:
    return ctx.extraction_confidence >= 0.60


def _supplier_gstin_present(ctx: EvalContext) -> bool:
    return bool(ctx.supplier_gstin)


def _supplier_gstin_valid(ctx: EvalContext) -> bool:
    return is_valid_gstin(ctx.supplier_gstin)


def _supplier_gstin_active(ctx: EvalContext) -> bool:
    # Fail only when the GSP explicitly reported the registration cancelled.
    # None means "not validated" (cheap claim) — assume ok; provisional-ness,
    # if any, is carried separately by ctx.gsp_unverified.
    return ctx.vendor_active is not False


def _arithmetic_consistent(ctx: EvalContext) -> bool:
    # (1) IGST and CGST/SGST must never both be non-zero on one invoice.
    if ctx.igst > 0 and (ctx.cgst > 0 or ctx.sgst > 0):
        return False
    # (2) taxable + tax must foot to the gross, within tolerance.
    tol = max(ARITHMETIC_TOLERANCE_ABS, ctx.amount_gross * ARITHMETIC_TOLERANCE_PCT)
    return abs(ctx.taxable_value + ctx.total_tax - ctx.amount_gross) <= tol


def _not_duplicate(ctx: EvalContext) -> bool:
    return (ctx.supplier_gstin, ctx.invoice_no) not in ctx.seen_keys


def _billed_to_company(ctx: EvalContext) -> bool:
    # Multi-state: billed to ANY of the company's registered GSTINs.
    return ctx.buyer_gstin in ctx.company_gstins


def _not_blocked_17_5(ctx: EvalContext) -> bool:
    return ctx.category not in BLOCKED_CATEGORIES_17_5


def _registered_in_pos_state(ctx: EvalContext) -> bool:
    # Only supply-located categories can be state-trapped. If the place of
    # supply is a state we aren't registered in, the credit never existed.
    if not ctx.pos_location_of_supply:
        return True
    return ctx.pos_state in ctx.registered_states


def _correct_state_gstin(ctx: EvalContext) -> bool:
    # We ARE registered in the POS state, but did the invoice use that state's
    # GSTIN? If not, the credit was available and thrown away by a fixable
    # mistake -> WRONG_GSTIN_USED.
    if not ctx.pos_location_of_supply:
        return True
    return ctx.buyer_state == ctx.pos_state


def _supplier_files_monthly(ctx: EvalContext) -> bool:
    # None => not validated (cheap claim); assume monthly so we don't spuriously
    # mark it PENDING_QRMP. Only a confirmed QRMP filer fails this check.
    if ctx.vendor_filing_frequency is None:
        return True
    return ctx.vendor_filing_frequency == "monthly"


def _noop(ctx: EvalContext) -> bool:
    return True


PREDICATES = {
    "extraction_confident": _extraction_confident,
    "supplier_gstin_present": _supplier_gstin_present,
    "supplier_gstin_valid": _supplier_gstin_valid,
    "supplier_gstin_active": _supplier_gstin_active,
    "arithmetic_consistent": _arithmetic_consistent,
    "not_duplicate": _not_duplicate,
    "billed_to_company": _billed_to_company,
    "not_blocked_17_5": _not_blocked_17_5,
    "registered_in_pos_state": _registered_in_pos_state,
    "correct_state_gstin": _correct_state_gstin,
    "supplier_files_monthly": _supplier_files_monthly,
    "noop": _noop,
}


def _parse_verdict(spec: str) -> tuple[Decision, Optional[str]]:
    """'EXCEPTION:MISSING_GSTIN' -> (EXCEPTION, 'MISSING_GSTIN'); 'BLOCKED_17_5' -> (BLOCKED_17_5, None)."""
    if spec.startswith("EXCEPTION:"):
        return Decision.EXCEPTION, spec.split(":", 1)[1]
    return Decision(spec), None


def evaluate(ctx: EvalContext, reg: RuleRegistry | None = None) -> VerdictResult:
    # Look the registry up dynamically so a version bump propagates immediately.
    reg = reg or rule_registry.registry
    checked_ids: list[str] = []
    checked_versions: list[int] = []

    for rule in reg.live_rules:
        predicate = PREDICATES.get(rule.check)
        if predicate is None:
            continue  # unknown check -> skip rather than guess
        checked_ids.append(rule.rule_id)
        checked_versions.append(rule.version)
        if not predicate(ctx):
            decision, reason = _parse_verdict(rule.verdict)
            provisional = ctx.gsp_unverified and decision in RECOVERABLE_DECISIONS
            if provisional:
                decision = Decision.PROVISIONAL
                reason = ReasonCode.CONTESTED_RULE.value if reason is None else reason
            return VerdictResult(
                decision=decision,
                rule_ids=checked_ids, rule_versions=checked_versions,
                reason_code=reason,
                reasoning=_explain(rule, decision, ctx),
                tax_at_stake=ctx.total_tax,
                provisional=provisional,
            )

    # All rules passed -> eligible.
    provisional = ctx.gsp_unverified
    if provisional:
        decision = Decision.PROVISIONAL
        reasoning = "All eligibility rules passed under degraded GSP — marked PROVISIONAL, queued for refresh."
    elif not ctx.pos_location_of_supply and ctx.igst > 0:
        # cross-state supply that follows the recipient → IGST, fully claimable
        decision = Decision.RECOVERABLE_IGST
        reasoning = ("Place of supply follows the recipient; interstate IGST is claimable at our "
                     "registered location. Recoverable.")
    else:
        decision = Decision.RECOVERABLE
        reasoning = "All eligibility rules passed. ITC is recoverable once the supplier files."
    return VerdictResult(
        decision=decision,
        rule_ids=checked_ids, rule_versions=checked_versions,
        reason_code=(ReasonCode.CONTESTED_RULE.value if provisional else None),
        reasoning=reasoning,
        tax_at_stake=ctx.total_tax,
        provisional=provisional,
    )


def _state_name(code: str) -> str:
    from .config import STATE_NAMES
    return STATE_NAMES.get(code, code)


def _explain(rule: Rule, decision: Decision, ctx: EvalContext) -> str:
    tax = f"₹{ctx.total_tax:,.2f}"
    if decision == Decision.STATE_TRAPPED:
        return (f"Place of supply is {_state_name(ctx.pos_state)} ({ctx.pos_state}) — you're only "
                f"registered in {', '.join(sorted(_state_name(s) for s in ctx.registered_states))}. "
                f"{tax} of GST is structurally dead: no invoice, in any name, can recover it. "
                f"Book as cost; do not claim. Cited {rule.rule_id} v{rule.version} ({rule.source_citation}).")
    if decision == Decision.WRONG_GSTIN_USED:
        right = settings.gstin_for_state(ctx.pos_state) or f"the {_state_name(ctx.pos_state)} GSTIN"
        return (f"Place of supply is {_state_name(ctx.pos_state)}, where you ARE registered — but the "
                f"invoice used the {_state_name(ctx.buyer_state)} GSTIN. {tax} is recoverable if reissued "
                f"against {right}. Fixable. Cited {rule.rule_id} v{rule.version}.")
    if decision == Decision.UNRECOVERABLE_WRONG_ENTITY:
        return (f"Invoice is billed to '{ctx.buyer_gstin or 'an individual'}', not the company "
                f"GSTIN. {tax} of GST cannot be claimed. Cited {rule.rule_id} v{rule.version} "
                f"({rule.source_citation}).")
    if decision == Decision.BLOCKED_17_5:
        return (f"Category '{ctx.category.value}' is a blocked credit under "
                f"{rule.source_citation}. {tax} is not claimable. Cited {rule.rule_id} "
                f"v{rule.version}.")
    if decision == Decision.PENDING_QRMP:
        return (f"Supplier files under QRMP; the 2B line can lag up to a quarter. "
                f"{tax} is recoverable but not yet visible. Cited {rule.rule_id} v{rule.version}.")
    if decision == Decision.EXCEPTION:
        return (f"Refused to decide: {rule.condition} failed. {rule.rule_id} v{rule.version}. "
                f"Routed to the exception list.")
    if decision == Decision.PROVISIONAL:
        return (f"Decided under degraded conditions ({rule.rule_id} v{rule.version}); "
                f"marked PROVISIONAL, payout not blocked.")
    return f"{rule.rule_id} v{rule.version}."
