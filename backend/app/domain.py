"""The shared vocabulary of CreditLoop.

Enums here are the *contract* between layers. A verdict Decision, an exception
ReasonCode, a triage Tier — these strings appear in the ledger, the API, and
the dashboard, so they must be stable and machine-readable."""

from __future__ import annotations

from enum import Enum


class ExpenseCategory(str, Enum):
    HOTEL = "hotel"
    FLIGHT = "flight"
    CAB = "cab"
    MEALS = "meals"
    SAAS = "saas"
    EQUIPMENT = "equipment"
    TELECOM = "telecom"
    COWORKING = "coworking"


# Categories whose GST is *concentrated and recoverable* — the pre-planned
# high-value spend the whole product is built to catch (PRD section 5).
HIGH_VALUE_CATEGORIES = {
    ExpenseCategory.HOTEL,
    ExpenseCategory.FLIGHT,
    ExpenseCategory.SAAS,
    ExpenseCategory.EQUIPMENT,
    ExpenseCategory.TELECOM,
    ExpenseCategory.COWORKING,
}


class ClaimStatus(str, Enum):
    SUBMITTED = "submitted"
    EXTRACTED = "extracted"
    JUDGED = "judged"
    APPROVED = "approved"
    PAID = "paid"
    EXCEPTION = "exception"
    INTERVENTION = "intervention"  # vendor reissue requested


class Decision(str, Enum):
    """The verdict on whether the GST comes back. Only the deterministic engine
    may emit these — an LLM never sets a Decision."""

    RECOVERABLE = "RECOVERABLE"                       # all ITC conditions look met
    RECOVERABLE_IGST = "RECOVERABLE_IGST"             # cross-state but IGST → follows the recipient
    PROVISIONAL = "PROVISIONAL"                       # decided under uncertainty (GSP down, etc.)
    PENDING_QRMP = "PENDING_QRMP"                      # supplier files quarterly; 2B will lag
    WRONG_GSTIN_USED = "WRONG_GSTIN_USED"             # right POS state, wrong company GSTIN — FIXABLE
    UNRECOVERABLE_WRONG_ENTITY = "UNRECOVERABLE_WRONG_ENTITY"  # invoice not in any company GSTIN
    STATE_TRAPPED = "STATE_TRAPPED"                    # place of supply is a state we're not registered in
    BLOCKED_17_5 = "BLOCKED_17_5"                      # Section 17(5) blocked credit
    EXCEPTION = "EXCEPTION"                            # agent refused to decide


# --- Three fates (PRD v2 §1). Every decided claim lands in exactly one. -----
# RECOVERABLE  — credit is available (or becomes available once a fixable
#                mistake is corrected); claim it.
# STRUCTURALLY_DEAD — credit never existed; no action creates it. Book as cost,
#                do NOT claim. (Claiming it anyway is the overclaim trap.)
RECOVERABLE_DECISIONS = {
    Decision.RECOVERABLE, Decision.RECOVERABLE_IGST, Decision.PROVISIONAL,
    Decision.PENDING_QRMP, Decision.WRONG_GSTIN_USED,
}
DEAD_DECISIONS = {
    Decision.STATE_TRAPPED, Decision.BLOCKED_17_5, Decision.UNRECOVERABLE_WRONG_ENTITY,
}
# Fixable within the recoverable set — worth an intervention (reissue).
FIXABLE_DECISIONS = {Decision.WRONG_GSTIN_USED, Decision.UNRECOVERABLE_WRONG_ENTITY}


class PlaceOfSupply(str, Enum):
    """Where a supply *legally happens* decides which state's tax it carries."""

    LOCATION_OF_SUPPLY = "LOCATION_OF_SUPPLY"        # you had to be there → trapped in that state
    LOCATION_OF_RECIPIENT = "LOCATION_OF_RECIPIENT"  # it came to you → credit follows you


# Category → place-of-supply rule. "If you had to physically be somewhere to
# consume it, the credit is stuck in that state; if it came to you, it follows
# you." (s.12 IGST Act; CBIC 2019 clarification; multiple AAR rulings.)
POS_BY_CATEGORY = {
    ExpenseCategory.HOTEL: PlaceOfSupply.LOCATION_OF_SUPPLY,
    ExpenseCategory.CAB: PlaceOfSupply.LOCATION_OF_SUPPLY,
    ExpenseCategory.MEALS: PlaceOfSupply.LOCATION_OF_SUPPLY,      # also blocked u/s 17(5)
    ExpenseCategory.COWORKING: PlaceOfSupply.LOCATION_OF_SUPPLY,  # venue / immovable property
    ExpenseCategory.SAAS: PlaceOfSupply.LOCATION_OF_RECIPIENT,
    ExpenseCategory.EQUIPMENT: PlaceOfSupply.LOCATION_OF_RECIPIENT,
    ExpenseCategory.TELECOM: PlaceOfSupply.LOCATION_OF_RECIPIENT,
    ExpenseCategory.FLIGHT: PlaceOfSupply.LOCATION_OF_RECIPIENT,
}


class ReasonCode(str, Enum):
    """Every unresolved claim carries exactly one of these. This IS the
    exception list Track 04 is graded on."""

    LOW_EXTRACTION_CONFIDENCE = "LOW_EXTRACTION_CONFIDENCE"  # VLM unsure, do not guess a GSTIN
    MISSING_GSTIN = "MISSING_GSTIN"                          # no supplier GSTIN on the invoice
    INVALID_GSTIN = "INVALID_GSTIN"                          # checksum / format fails
    GSTIN_NOT_ACTIVE = "GSTIN_NOT_ACTIVE"                    # GSP says registration cancelled
    ARITHMETIC_MISMATCH = "ARITHMETIC_MISMATCH"             # taxable + tax != gross
    NO_RULE_MATCH = "NO_RULE_MATCH"                          # no rule covers this category
    DUPLICATE_CLAIM = "DUPLICATE_CLAIM"                      # same invoice already seen
    CONTESTED_RULE = "CONTESTED_RULE"                        # rule is contested -> provisional, not auto-block
    OVERCLAIM_RISK = "OVERCLAIM_RISK"                        # dead credit that was already claimed in 3B


class FilingFrequency(str, Enum):
    MONTHLY = "monthly"
    QRMP = "QRMP"  # Quarterly Return, Monthly Payment — 2B can lag a full quarter


class ExtractionMethod(str, Enum):
    SYNTHETIC_TRUTH = "synthetic_truth"  # fixture-backed ground truth (demo default)
    VLM = "vlm"                          # real vision model (Claude), slot for later
    MANUAL = "manual"                    # human review queue


class PayoutStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    PAID = "paid"
    TIMEOUT = "timeout"
    RECONCILED = "reconciled"
    FAILED = "failed"


class RuleStatus(str, Enum):
    SETTLED = "settled"      # auto-applies
    CONTESTED = "contested"  # produces PROVISIONAL, never an automatic block
    PROPOSED = "proposed"    # awaiting CA approval, not live


class Tier(int, Enum):
    """Triage tier by expected value. Lower tier == cheaper to process."""

    TIER_0 = 0  # tax < ₹200          -> auto-approve, 0 API calls
    TIER_1 = 1  # ₹200–₹2,000         -> cached vendor data only
    TIER_2 = 2  # > ₹2,000            -> full pipeline, live GSP
    TIER_3 = 3  # > ₹2,000 & p < 0.5  -> intervene, draft vendor request
