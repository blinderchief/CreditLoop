"""Layer 3 — money actions. Runs payouts across the judged batch.

Payment policy (deliberate, defensible, demoable):
  * A tax problem is the COMPANY's problem, not the employee's — so a claim with
    a wrong-entity or blocked verdict is still PAID on time. (PRD user story 5.)
  * But two reason codes affect the legitimacy/amount of the reimbursement
    itself, so they HOLD payment for human review:
        DUPLICATE_CLAIM     — never pay the same invoice twice
        ARITHMETIC_MISMATCH — the amount doesn't foot; verify before paying
Every payout is idempotent (see tools/razorpay.py), so this is safe to re-run.
"""

from __future__ import annotations

from sqlmodel import select

from .db import get_session
from .domain import ClaimStatus, PayoutStatus, ReasonCode
from .log import banner, console, log, rupees, step
from .models import Claim, Payout, Verdict
from .tools.razorpay import RazorpayClient, execute_payout, reconcile_payout

HOLD_REASONS = {ReasonCode.DUPLICATE_CLAIM.value, ReasonCode.ARITHMETIC_MISMATCH.value}


def _latest_verdict(session, claim_id: str) -> Verdict | None:
    return session.exec(
        select(Verdict).where(Verdict.claim_id == claim_id).order_by(Verdict.created_at.desc())
    ).first()


def run_payouts(razorpay: RazorpayClient | None = None, force_timeout_on_first: bool = False) -> dict:
    """Pay every judged claim except those held for review. Demonstrates a
    forced timeout + reconciliation when force_timeout_on_first is set."""
    razorpay = razorpay or RazorpayClient()
    step("STEP 3a — Payouts (idempotent, timeout-safe)")

    paid = held = reconciled = 0
    total_paid = 0.0
    timed_out_claim: str | None = None

    with get_session() as s:
        claims = s.exec(select(Claim).order_by(Claim.seq)).all()
        first = True
        for claim in claims:
            v = _latest_verdict(s, claim.claim_id)
            if v and v.reason_code in HOLD_REASONS:
                claim.status = ClaimStatus.EXCEPTION
                s.add(claim)
                held += 1
                continue

            if force_timeout_on_first and first:
                razorpay.fail_timeout = True
                first = False

            payout = execute_payout(s, claim, razorpay)
            if payout.status == PayoutStatus.TIMEOUT:
                timed_out_claim = claim.claim_id
            else:
                if claim.status != ClaimStatus.EXCEPTION:
                    claim.status = ClaimStatus.PAID
                    s.add(claim)
                paid += 1
                total_paid += payout.amount

        # Recover the injected timeout: poll + settle with the same key.
        if timed_out_claim:
            payout = s.exec(select(Payout).where(Payout.claim_id == timed_out_claim)).first()
            reconcile_payout(s, payout, razorpay)
            claim = s.get(Claim, timed_out_claim)
            claim.status = ClaimStatus.PAID
            s.add(claim)
            reconciled = 1
            paid += 1

    stats = {
        "paid": paid, "held_for_review": held, "reconciled_after_timeout": reconciled,
        "total_paid": round(total_paid, 2), "rail_calls": razorpay.calls,
        "timeouts": razorpay.timeouts,
    }
    banner("Payouts complete",
           f"{paid} paid · {held} held · {reconciled} reconciled after timeout")
    console.print(f"  Total disbursed : [loop.money]{rupees(stats['total_paid'])}[/]")
    console.print(f"  Held for review : [loop.risk]{held}[/] (duplicate / arithmetic)")
    if reconciled:
        console.print(f"  [loop.money]Recovered 1 timed-out payout via reconciliation "
                      f"(idempotent, no double-pay).[/]")
    return stats
