import { useEffect, useState } from "react";
import { api, type Proposal } from "../api";
import { Card, Badge, SectionHead } from "./ui";

// The Dynamic Compliance Engine: an agent reads GST sources and DRAFTS rule
// diffs; a human approves before anything goes live. Detection autonomous,
// application gated.
export function Compliance({ onChanged }: { onChanged: () => void }) {
  const [props, setProps] = useState<Proposal[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = () => api.proposals().then(setProps);
  useEffect(() => { load(); }, []);

  async function detect() {
    setBusy("detect");
    try { await api.detect(); await load(); } finally { setBusy(null); }
  }
  async function act(id: string, kind: "approve" | "reject") {
    setBusy(id);
    try {
      await (kind === "approve" ? api.approve(id) : api.reject(id));
      await load();
      onChanged();
    } finally { setBusy(null); }
  }

  const tone: Record<string, string> = { pending: "risk", approved: "money", rejected: "loss" };

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <SectionHead title="Dynamic Compliance Engine"
          sub="An agent watches GST sources and drafts rule changes. Nothing goes live without a human. Detection is autonomous; application is gated." />
        <button onClick={detect} disabled={!!busy}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-[#0d0b09] transition hover:brightness-110 disabled:opacity-50">
          {busy === "detect" ? "Scanning…" : "⟳ Scan GST sources"}
        </button>
      </div>

      {!props ? null : props.length === 0 ? (
        <Card className="p-8 text-center text-muted">
          No proposals yet. Click “Scan GST sources” to run the change-detection agent.
        </Card>
      ) : (
        <div className="space-y-4">
          {props.map((p) => (
            <Card key={p.id} className="p-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <Badge tone={tone[p.status]}>{p.status}</Badge>
                    <span className="text-sm font-semibold">{p.source_title}</span>
                  </div>
                  <p className="mt-2 text-sm text-muted">{p.source_excerpt}</p>
                </div>
                {p.source_url && (
                  <a href={p.source_url} target="_blank" rel="noreferrer"
                    className="shrink-0 text-xs text-accent hover:underline">source ↗</a>
                )}
              </div>

              <div className="mt-3 rounded-xl bg-paper p-3 text-sm">
                <span className="text-muted">Proposed diff · </span>
                <span className="font-mono text-accent">{p.target_rule_id}</span>
                <span className="text-muted"> — {p.action}</span>
                {p.payload?.category && (
                  <span> → block <span className="font-medium">{p.payload.category}</span></span>
                )}
                <p className="mt-1 text-muted">{p.rationale}</p>
              </div>

              {p.status === "pending" ? (
                <div className="mt-3 flex gap-2">
                  <button onClick={() => act(p.id, "approve")} disabled={!!busy}
                    className="rounded-lg bg-money px-4 py-1.5 text-sm font-medium text-[#0d0b09] transition hover:brightness-110 disabled:opacity-50">
                    {busy === p.id ? "Applying…" : "✓ Approve (CA) → recompute history"}
                  </button>
                  <button onClick={() => act(p.id, "reject")} disabled={!!busy}
                    className="rounded-lg border border-line px-4 py-1.5 text-sm font-medium text-muted transition hover:bg-paper disabled:opacity-50">
                    Reject
                  </button>
                </div>
              ) : p.status === "approved" ? (
                <div className="mt-3 text-sm text-money">
                  ✓ Approved by {p.reviewed_by} · {p.changed_claim_count} historical verdicts recomputed
                  (old verdicts kept — append-only).
                </div>
              ) : (
                <div className="mt-3 text-sm text-muted">Rejected — no change applied.</div>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
