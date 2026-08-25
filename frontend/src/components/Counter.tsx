import type { Summary } from "../api";
import { rupees, pct } from "../format";
import { Card } from "./ui";

// The number that exists nowhere else in an Indian finance stack:
// ₹ recovered vs ₹ lost, before the money moves.
export function Counter({ s }: { s: Summary }) {
  const m = s.money;
  const denom = m.recovered + m.lost_wrong_entity + m.blocked_17_5 || 1;
  const recPct = m.recovered / denom;

  return (
    <Card className="p-6 fadeup">
      <div className="flex items-baseline justify-between">
        <div>
          <div className="text-sm font-medium text-muted">GST on this batch of {s.batch.claims} claims</div>
          <div className="mt-1 text-4xl font-semibold tracking-tight tnum">{rupees(m.total_gst)}</div>
        </div>
        <div className="text-right">
          <div className="text-sm text-muted">Recoverable</div>
          <div className="text-2xl font-semibold text-money tnum">{pct(recPct, 0)}</div>
        </div>
      </div>

      {/* the loop bar */}
      <div className="mt-5 flex h-3 overflow-hidden rounded-full bg-paper">
        <Seg w={m.recovered / denom} className="bg-money" />
        <Seg w={m.lost_wrong_entity / denom} className="bg-loss" />
        <Seg w={m.blocked_17_5 / denom} className="bg-risk" />
      </div>

      <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Recovered" value={rupees(m.recovered)} tone="text-money" sub="eligible ITC" />
        <Stat label="Lost — wrong entity" value={rupees(m.lost_wrong_entity)} tone="text-loss"
          sub={`${s.reissue_candidates} fixable by reissue`} />
        <Stat label="Blocked 17(5)" value={rupees(m.blocked_17_5)} tone="text-risk" sub="never claimable" />
        <Stat label="At risk — chase" value={rupees(m.at_risk_chase)} tone="text-ink"
          sub="eligible but unlikely to file" />
      </div>
    </Card>
  );
}

function Seg({ w, className }: { w: number; className: string }) {
  return <div className={className} style={{ width: `${Math.max(0, w * 100)}%` }} />;
}

function Stat({ label, value, tone, sub }: { label: string; value: string; tone: string; sub?: string }) {
  return (
    <div className="rounded-xl bg-elevated px-3 py-3">
      <div className="text-xs font-medium text-muted">{label}</div>
      <div className={`mt-0.5 text-xl font-semibold tnum ${tone}`}>{value}</div>
      {sub && <div className="mt-0.5 text-[11px] text-muted">{sub}</div>}
    </div>
  );
}
