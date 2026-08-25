import { useEffect, useState } from "react";
import { api, type ClaimRow } from "../api";
import { rupees, categoryEmoji, decisionLabel, decisionTone } from "../format";
import { Badge, TierPill, Spinner } from "./ui";

const DECISIONS = ["", "RECOVERABLE", "PENDING_QRMP", "PROVISIONAL",
  "UNRECOVERABLE_WRONG_ENTITY", "BLOCKED_17_5", "EXCEPTION"];

export function ClaimsTable({ onOpen, reloadKey }: { onOpen: (id: string) => void; reloadKey: number }) {
  const [rows, setRows] = useState<ClaimRow[] | null>(null);
  const [decision, setDecision] = useState("");
  const [q, setQ] = useState("");

  useEffect(() => {
    setRows(null);
    const params = new URLSearchParams();
    if (decision) params.set("decision", decision);
    if (q) params.set("q", q);
    const qs = params.toString();
    api.claims(qs ? "?" + qs : "").then(setRows);
  }, [decision, q, reloadKey]);

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search employee or vendor…"
          className="w-64 rounded-lg border border-line bg-card px-3 py-1.5 text-sm outline-none focus:border-accent/50"
        />
        <select
          value={decision}
          onChange={(e) => setDecision(e.target.value)}
          className="rounded-lg border border-line bg-card px-3 py-1.5 text-sm outline-none focus:border-accent/50"
        >
          {DECISIONS.map((d) => (
            <option key={d} value={d}>{d ? decisionLabel[d] ?? d : "All verdicts"}</option>
          ))}
        </select>
        {rows && <span className="text-sm text-muted">{rows.length} claims</span>}
      </div>

      {!rows ? <Spinner /> : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
                <th className="px-4 py-2 font-medium">Claim</th>
                <th className="px-4 py-2 font-medium">Vendor</th>
                <th className="px-4 py-2 text-right font-medium">Amount</th>
                <th className="px-4 py-2 text-right font-medium">Tax</th>
                <th className="px-4 py-2 text-center font-medium">Tier</th>
                <th className="px-4 py-2 font-medium">Verdict</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr
                  key={r.claim_id}
                  onClick={() => onOpen(r.claim_id)}
                  className="cursor-pointer border-b border-line/60 transition hover:bg-paper"
                >
                  <td className="px-4 py-2.5">
                    <div className="font-medium">
                      {categoryEmoji[r.category]} {r.employee_name}
                    </div>
                    <div className="text-xs text-muted">{r.category}</div>
                  </td>
                  <td className="px-4 py-2.5 text-muted">{r.supplier_name || "—"}</td>
                  <td className="px-4 py-2.5 text-right tnum">{rupees(r.amount_gross)}</td>
                  <td className="px-4 py-2.5 text-right tnum text-muted">{rupees(r.tax_at_stake)}</td>
                  <td className="px-4 py-2.5 text-center"><TierPill tier={r.tier} /></td>
                  <td className="px-4 py-2.5">
                    {r.decision && (
                      <Badge tone={decisionTone[r.decision]}>
                        {decisionLabel[r.decision] ?? r.decision}
                        {r.reason_code ? ` · ${r.reason_code}` : ""}
                      </Badge>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
