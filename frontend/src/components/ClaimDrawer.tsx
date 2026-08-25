import { useEffect, useState } from "react";
import { api, type ClaimDetail, type Draft } from "../api";
import { rupees, pct, decisionLabel, decisionTone, categoryEmoji } from "../format";
import { Badge, Spinner } from "./ui";

const DRAFT_DECISIONS = new Set([
  "UNRECOVERABLE_WRONG_ENTITY", "RECOVERABLE", "PENDING_QRMP", "PROVISIONAL",
]);

export function ClaimDrawer({ id, onClose }: { id: string | null; onClose: () => void }) {
  const [d, setD] = useState<ClaimDetail | null>(null);
  useEffect(() => {
    setD(null);
    if (id) api.claim(id).then(setD);
  }, [id]);

  if (!id) return null;
  const v = d?.verdicts?.[d.verdicts.length - 1];

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-[2px]" onClick={onClose} />
      <div className="relative z-50 h-full w-full max-w-2xl overflow-y-auto bg-paper shadow-2xl fadeup">
        {!d ? <Spinner /> : (
          <div className="p-6">
            <div className="flex items-start justify-between">
              <div>
                <div className="text-xs uppercase tracking-wide text-muted">Claim {d.claim.claim_id}</div>
                <h2 className="mt-1 text-2xl font-semibold">
                  {categoryEmoji[d.claim.category]} {d.claim.employee_name}
                </h2>
                <div className="text-sm text-muted">{d.claim.description}</div>
              </div>
              <button onClick={onClose} className="rounded-lg px-3 py-1 text-muted hover:bg-line/50">✕</button>
            </div>

            {/* verdict headline */}
            {v && (
              <div className="mt-4 rounded-2xl border border-line bg-card p-4">
                <div className="flex items-center justify-between">
                  <Badge tone={decisionTone[v.decision]}>
                    {decisionLabel[v.decision] ?? v.decision}{v.reason_code ? ` · ${v.reason_code}` : ""}
                  </Badge>
                  <div className="text-sm text-muted">
                    P(recover) <span className="font-semibold text-ink tnum">{pct(v.predicted_recoverable_p)}</span>
                  </div>
                </div>
                <p className="mt-2 text-sm text-ink/80">{v.reasoning}</p>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {v.rules.map((r: string) => (
                    <span key={r} className="rounded-md bg-accent-soft px-2 py-0.5 font-mono text-[11px] text-accent">
                      {r}
                    </span>
                  ))}
                </div>
                {d.scenario && (
                  <div className="mt-2 text-[11px] text-muted">
                    ground-truth scenario: <span className="font-mono">{d.scenario}</span>
                  </div>
                )}
              </div>
            )}

            {v && DRAFT_DECISIONS.has(v.decision) && <DraftPanel id={d.claim.claim_id} decision={v.decision} />}

            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              {/* receipt */}
              <div className="rounded-2xl border border-line bg-card p-3">
                <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Receipt</div>
                {d.claim.receipt_path
                  ? <img src={"/" + d.claim.receipt_path} alt="receipt"
                      className="max-h-80 w-full rounded-lg object-contain" />
                  : <div className="text-sm text-muted">no image</div>}
              </div>

              {/* extracted invoice */}
              <div className="rounded-2xl border border-line bg-card p-3">
                <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
                  Extracted invoice · conf {pct(d.invoice?.extraction_confidence, 0)}
                </div>
                {d.invoice ? (
                  <dl className="space-y-1 text-sm">
                    <Row k="Supplier" val={d.invoice.supplier_name} />
                    <Row k="Supplier GSTIN" mono val={d.invoice.supplier_gstin || "— missing —"} />
                    <Row k="Invoice #" mono val={d.invoice.invoice_no || "—"} />
                    <Row k="Date" val={d.invoice.invoice_date || "—"} />
                    <Row k="Taxable" val={rupees(d.invoice.taxable_value, true)} />
                    <Row k="Tax (C+S+I)" val={rupees(d.invoice.total_tax, true)} />
                    <Row k="Billed to" val={d.invoice.buyer_name} />
                    <Row k="Buyer GSTIN" mono val={d.invoice.buyer_gstin || "— individual —"} />
                  </dl>
                ) : <div className="text-sm text-muted">—</div>}
              </div>
            </div>

            {/* payout + 2B */}
            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Mini title="Payout">
                {d.payout ? (
                  <div className="text-sm">
                    <div className="flex justify-between"><span className="text-muted">Status</span>
                      <span className="font-medium">{d.payout.status}</span></div>
                    <div className="flex justify-between"><span className="text-muted">Amount</span>
                      <span className="tnum">{rupees(d.payout.amount, true)}</span></div>
                    <div className="flex justify-between"><span className="text-muted">Ref</span>
                      <span className="font-mono text-xs">{d.payout.razorpay_ref || "—"}</span></div>
                    <div className="mt-1 text-[11px] text-muted">idem: {d.payout.idempotency_key}</div>
                  </div>
                ) : <span className="text-sm text-muted">held / not paid</span>}
              </Mini>
              <Mini title="GSTR-2B line">
                {d.two_b_line ? (
                  <div className="text-sm">
                    <div className="flex justify-between"><span className="text-muted">Matched</span>
                      <span className="font-medium text-money">yes · {d.two_b_line.return_period}</span></div>
                    <div className="flex justify-between"><span className="text-muted">2B taxable</span>
                      <span className="tnum">{rupees(d.two_b_line.taxable_value, true)}</span></div>
                  </div>
                ) : <span className="text-sm text-muted">not in this 2B pull</span>}
              </Mini>
            </div>

            {/* audit trail */}
            <div className="mt-4 rounded-2xl border border-line bg-card p-3">
              <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Audit trail</div>
              <ol className="space-y-2">
                {d.audit.map((a: any) => (
                  <li key={a.id} className="flex gap-3 text-sm">
                    <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                    <div>
                      <span className="font-mono text-xs text-accent">{a.action}</span>
                      <span className="ml-2 text-[11px] text-muted">{a.actor} · {new Date(a.at).toLocaleTimeString()}</span>
                      <pre className="mt-0.5 whitespace-pre-wrap break-all text-[11px] text-muted">
                        {JSON.stringify(a.detail)}
                      </pre>
                    </div>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function DraftPanel({ id, decision }: { id: string; decision: string }) {
  const [draft, setDraft] = useState<Draft | null>(null);
  const [lang, setLang] = useState<"english" | "hinglish">("english");
  const [busy, setBusy] = useState(false);
  const label = decision === "UNRECOVERABLE_WRONG_ENTITY"
    ? "Draft reissue request to vendor" : "Draft filing reminder to vendor";

  async function load() {
    setBusy(true);
    try { setDraft(await api.draft(id)); } finally { setBusy(false); }
  }

  return (
    <div className="mt-4 rounded-2xl border border-line bg-card p-4">
      <div className="flex items-center justify-between">
        <div className="text-xs font-semibold uppercase tracking-wide text-muted">Intervention</div>
        {draft && (
          <div className="flex gap-1 text-xs">
            {(["english", "hinglish"] as const).map((l) => (
              <button key={l} onClick={() => setLang(l)}
                className={`rounded-md px-2 py-0.5 capitalize ${lang === l ? "bg-accent-soft text-accent" : "text-muted"}`}>{l}</button>
            ))}
          </div>
        )}
      </div>
      {!draft ? (
        <button onClick={load} disabled={busy}
          className="mt-2 rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-[#0d0b09] transition hover:brightness-110 disabled:opacity-50">
          {busy ? "Drafting…" : `✍ ${label}`}
        </button>
      ) : (
        <div className="mt-2">
          <div className="text-sm font-medium">{draft.subject}</div>
          <pre className="mt-2 max-h-56 overflow-y-auto whitespace-pre-wrap rounded-lg bg-paper p-3 text-[13px] leading-relaxed text-ink/85">
            {lang === "english" ? draft.english : draft.hinglish}
          </pre>
          <div className="mt-1 text-[11px] text-muted">drafted by {draft.source}</div>
        </div>
      )}
    </div>
  );
}

function Row({ k, val, mono }: { k: string; val: string; mono?: boolean }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-muted">{k}</dt>
      <dd className={mono ? "font-mono text-xs" : ""}>{val}</dd>
    </div>
  );
}
function Mini({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-line bg-card p-3">
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">{title}</div>
      {children}
    </div>
  );
}
