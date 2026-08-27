"""The Rule Registry (PRD section 7).

Every rule is a *versioned record, not code*. The engine holds the predicate
implementations (keyed by `check`), the registry holds the law: verdict,
citation, version, effective dates, and settled/contested/proposed status.

Because every verdict cites `rule_id + version`, when the law moves we can
re-run history and say exactly which past claims are affected. No existing
Indian tool can do that.

The default registry is seeded to data/rule_registry.json on first load so a
reviewer can read and diff the rules as plain data.
"""

from __future__ import annotations

import json
from typing import Optional

from pydantic import BaseModel

from .config import settings
from .domain import RuleStatus

REGISTRY_PATH = settings.db_path.parent / "rule_registry.json"


class Rule(BaseModel):
    rule_id: str
    version: int
    check: str                       # predicate key implemented in engine.py
    verdict: str                     # Decision or "EXCEPTION:<REASON>" the rule emits on failure
    effective_from: str
    effective_to: Optional[str] = None
    condition: str = ""              # human-readable condition text
    exception: str = ""              # carve-out text
    source_citation: str = ""
    source_url: str = ""
    approved_by: str = ""
    status: RuleStatus = RuleStatus.SETTLED
    confidence: str = "settled"
    place_of_supply_rule: Optional[str] = None   # LOCATION_OF_SUPPLY | LOCATION_OF_RECIPIENT


# --- The seeded law -------------------------------------------------------
# Order is priority order: the engine applies them top-to-bottom and stops at
# the first rule that does not pass.

DEFAULT_RULES: list[Rule] = [
    Rule(
        rule_id="EXTRACTION_CONFIDENCE", version=1, check="extraction_confident",
        verdict="EXCEPTION:LOW_EXTRACTION_CONFIDENCE",
        condition="extraction_confidence >= 0.60",
        source_citation="Internal control — do not guess a GSTIN",
        approved_by="ca_review_2026_03_11", effective_from="2026-01-01",
    ),
    Rule(
        rule_id="GSTIN_PRESENT", version=1, check="supplier_gstin_present",
        verdict="EXCEPTION:MISSING_GSTIN",
        condition="supplier_gstin is present",
        source_citation="CGST Act s.16(2)(a) — a tax invoice is required",
        source_url="https://cleartax.in/s/section-175-of-cgst-act",
        approved_by="ca_review_2026_03_11", effective_from="2026-01-01",
    ),
    Rule(
        rule_id="GSTIN_VALID", version=1, check="supplier_gstin_valid",
        verdict="EXCEPTION:INVALID_GSTIN",
        condition="supplier_gstin passes the 15-char base-36 checksum",
        source_citation="GSTN GSTIN format specification",
        approved_by="ca_review_2026_03_11", effective_from="2026-01-01",
    ),
    Rule(
        rule_id="GSTIN_ACTIVE", version=1, check="supplier_gstin_active",
        verdict="EXCEPTION:GSTIN_NOT_ACTIVE",
        condition="supplier registration is Active per GSP",
        source_citation="CGST Act s.16(2) — supplier must be a registered person",
        approved_by="ca_review_2026_03_11", effective_from="2026-01-01",
    ),
    Rule(
        rule_id="TAX_ARITHMETIC", version=1, check="arithmetic_consistent",
        verdict="EXCEPTION:ARITHMETIC_MISMATCH",
        condition="abs(taxable + cgst + sgst + igst - amount_gross) <= tolerance",
        source_citation="Internal control — invoice must foot",
        approved_by="ca_review_2026_03_11", effective_from="2026-01-01",
    ),
    Rule(
        rule_id="DUPLICATE_INVOICE", version=1, check="not_duplicate",
        verdict="EXCEPTION:DUPLICATE_CLAIM",
        condition="(supplier_gstin, invoice_no) not previously claimed",
        source_citation="Internal control — ITC once per invoice",
        approved_by="ca_review_2026_03_11", effective_from="2026-01-01",
    ),
    Rule(
        rule_id="SEC_16_2_BUYER_ENTITY", version=2, check="billed_to_company",
        verdict="UNRECOVERABLE_WRONG_ENTITY",
        condition="buyer_gstin == company_gstin",
        exception="none — an invoice in an individual's name is never creditable to the company",
        source_citation="CGST Act s.16(2)(a) — recipient must hold the tax invoice",
        source_url="https://cleartax.in/s/section-175-of-cgst-act",
        approved_by="ca_review_2026_03_11", effective_from="2025-07-01",
    ),
    Rule(
        rule_id="SEC_17_5_B_FOOD_BEVERAGE", version=4, check="not_blocked_17_5",
        verdict="BLOCKED_17_5",
        condition="expense_category NOT IN ['meals','food','beverage','outdoor_catering']",
        exception="unless the employer is statutorily obligated to provide it",
        source_citation="CGST Act s.17(5)(b)",
        source_url="https://cleartax.in/s/section-175-of-cgst-act",
        approved_by="ca_review_2026_03_11", effective_from="2025-07-01",
    ),
    Rule(
        rule_id="POS_STATE_REGISTERED", version=1, check="registered_in_pos_state",
        verdict="STATE_TRAPPED",
        condition="place-of-supply state IN company's registered states",
        exception="only supply-located categories (hotel, cab, meals, coworking) can be trapped",
        source_citation="Section 12(3)/12(9), IGST Act 2017; CBIC clarification 2019; multiple AAR rulings",
        source_url="https://cbic-gst.gov.in",
        place_of_supply_rule="LOCATION_OF_SUPPLY",
        approved_by="ca_review_2026_03_11", effective_from="2017-07-01",
    ),
    Rule(
        rule_id="POS_CORRECT_GSTIN", version=1, check="correct_state_gstin",
        verdict="WRONG_GSTIN_USED",
        condition="buyer GSTIN's state == place-of-supply state",
        exception="fixable — reissue against the correct state's registration",
        source_citation="Section 16(2), CGST Act — credit belongs to the registration that bore the tax",
        place_of_supply_rule="LOCATION_OF_SUPPLY",
        approved_by="ca_review_2026_03_11", effective_from="2017-07-01",
    ),
    Rule(
        rule_id="QRMP_TIMING", version=1, check="supplier_files_monthly",
        verdict="PENDING_QRMP",
        condition="supplier filing_frequency == 'monthly'",
        exception="QRMP suppliers file quarterly; 2B lags up to a quarter — not unrecoverable",
        source_citation="Rule 61 / QRMP scheme; IMS mechanics",
        source_url="https://treelife.in/calendar/gst-compliance-calendar/",
        approved_by="ca_review_2026_03_11", effective_from="2026-01-01",
    ),
    # A PROPOSED rule — sits in the review queue, NOT applied. Demonstrates the
    # Dynamic Compliance Engine's human-approval gate.
    Rule(
        rule_id="ADVISORY_IMS_PENDING_WINDOW", version=1, check="noop",
        verdict="PROVISIONAL",
        condition="invoice pending in IMS beyond the acceptance window",
        source_citation="Draft — GSTN advisory on IMS pending-invoice handling",
        approved_by="", status=RuleStatus.PROPOSED, confidence="proposed",
        effective_from="2026-09-01",
    ),
]


