"""The agent loop (Layer 2 -> Layer 1 write).

For each claim:  extract -> triage band -> (maybe) GSP validate -> deterministic
verdict -> recoverability prediction -> persist verdict + audit event.

The expensive calls (live GSP) are spent ONLY on claims where real money is at
stake. Cheap claims run the free deterministic checks and are auto-approved.
That gap — free checks everywhere, paid checks almost nowhere — is the whole
efficiency argument.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from sqlmodel import select

from .config import settings
from .db import get_session
from .domain import (
    ClaimStatus,
    Decision,
    FilingFrequency,
    RECOVERABLE_DECISIONS,
)
from .engine import EvalContext, VerdictResult, evaluate
from .log import banner, console, log, rupees, step
from .models import AuditEvent, Claim, Invoice, Vendor, Verdict
from .predict import predict_recoverability
from .tools.extract import extract_invoice
from .tools.gsp import GspClient, GspUnavailable
from .triage import TriageDecision, triage


@dataclass
class ProcessResult:
    claim: Claim
    verdict: Verdict
    triage: TriageDecision


def _status_for(decision: Decision, td: TriageDecision) -> ClaimStatus:
    # Verdict-time status only. Payout + vendor intervention are Layer-3 actions
    # applied in the next step.
    if decision == Decision.EXCEPTION:
        return ClaimStatus.EXCEPTION
    return ClaimStatus.JUDGED


def process_claim(session, claim: Claim, invoice: Invoice, gsp: GspClient,
                  seen_keys: set, narrate: bool = False) -> ProcessResult:
    ext = extract_invoice(invoice, mode="synthetic_truth")
    tax = round(ext.cgst + ext.sgst + ext.igst, 2)

    tier0 = tax < settings.tier0_max_tax          # < ₹200: spend truly zero effort
    high_value = tax >= settings.tier1_max_tax    # >= ₹2,000: warrants a live GSP call
    vendor_active = filing_freq = reliability = None
    gsp_unverified = False

    # Our OWN vendor table is the moat — reading reliability + filing frequency
    # from it is FREE (no external call). Available for every tier above tier_0.
    # This is the PRD's "tier_1: cached vendor data only".
    if not tier0 and ext.supplier_gstin:
        vrow = session.exec(select(Vendor).where(Vendor.gstin == ext.supplier_gstin)).first()
        if vrow is not None:
            reliability = vrow.reliability_score
            filing_freq = vrow.filing_frequency.value

    # A LIVE external GSP call validates registration status (freshness matters)
    # and is spent only on high-value claims.
    if high_value:
        try:
            info = gsp.lookup(ext.supplier_gstin)
            vendor_active = info.active
            filing_freq = info.filing_frequency or filing_freq
            if info.reliability_score is not None:
                reliability = info.reliability_score
        except GspUnavailable:
            info = gsp.cached(ext.supplier_gstin)
            if info is not None:
                vendor_active = info.active
            else:
                gsp_unverified = True   # degrade to PROVISIONAL, never block payout

    ctx = EvalContext(
        amount_gross=claim.amount_gross, category=claim.category,
        taxable_value=ext.taxable_value, cgst=ext.cgst, sgst=ext.sgst, igst=ext.igst,
        supplier_gstin=ext.supplier_gstin, buyer_gstin=ext.buyer_gstin, invoice_no=ext.invoice_no,
        extraction_confidence=ext.confidence, vendor_active=vendor_active,
        vendor_filing_frequency=filing_freq, seen_keys=seen_keys, gsp_unverified=gsp_unverified,
    )
    vr: VerdictResult = evaluate(ctx)

    rel_for_p = reliability if reliability is not None else 0.7
    ff = FilingFrequency(filing_freq) if filing_freq else None
    p = predict_recoverability(vr.decision, rel_for_p, ff, claim.category)

    td = triage(tax, p)

    verdict = Verdict(
        claim_id=claim.claim_id, decision=vr.decision, rule_ids=vr.rule_ids,
        rule_versions=vr.rule_versions, reason_code=vr.reason_code,
        predicted_recoverable_p=p, tax_at_stake=tax, reasoning=vr.reasoning,
        provisional=vr.provisional,
    )
    session.add(verdict)

    claim.tier = td.tier.value
    claim.expected_value_score = td.expected_value
    claim.status = _status_for(vr.decision, td)
    session.add(claim)

    session.add(AuditEvent(
        claim_id=claim.claim_id, actor="rule_engine", action="verdict.emitted",
        detail={
            "decision": vr.decision.value, "reason_code": vr.reason_code,
            "rules": [f"{r} v{v}" for r, v in zip(vr.rule_ids, vr.rule_versions)],
            "tax_at_stake": tax, "p_recoverable": p, "tier": td.tier.value,
            "expected_value": td.expected_value, "provisional": vr.provisional,
        },
    ))

    seen_keys.add((ext.supplier_gstin, ext.invoice_no))

    if narrate:
        _narrate(claim, verdict, td)
    return ProcessResult(claim=claim, verdict=verdict, triage=td)


_DECISION_STYLE = {
    Decision.RECOVERABLE: "loop.money", Decision.PROVISIONAL: "loop.risk",
    Decision.PENDING_QRMP: "loop.risk", Decision.UNRECOVERABLE_WRONG_ENTITY: "loop.loss",
    Decision.BLOCKED_17_5: "loop.loss", Decision.EXCEPTION: "loop.risk",
}


def _narrate(claim: Claim, verdict: Verdict, td: TriageDecision) -> None:
    style = _DECISION_STYLE.get(verdict.decision, "loop.dim")
    console.print(
        f"  [loop.tier]T{td.tier.value}[/] {claim.employee_name:16s} "
        f"{claim.category.value:9s} {rupees(claim.amount_gross):>11} "
        f"tax {rupees(verdict.tax_at_stake):>9} "
        f"→ [{style}]{verdict.decision.value}[/] "
        f"p={verdict.predicted_recoverable_p:.2f}"
    )
    console.print(f"      [loop.dim]{verdict.reasoning}[/]")


def run_batch(gsp: GspClient | None = None, narrate_n: int = 6) -> dict:
    gsp = gsp or GspClient()
    step("STEP 2 — Judgment (extract → rules → predict → triage)")
    t0 = time.perf_counter()
    results: list[ProcessResult] = []
    with get_session() as s:
        claims = s.exec(select(Claim).order_by(Claim.seq)).all()
        invoices = {i.claim_id: i for i in s.exec(select(Invoice)).all()}
        seen: set = set()
        console.print(f"[loop.dim]Processing {len(claims)} claims (narrating first {narrate_n})…[/]\n")
        for i, claim in enumerate(claims):
            results.append(process_claim(s, claim, invoices[claim.claim_id], gsp, seen,
                                         narrate=i < narrate_n))
    elapsed = time.perf_counter() - t0
    stats = _aggregate(results, gsp, elapsed)
    _report(stats, gsp)
    return stats


def _aggregate(results: list[ProcessResult], gsp: GspClient, elapsed: float) -> dict:
    from collections import Counter

    decisions = Counter(r.verdict.decision.value for r in results)
    tiers = Counter(r.triage.tier.value for r in results)

    recovered = sum(r.verdict.tax_at_stake for r in results
                    if r.verdict.decision in RECOVERABLE_DECISIONS)
    lost = sum(r.verdict.tax_at_stake for r in results
               if r.verdict.decision == Decision.UNRECOVERABLE_WRONG_ENTITY)
    blocked = sum(r.verdict.tax_at_stake for r in results
                  if r.verdict.decision == Decision.BLOCKED_17_5)
    # "At risk" = eligible ITC we predict probably won't file (chase these).
    at_risk = sum(r.verdict.tax_at_stake for r in results
                  if r.verdict.decision in RECOVERABLE_DECISIONS
                  and r.verdict.predicted_recoverable_p < settings.intervene_p_below)
    # Wrong-entity invoices are lost today but fixable via a reissue request.
    reissue = [r for r in results if r.verdict.decision == Decision.UNRECOVERABLE_WRONG_ENTITY]
    exceptions = [r for r in results if r.verdict.decision == Decision.EXCEPTION]

    n = len(results)
    return {
        "claims": n,
        "decisions": dict(decisions),
        "tiers": {f"tier_{k}": tiers.get(k, 0) for k in range(4)},
        "recovered": round(recovered, 2),
        "lost_wrong_entity": round(lost, 2),
        "blocked_17_5": round(blocked, 2),
        "at_risk_chase": round(at_risk, 2),
        "reissue_candidates": len(reissue),
        "exceptions": len(exceptions),
        "gsp": gsp.stats(),
        "gsp_calls_per_claim": round(gsp.stats()["live_calls"] / n, 3) if n else 0,
        "elapsed_s": round(elapsed, 3),
        "claims_per_min": round(n / elapsed * 60, 1) if elapsed else 0,
    }


def _report(stats: dict, gsp: GspClient) -> None:
    from rich.table import Table

    banner("Judgment complete", f"{stats['claims']} claims in {stats['elapsed_s']}s "
                                f"({stats['claims_per_min']} claims/min)")

    td = Table(title="Verdicts", show_edge=False, title_style="loop.step")
    td.add_column("decision"); td.add_column("count", justify="right")
    for k, v in sorted(stats["decisions"].items(), key=lambda x: -x[1]):
        td.add_row(k, str(v))
    console.print(td)

    tt = Table(title="Triage tiers (cost concentration)", show_edge=False, title_style="loop.step")
    tt.add_column("tier"); tt.add_column("count", justify="right"); tt.add_column("meaning")
    meanings = {"tier_0": "<₹200 · auto-approve · 0 calls", "tier_1": "₹200–2k · cached only",
                "tier_2": ">₹2k · live GSP", "tier_3": ">₹2k & p<0.5 · intervene"}
    for k in ["tier_0", "tier_1", "tier_2", "tier_3"]:
        tt.add_row(k, str(stats["tiers"][k]), meanings[k])
    console.print(tt)

    g = stats["gsp"]
    console.print(f"\n  GST recoverable (eligible) : [loop.money]{rupees(stats['recovered'])}[/]")
    console.print(f"  Lost — wrong entity        : [loop.loss]{rupees(stats['lost_wrong_entity'])}[/] "
                  f"[loop.dim]({stats['reissue_candidates']} fixable via reissue)[/]")
    console.print(f"  Blocked u/s 17(5)          : [loop.loss]{rupees(stats['blocked_17_5'])}[/]")
    console.print(f"  At risk — chase vendor     : [loop.risk]{rupees(stats['at_risk_chase'])}[/]")
    console.print(f"  Exceptions (refused)       : [loop.risk]{stats['exceptions']}[/]")
    console.print(
        f"\n  [loop.step]Efficiency:[/] {g['live_calls']} live GSP calls for "
        f"{stats['claims']} claims = [loop.money]{stats['gsp_calls_per_claim']} calls/claim[/] "
        f"({g['cache_hits']} cache hits)."
    )


if __name__ == "__main__":
    run_batch()
