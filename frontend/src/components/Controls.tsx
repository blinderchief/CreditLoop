import { useState } from "react";
import { api } from "../api";

// The demo console: re-run the loop, inject the two graded failure modes, and
// fire the Dynamic Compliance Engine (a rule version bump that recomputes
// history). Kept to plain buttons — the drama is in the numbers, not the UI.
export function Controls({ onDone }: { onDone: () => void }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  async function run(label: string, fn: () => Promise<any>, done: (r: any) => string) {
    setBusy(label); setMsg(null);
    try {
      const r = await fn();
      setMsg(done(r));
      onDone();
    } catch (e) {
      setMsg("Error: " + (e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  const B = ({ id, label, hint, onClick, tone = "" }:
    { id: string; label: string; hint: string; onClick: () => void; tone?: string }) => (
    <button
      onClick={onClick}
      disabled={!!busy}
      className={`group flex-1 rounded-xl border border-line bg-card px-4 py-3 text-left transition hover:border-accent/40 hover:shadow-sm disabled:opacity-50 ${tone}`}
    >
      <div className="text-sm font-semibold">{busy === id ? "Running…" : label}</div>
      <div className="text-xs text-muted">{hint}</div>
    </button>
  );

  return (
    <div>
      <div className="flex flex-col gap-2 sm:flex-row">
        <B id="clean" label="Run the loop" hint="200 claims · judge · pay · reconcile"
          onClick={() => run("clean", () => api.run({ regenerate: true }),
            () => "Clean run complete.")} />
        <B id="timeout" label="Inject payout timeout" hint="force a rail timeout → reconcile"
          onClick={() => run("timeout", () => api.run({ regenerate: true, fail_payout: true }),
            () => "Payout timed out, then reconciled — no double-pay.")} />
        <B id="gsp" label="Take the GSP offline" hint="verdicts degrade to PROVISIONAL"
          onClick={() => run("gsp", () => api.run({ regenerate: true, gsp_down: true }),
            () => "GSP down: high-value claims went PROVISIONAL, payouts still ran.")} />
        <B id="rule" label="Simulate a GST rule change" hint="block coworking u/s 17(5) → recompute history"
          onClick={() => run("rule", () => api.reevaluate({ block_category: "coworking" }),
            (r) => `Rule bumped to v${r.new_version}: ${r.changed_count} historical verdicts recomputed.`)} />
      </div>
      {msg && <div className="mt-2 text-sm text-accent fadeup">{msg}</div>}
    </div>
  );
}
