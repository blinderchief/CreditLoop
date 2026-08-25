"""extract_invoice — receipt image -> structured, schema-valid fields.

A genuinely good use of a VLM (crumpled thermal paper, Hindi text, a GSTIN
printed sideways). But an LLM never decides eligibility — it only reads.

Modes:
  * synthetic_truth (default) — returns the ground-truth invoice already in the
    ledger, with its generated confidence. Fast, offline, deterministic.
  * vlm — real Gemini vision. Schema-validated; on malformed output we retry
    once then fall back to synthetic-truth so the deterministic path never
    breaks (PRD failure mode). Used by the extraction eval + high-value claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..config import settings
from ..domain import ExtractionMethod
from ..log import log
from ..models import Invoice


@dataclass
class ExtractionResult:
    supplier_gstin: Optional[str]
    supplier_name: str
    invoice_no: Optional[str]
    invoice_date: Optional[str]
    taxable_value: float
    cgst: float
    sgst: float
    igst: float
    buyer_gstin: Optional[str]
    buyer_name: str
    confidence: float
    method: ExtractionMethod


def _from_invoice(invoice: Invoice) -> ExtractionResult:
    return ExtractionResult(
        supplier_gstin=invoice.supplier_gstin, supplier_name=invoice.supplier_name,
        invoice_no=invoice.invoice_no, invoice_date=invoice.invoice_date,
        taxable_value=invoice.taxable_value, cgst=invoice.cgst, sgst=invoice.sgst,
        igst=invoice.igst, buyer_gstin=invoice.buyer_gstin, buyer_name=invoice.buyer_name,
        confidence=invoice.extraction_confidence, method=ExtractionMethod.SYNTHETIC_TRUTH,
    )


def _num(x, default=0.0) -> float:
    try:
        return round(float(x), 2)
    except (TypeError, ValueError):
        return default


def _validate(raw: dict) -> ExtractionResult:
    """Coerce the model's JSON into a schema-valid ExtractionResult."""
    def clean_gstin(v):
        if not v or not isinstance(v, str):
            return None
        v = v.strip().upper()
        return v if len(v) == 15 else (v or None)

    return ExtractionResult(
        supplier_gstin=clean_gstin(raw.get("supplier_gstin")),
        supplier_name=str(raw.get("supplier_name") or ""),
        invoice_no=(str(raw["invoice_no"]) if raw.get("invoice_no") else None),
        invoice_date=(str(raw["invoice_date"]) if raw.get("invoice_date") else None),
        taxable_value=_num(raw.get("taxable_value")),
        cgst=_num(raw.get("cgst")), sgst=_num(raw.get("sgst")), igst=_num(raw.get("igst")),
        buyer_gstin=clean_gstin(raw.get("buyer_gstin")),
        buyer_name=str(raw.get("buyer_name") or ""),
        confidence=max(0.0, min(1.0, _num(raw.get("confidence"), 0.5))),
        method=ExtractionMethod.VLM,
    )


def _receipt_abs_path(invoice: Invoice, receipt_path: Optional[str]) -> Optional[Path]:
    rel = receipt_path or f"receipts/{invoice.claim_id}.png"
    p = settings.db_path.parent / rel
    return p if p.exists() else None


def extract_invoice(invoice: Invoice, mode: str = "synthetic_truth",
                    receipt_path: Optional[str] = None) -> ExtractionResult:
    if mode != "vlm":
        return _from_invoice(invoice)

    # --- real VLM path ---
    from ..llm import client, LLMUnavailable
    if not client.enabled:
        return _from_invoice(invoice)
    path = _receipt_abs_path(invoice, receipt_path)
    if path is None:
        return _from_invoice(invoice)

    for attempt in range(2):  # one retry on malformed output
        try:
            raw = client.extract_receipt(str(path))
            return _validate(raw)
        except LLMUnavailable as e:
            log.warning("[loop.risk]VLM extract attempt %d failed: %s[/]", attempt + 1, e)
    log.warning("[loop.risk]VLM extraction gave up for %s — falling back to deterministic path[/]",
                invoice.claim_id)
    return _from_invoice(invoice)
