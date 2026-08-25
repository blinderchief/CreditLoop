"""End-to-end demo runner — the whole loop in one command.

    synthetic data -> judgment -> payouts -> 2B reconciliation -> metrics

This is what `make demo` calls. Pass --fail-payout to inject a payout timeout
and watch it reconcile; pass --gsp-down to run judgment with the GSP offline and
watch verdicts degrade to PROVISIONAL without ever blocking a payout.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from .actions import run_payouts
from .log import console, step
from .metrics import compute_metrics
from .pipeline import run_batch
from .queries import RUN_SUMMARY_PATH
from .reconcile import reconcile
from .synthetic import generate
from .tools.gsp import GspClient
from .tools.razorpay import RazorpayClient


def run_full(fail_payout: bool = False, gsp_down: bool = False, regenerate: bool = True) -> dict:
    """Run the whole loop and persist a consolidated run summary. Reusable by
    both the CLI demo and the API's POST /api/run."""
    if regenerate:
        generate()

    gsp = GspClient(available=not gsp_down)
    pipeline_stats = run_batch(gsp=gsp)

    payout_stats = run_payouts(razorpay=RazorpayClient(), force_timeout_on_first=fail_payout)
    recon = reconcile()
    metrics = compute_metrics(pipeline_stats=pipeline_stats)

    summary = {
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "failure_flags": {"fail_payout": fail_payout, "gsp_down": gsp_down},
        "pipeline": pipeline_stats,
        "payouts": payout_stats,
        "reconcile": recon.to_dict(),
        "metrics": {k: metrics[k] for k in metrics if k != "reliability_curve"},
    }
    RUN_SUMMARY_PATH.write_text(json.dumps(summary, indent=2, default=str))

    step("DEMO COMPLETE")
    console.print("[loop.money]● The loop closed: claim → invoice → GSTIN → 2B → payout → book.[/]")
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description="CreditLoop end-to-end demo")
    ap.add_argument("--fail-payout", action="store_true", help="inject one payout timeout")
    ap.add_argument("--gsp-down", action="store_true", help="run judgment with the GSP offline")
    ap.add_argument("--skip-gen", action="store_true", help="reuse existing data")
    args = ap.parse_args()
    run_full(fail_payout=args.fail_payout, gsp_down=args.gsp_down, regenerate=not args.skip_gen)


if __name__ == "__main__":
    main()
