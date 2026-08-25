"""Step 3b — GSTR-2B reconciliation + the learning loop (PRD P0.8, section 8).

Every month the government's 2B statement tells us, for free, whether each
prediction was right. We:
  1. match each recoverable claim to its 2B line by (supplier_gstin, invoice_no)
  2. flag matched-but-mismatched amounts
  3. sort unmatched recoverable claims into QRMP-lag (expected) vs
     unconfirmed (chase the vendor)
  4. update each vendor's reliability_score from what actually filed — the
     supervised signal that compounds forever.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlmodel import select

from .db import get_session
from .domain import Decision, FilingFrequency, RECOVERABLE_DECISIONS
from .log import banner, console, log, rupees, step
from .models import AuditEvent, Claim, Invoice, TwoBLine, Vendor, Verdict

AMOUNT_TOL = 1.0  # rupees; larger gap => flagged mismatch


@dataclass
class ReconResult:
    total_2b_lines: int = 0
    matched_lines: int = 0
    predicted_recoverable: int = 0
    confirmed: int = 0
    pending_qrmp: int = 0
    unconfirmed: int = 0          # recoverable, monthly, but no 2B line -> chase
    amount_mismatches: list = field(default_factory=list)
    vendors_updated: int = 0

    @property
    def line_match_rate(self) -> float:
        return round(self.matched_lines / self.total_2b_lines, 4) if self.total_2b_lines else 0.0

    @property
    def recovery_confirmed_rate(self) -> float:
        return round(self.confirmed / self.predicted_recoverable, 4) if self.predicted_recoverable else 0.0

    def to_dict(self) -> dict:
        return {
            "total_2b_lines": self.total_2b_lines, "matched_lines": self.matched_lines,
            "line_match_rate": self.line_match_rate,
            "predicted_recoverable": self.predicted_recoverable, "confirmed": self.confirmed,
            "pending_qrmp": self.pending_qrmp, "unconfirmed": self.unconfirmed,
            "recovery_confirmed_rate": self.recovery_confirmed_rate,
            "amount_mismatches": self.amount_mismatches, "vendors_updated": self.vendors_updated,
        }


def _latest_verdict(session, claim_id: str) -> Verdict | None:
    return session.exec(
        select(Verdict).where(Verdict.claim_id == claim_id).order_by(Verdict.created_at.desc())
    ).first()


def reconcile(update_vendors: bool = True) -> ReconResult:
    step("STEP 3b — GSTR-2B reconciliation + vendor learning")
    r = ReconResult()

    with get_session() as s:
        claims = s.exec(select(Claim).order_by(Claim.seq)).all()
        invoices = {i.claim_id: i for i in s.exec(select(Invoice)).all()}
        vendors = {v.gstin: v for v in s.exec(select(Vendor)).all()}
        lines = s.exec(select(TwoBLine)).all()
        r.total_2b_lines = len(lines)

        # index 2B lines by (gstin, invoice_no)
        line_ix: dict[tuple, TwoBLine] = {(l.gstin, l.invoice_no): l for l in lines}

        # per-vendor observation tallies for the learning loop
        obs: dict[str, list[int]] = {}  # gstin -> [confirmed, attempts]

        for claim in claims:
            inv = invoices[claim.claim_id]
            v = _latest_verdict(s, claim.claim_id)
            key = (inv.supplier_gstin, inv.invoice_no)
            line = line_ix.get(key)
            vendor = vendors.get(inv.supplier_gstin)

            # (1) MATCHING — link every claim whose invoice appears in the 2B,
            # regardless of verdict. A blocked invoice can still be on the 2B;
            # matching it correctly is a matching-quality question.
            if line is not None and line.matched_claim_id is None:
                line.matched_claim_id = claim.claim_id
                s.add(line)
                r.matched_lines += 1
                gap = abs(inv.taxable_value - line.taxable_value)
                if gap > AMOUNT_TOL:
                    r.amount_mismatches.append({
                        "claim_id": claim.claim_id, "invoice_no": inv.invoice_no,
                        "invoice_taxable": inv.taxable_value, "twob_taxable": line.taxable_value,
                        "gap": round(gap, 2),
                    })
                    s.add(AuditEvent(claim_id=claim.claim_id, actor="agent",
                          action="recon.amount_mismatch",
                          detail={"invoice_taxable": inv.taxable_value,
                                  "twob_taxable": line.taxable_value, "gap": round(gap, 2)}))

            # (2) RECOVERY tracking + learning — only for claims we predicted
            # would recover.
            if v is None or v.decision not in RECOVERABLE_DECISIONS:
                continue
            r.predicted_recoverable += 1
            is_qrmp = (v.decision == Decision.PENDING_QRMP or
                       (vendor and vendor.filing_frequency == FilingFrequency.QRMP))
            if vendor and not is_qrmp:
                obs.setdefault(inv.supplier_gstin, [0, 0])[1] += 1

            if line is not None:
                r.confirmed += 1
                if vendor and not is_qrmp:
                    obs[inv.supplier_gstin][0] += 1
            elif is_qrmp:
                r.pending_qrmp += 1
            else:
                r.unconfirmed += 1
                s.add(AuditEvent(claim_id=claim.claim_id, actor="agent",
                      action="recon.unconfirmed",
                      detail={"reason": "no 2B line — supplier has not filed; chase",
                              "tax_at_stake": v.tax_at_stake}))

        # --- the learning loop: update vendor reliability from reality --------
        if update_vendors:
            for gstin, (confirmed, attempts) in obs.items():
                if attempts == 0:
                    continue
                vendor = vendors[gstin]
                observed = confirmed / attempts
                old = vendor.reliability_score
                vendor.reliability_score = round(0.6 * old + 0.4 * observed, 3)
                vendor.observation_count += attempts
                s.add(vendor)
                r.vendors_updated += 1

    _report(r)
    return r


def _report(r: ReconResult) -> None:
    banner("Reconciliation complete",
           f"{r.matched_lines}/{r.total_2b_lines} 2B lines matched")
    console.print(f"  2B line-match rate       : [loop.money]{r.line_match_rate*100:.1f}%[/] "
                  f"[loop.dim]({r.matched_lines}/{r.total_2b_lines})[/]")
    console.print(f"  Predicted recoverable    : {r.predicted_recoverable}")
    console.print(f"    ├ confirmed in 2B      : [loop.money]{r.confirmed}[/]")
    console.print(f"    ├ pending (QRMP lag)   : [loop.risk]{r.pending_qrmp}[/]")
    console.print(f"    └ unconfirmed (chase)  : [loop.loss]{r.unconfirmed}[/]")
    console.print(f"  Recovery-confirmed rate  : {r.recovery_confirmed_rate*100:.1f}%")
    console.print(f"  Amount mismatches flagged: [loop.risk]{len(r.amount_mismatches)}[/]")
    console.print(f"  Vendor scores updated    : {r.vendors_updated} (learned from 2B)")


if __name__ == "__main__":
    reconcile()
