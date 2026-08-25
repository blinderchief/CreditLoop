"""VLM extraction accuracy — the honest number.

Runs real Gemini vision on a sample of receipt images and scores each field
against the ground-truth invoice. This is what makes "extraction accuracy"
meaningful (in synthetic-truth mode it is 100% by construction). Capped at
settings.llm_extract_sample to stay inside the free-tier rate limit.
"""

from __future__ import annotations

import json
import random

from sqlmodel import select

from .config import settings
from .db import get_session
from .llm import client
from .log import banner, console, log, step
from .models import Claim, Invoice
from .tools.extract import extract_invoice

AMOUNT_TOL = 2.0


def _match_gstin(a, b) -> bool:
    return (a or None) == (b or None)


def _match_num(a, b) -> bool:
    return abs((a or 0) - (b or 0)) <= AMOUNT_TOL


def _match_buyer_kind(a, b) -> bool:
    # the decisive bit: is it billed to a company GSTIN or an individual?
    return bool(a) == bool(b)


def run_extraction_eval(sample: int | None = None, seed: int = 7) -> dict:
    step("VLM extraction accuracy (Gemini vision)")
    if not client.enabled:
        console.print("[loop.risk]No GEMINI_API_KEY — extraction stays synthetic-truth (100% by construction).[/]")
        return {"enabled": False, "note": "set CREDITLOOP_GEMINI_API_KEY to measure real extraction"}

    n = sample or settings.llm_extract_sample
    with get_session() as s:
        invoices = s.exec(select(Invoice)).all()
        claims = {c.claim_id: c for c in s.exec(select(Claim)).all()}
    rng = random.Random(seed)
    rng.shuffle(invoices)
    invoices = invoices[:n]

    fields = ["supplier_gstin", "invoice_no", "taxable_value", "tax_total", "buyer_kind"]
    hits = {f: 0 for f in fields}
    total = 0
    conf_sum = 0.0
    per_claim = []

    for inv in invoices:
        claim = claims.get(inv.claim_id)
        res = extract_invoice(inv, mode="vlm", receipt_path=claim.receipt_path if claim else None)
        if res.method.value != "vlm":
            continue  # fell back; don't count
        total += 1
        conf_sum += res.confidence
        r = {
            "supplier_gstin": _match_gstin(res.supplier_gstin, inv.supplier_gstin),
            "invoice_no": (res.invoice_no or None) == (inv.invoice_no or None),
            "taxable_value": _match_num(res.taxable_value, inv.taxable_value),
            "tax_total": _match_num(res.cgst + res.sgst + res.igst, inv.total_tax),
            "buyer_kind": _match_buyer_kind(res.buyer_gstin, inv.buyer_gstin),
        }
        for f in fields:
            hits[f] += 1 if r[f] else 0
        per_claim.append({"claim_id": inv.claim_id, "confidence": res.confidence, **r})

    acc = {f: round(hits[f] / total, 4) for f in fields} if total else {}
    report = {
        "enabled": True, "provider": "gemini", "model": client.model,
        "sample": total, "per_field_accuracy": acc,
        "mean_confidence": round(conf_sum / total, 3) if total else 0.0,
        "field_overall": round(sum(hits.values()) / (total * len(fields)), 4) if total else 0.0,
    }

    banner("Extraction accuracy", f"{total} receipts read by {client.model}")
    for f in fields:
        console.print(f"  {f:16s} {acc.get(f, 0)*100:5.1f}%")
    console.print(f"  mean confidence  {report['mean_confidence']}")

    out = settings.db_path.parent / "extraction_eval.json"
    out.write_text(json.dumps({**report, "per_claim": per_claim}, indent=2))
    return report


if __name__ == "__main__":
    run_extraction_eval()
