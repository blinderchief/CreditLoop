"""P1.1 — draft the vendor reissue / filing request.

The intervention that closes the loop while it's still fixable: ask the vendor
to reissue the invoice in the company's GSTIN (wrong-entity), or to file their
GSTR-1 for an invoice we predict won't appear (unreliable filer).

LLM-drafted (Gemini) for natural Hinglish + English, with a solid template
fallback so it works with no key.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import settings
from .domain import Decision
from .llm import client, LLMUnavailable
from .log import log


@dataclass
class Draft:
    kind: str          # "reissue" | "nudge_filing"
    subject: str
    english: str
    hinglish: str
    source: str        # "gemini" | "template"


def _kind_for(decision: str) -> str:
    return "reissue" if decision == Decision.UNRECOVERABLE_WRONG_ENTITY.value else "nudge_filing"


def _template(kind: str, ctx: dict) -> Draft:
    if kind == "reissue":
        subject = f"Request: reissue invoice {ctx['invoice_no']} in company GSTIN"
        english = (
            f"Dear {ctx['supplier_name']},\n\n"
            f"Invoice {ctx['invoice_no']} dated {ctx['invoice_date']} (₹{ctx['amount']:.0f}) was billed "
            f"to an individual. Kindly reissue it in our company's name so we can claim input tax credit:\n\n"
            f"  {ctx['company_name']}\n  GSTIN: {ctx['company_gstin']}\n\n"
            f"₹{ctx['tax']:.0f} of GST depends on this correction. Please share the revised invoice at your "
            f"earliest convenience.\n\nThank you,\nAccounts, {ctx['company_name']}"
        )
        hinglish = (
            f"Namaste {ctx['supplier_name']},\n\n"
            f"Invoice {ctx['invoice_no']} ({ctx['invoice_date']}, ₹{ctx['amount']:.0f}) individual ke naam pe "
            f"bani hai. Please ise humari company ke naam/GSTIN pe reissue kar dijiye taaki hum ITC claim kar sakein:\n\n"
            f"  {ctx['company_name']}\n  GSTIN: {ctx['company_gstin']}\n\n"
            f"Is correction pe ₹{ctx['tax']:.0f} ka GST depend karta hai. Revised invoice jaldi bhej dijiye.\n\n"
            f"Dhanyavaad,\nAccounts, {ctx['company_name']}"
        )
    else:
        subject = f"Reminder: please file GSTR-1 for invoice {ctx['invoice_no']}"
        english = (
            f"Dear {ctx['supplier_name']},\n\n"
            f"We have not yet seen invoice {ctx['invoice_no']} ({ctx['invoice_date']}, ₹{ctx['amount']:.0f}) in "
            f"our GSTR-2B. Please ensure it is reported in your GSTR-1 so we can claim the ₹{ctx['tax']:.0f} input "
            f"tax credit.\n\nThank you,\nAccounts, {ctx['company_name']}"
        )
        hinglish = (
            f"Namaste {ctx['supplier_name']},\n\n"
            f"Invoice {ctx['invoice_no']} ({ctx['invoice_date']}, ₹{ctx['amount']:.0f}) abhi tak humare GSTR-2B "
            f"mein nahi aaya. Please apni GSTR-1 mein report kar dijiye taaki hum ₹{ctx['tax']:.0f} ka ITC le "
            f"sakein.\n\nDhanyavaad,\nAccounts, {ctx['company_name']}"
        )
    return Draft(kind=kind, subject=subject, english=english, hinglish=hinglish, source="template")


def draft_request(claim, invoice, verdict) -> Draft:
    ctx = {
        "supplier_name": invoice.supplier_name, "invoice_no": invoice.invoice_no or "—",
        "invoice_date": invoice.invoice_date or "—", "amount": claim.amount_gross,
        "tax": verdict.tax_at_stake, "company_name": settings.company_name,
        "company_gstin": settings.company_gstin,
    }
    kind = _kind_for(verdict.decision.value if hasattr(verdict.decision, "value") else verdict.decision)

    if not client.enabled:
        return _template(kind, ctx)

    goal = ("ask them to REISSUE the invoice in the company's GSTIN so ITC can be claimed"
            if kind == "reissue" else
            "politely remind them to file their GSTR-1 so this invoice appears in our GSTR-2B")
    prompt = (
        f"Write a short, polite vendor message for an Indian company's accounts team. Goal: {goal}.\n"
        f"Vendor: {ctx['supplier_name']}. Invoice {ctx['invoice_no']} dated {ctx['invoice_date']}, "
        f"amount ₹{ctx['amount']:.0f}, GST at stake ₹{ctx['tax']:.0f}. "
        f"Company: {ctx['company_name']}, GSTIN {ctx['company_gstin']}.\n"
        "Return strict JSON: {\"subject\": str, \"english\": str, \"hinglish\": str}. "
        "Keep each body under 90 words, warm and concrete. Hinglish = natural Hindi-English mix in Latin script."
    )
    try:
        import json
        raw = json.loads(client.complete(prompt, json_out=True, temperature=0.4))
        return Draft(kind=kind, subject=raw.get("subject", "").strip() or _template(kind, ctx).subject,
                     english=raw.get("english", "").strip(), hinglish=raw.get("hinglish", "").strip(),
                     source="gemini")
    except (LLMUnavailable, ValueError, KeyError) as e:
        log.warning("[loop.risk]Draft via Gemini failed (%s) — using template[/]", e)
        return _template(kind, ctx)
