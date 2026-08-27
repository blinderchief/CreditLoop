import type { Summary } from "../api";
import { rupees, pct } from "../format";
import { Card } from "./ui";

// The counter, now in THREE fates (PRD v2): recoverable / structurally dead /
// wrongly claimed. The red one — money you owe back with interest — is the loud
// number nobody's finance stack shows them.
export function Counter({ s }: { s: Summary }) {
  const m = s.money;
  const denom = m.recoverable + m.structurally_dead + m.overclaimed || 1;

  return (
    <Card className="p-6 fadeup">
      <div className="flex items-baseline justify-between">
        <div>
          <div className="text-sm font-medium text-muted">GST on this batch of {s.batch.claims} claims</div>
          <div className="mt-1 text-4xl font-semibold tracking-tight tnum">{rupees(m.total_gst)}</div>
        </div>
        <div className="text-right">
          <div className="text-sm text-muted">Recoverable</div>
          <div className="text-2xl font-semibold text-money tnum">{pct(m.recoverable / denom, 0)}</div>
        </div>
      </div>

      {/* the loop bar: three fates */}
      <div className="mt-5 flex h-3 overflow-hidden rounded-full bg-paper">
        <Seg w={m.recoverable / denom} className="bg-money" />
        <Seg w={m.structurally_dead / denom} className="bg-[#6b6153]" />
        <Seg w={m.overclaimed / denom} className="bg-loss" />
      </div>

      <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Stat label="Recoverable" value={rupees(m.recoverable)} tone="text-money"
          sub={m.fixable_wrong_gstin > 0 ? `${rupees(m.fixable_wrong_gstin)} fixable (wrong GSTIN)` : "claim it"} />
        <Stat label="Structurally dead" value={rupees(m.structurally_dead)} tone="text-[#c9bca6]"
          sub="no action will help — book as cost" />
        <Stat label="⚠ Wrongly claimed" value={rupees(m.overclaimed)} tone="text-loss"
          sub={`${s.batch.overclaim_claims} claims · owe back + 24% interest`} big />
      </div>
    </Card>
  );
}

function Seg({ w, className }: { w: number; className: string }) {
  return <div className={className} style={{ width: `${Math.max(0, w * 100)}%` }} />;
}

function Stat({ label, value, tone, sub, big }:
  { label: string; value: string; tone: string; sub?: string; big?: boolean }) {
  return (
    <div className={`rounded-xl px-3 py-3 ${big ? "bg-loss-soft ring-1 ring-loss/25" : "bg-elevated"}`}>
      <div className="text-xs font-medium text-muted">{label}</div>
      <div className={`mt-0.5 text-xl font-semibold tnum ${tone}`}>{value}</div>
      {sub && <div className="mt-0.5 text-[11px] text-muted">{sub}</div>}
    </div>
  );
}
