"""Layer 1 — the Ledger. The immutable join that does not exist in Indian
finance stacks today:

    claim -> invoice -> GSTIN -> 2B line -> payout -> book entry

Design rules:
  * Verdict and AuditEvent are APPEND-ONLY. Never update a row; always insert a
    new one. History is the product.
  * List/dict fields are stored as JSON columns (SQLite-friendly).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel

from .domain import (
    ClaimStatus,
    Decision,
    ExpenseCategory,
    ExtractionMethod,
    FilingFrequency,
    PayoutStatus,
)


def _uuid() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Claim(SQLModel, table=True):
    """The money-pipeline view of an expense: what the employee submitted."""

    claim_id: str = Field(default_factory=_uuid, primary_key=True)
    seq: int = Field(default=0, index=True)  # stable processing order within a batch
    employee_id: str = Field(index=True)
    employee_name: str = ""
    submitted_at: datetime = Field(default_factory=_now)
    amount_gross: float = 0.0          # what the employee paid, tax included
    category: ExpenseCategory = ExpenseCategory.MEALS
    description: str = ""              # free text, e.g. "Taj Mumbai 2 nights"
    status: ClaimStatus = Field(default=ClaimStatus.SUBMITTED, index=True)
    expected_value_score: float = 0.0  # tax_at_stake * p - cost_to_process
    tier: int = 0                      # triage tier assigned
    receipt_path: Optional[str] = None
    # Whether finance already claimed this ITC in a filed GSTR-3B. A dead credit
    # that was already claimed is an OVERCLAIM — money owed back with interest.
    already_claimed: bool = False
    claimed_days_ago: int = 0          # days since the wrong claim was filed (for interest)


class Invoice(SQLModel, table=True):
    """The tax-pipeline view: what the invoice actually says. One per claim."""

    invoice_id: str = Field(default_factory=_uuid, primary_key=True)
    claim_id: str = Field(foreign_key="claim.claim_id", index=True)
    supplier_gstin: Optional[str] = Field(default=None, index=True)
    supplier_name: str = ""
    invoice_no: Optional[str] = None
    invoice_date: Optional[str] = None  # ISO date string
    taxable_value: float = 0.0
    cgst: float = 0.0
    sgst: float = 0.0
    igst: float = 0.0
    buyer_gstin: Optional[str] = None   # who the invoice is billed to (the join test)
    buyer_name: str = ""
    extraction_confidence: float = 1.0
    extraction_method: ExtractionMethod = ExtractionMethod.SYNTHETIC_TRUTH
    # Place of supply: the first 2 digits of the supplier GSTIN ARE the state —
    # free, no API call. place_of_supply_state is where the supply legally
    # happened (per the category's POS rule). tax_type is CGST_SGST or IGST.
    supplier_state_code: Optional[str] = None
    place_of_supply_state: Optional[str] = None
    tax_type: str = "CGST_SGST"
    buyer_gstin_used: Optional[str] = None   # which of our registrations was quoted on the bill

    @property
    def total_tax(self) -> float:
        return round(self.cgst + self.sgst + self.igst, 2)


class Verdict(SQLModel, table=True):
    """APPEND-ONLY. The judgment: does this GST come back, under which rules?"""

    verdict_id: str = Field(default_factory=_uuid, primary_key=True)
    claim_id: str = Field(foreign_key="claim.claim_id", index=True)
    decision: Decision
    rule_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    rule_versions: list[int] = Field(default_factory=list, sa_column=Column(JSON))
    reason_code: Optional[str] = None            # set when decision is EXCEPTION/PROVISIONAL
    predicted_recoverable_p: float = 0.0         # calibrated probability (advisory)
    tax_at_stake: float = 0.0
    reasoning: str = ""                          # plain-language explanation
    provisional: bool = False                    # decided under degraded conditions
    created_at: datetime = Field(default_factory=_now, index=True)


class Vendor(SQLModel, table=True):
    """THE MOAT. Shared filing behaviour, learned from every claim, forever."""

    gstin: str = Field(primary_key=True)
    legal_name: str = ""
    filing_frequency: FilingFrequency = FilingFrequency.MONTHLY
    gstr1_filing_history: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    reliability_score: float = 0.5               # P(files a given invoice into 2B)
    active: bool = True                          # GSTIN registration status
    observation_count: int = 0
    last_refreshed_at: datetime = Field(default_factory=_now)


class TwoBLine(SQLModel, table=True):
    """A line from the government's GSTR-2B: the free supervised label.
    Every month reality tells us whether our prediction was right."""

    id: str = Field(default_factory=_uuid, primary_key=True)
    gstin: str = Field(index=True)
    invoice_no: str = Field(index=True)
    invoice_date: str = ""
    taxable_value: float = 0.0
    tax: float = 0.0
    return_period: str = ""                       # e.g. "072026"
    matched_claim_id: Optional[str] = Field(default=None, foreign_key="claim.claim_id")


class Payout(SQLModel, table=True):
    """Layer 3 money action. Idempotency key is mandatory — double-paying a
    reimbursement is the single worst bug this product can have."""

    payout_id: str = Field(default_factory=_uuid, primary_key=True)
    claim_id: str = Field(foreign_key="claim.claim_id", index=True)
    idempotency_key: str = Field(index=True)      # one per (claim), enforced in service
    razorpay_ref: Optional[str] = None
    amount: float = 0.0
    status: PayoutStatus = PayoutStatus.QUEUED
    rail: str = "IMPS"
    created_at: datetime = Field(default_factory=_now)
    settled_at: Optional[datetime] = None


class RuleProposal(SQLModel, table=True):
    """P1.2 — the review queue. The Change Detection Agent reads a GST source and
    drafts a structured rule diff here. NOTHING goes live unapproved — detection
    is autonomous, application is gated behind a human/CA."""

    id: str = Field(default_factory=_uuid, primary_key=True)
    created_at: datetime = Field(default_factory=_now, index=True)
    source_title: str = ""
    source_excerpt: str = ""
    source_url: str = ""
    target_rule_id: str = ""
    action: str = ""                 # e.g. "add_blocked_category"
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    rationale: str = ""
    status: str = Field(default="pending", index=True)   # pending | approved | rejected
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    changed_claim_count: Optional[int] = None


class AuditEvent(SQLModel, table=True):
    """APPEND-ONLY. Every verdict and money action is reconstructible from
    this log. If a CA cannot audit it, the product is unsellable."""

    id: str = Field(default_factory=_uuid, primary_key=True)
    claim_id: Optional[str] = Field(default=None, foreign_key="claim.claim_id", index=True)
    at: datetime = Field(default_factory=_now, index=True)
    actor: str = "agent"                          # agent | rule_engine | razorpay | ca
    action: str = ""                              # short verb, e.g. "verdict.emitted"
    detail: dict = Field(default_factory=dict, sa_column=Column(JSON))