class RuleRegistry:
    def __init__(self, rules: list[Rule]):
        self.rules = rules

    @property
    def live_rules(self) -> list[Rule]:
        """Rules that actually apply: settled or contested, never proposed."""
        return [r for r in self.rules if r.status != RuleStatus.PROPOSED]

    def get(self, rule_id: str) -> Optional[Rule]:
        for r in self.rules:
            if r.rule_id == rule_id:
                return r
        return None

    def bump(self, rule_id: str, **changes) -> Rule:
        """Create a new version of a rule (append-only versioning)."""
        old = self.get(rule_id)
        assert old is not None, f"unknown rule {rule_id}"
        data = old.model_dump()
        data.update(changes)
        data["version"] = old.version + 1
        new = Rule(**data)
        self.rules = [r for r in self.rules if r.rule_id != rule_id] + [new]
        return new

    def save(self, path=REGISTRY_PATH) -> None:
        path.write_text(json.dumps([r.model_dump() for r in self.rules], indent=2, default=str))


def load_registry() -> RuleRegistry:
    if REGISTRY_PATH.exists():
        data = json.loads(REGISTRY_PATH.read_text())
        return RuleRegistry([Rule(**r) for r in data])
    reg = RuleRegistry(list(DEFAULT_RULES))
    reg.save()
    return reg


def reset_registry() -> "RuleRegistry":
    """Restore the seeded law (baseline versions). Makes the rule-change demo
    repeatable — every run starts from the same registry."""
    global registry
    registry = RuleRegistry([r.model_copy() for r in DEFAULT_RULES])
    registry.save()
    return registry


registry = load_registry()
