import { useEffect, useState } from "react";
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, Scatter, ComposedChart,
} from "recharts";
import { api, type Metrics as M, type Summary } from "../api";
import { rupees, pct } from "../format";
import { Card, SectionHead } from "./ui";

export function Metrics({ s }: { s: Summary }) {
  const [m, setM] = useState<M | null>(null);
  useEffect(() => { api.metrics().then(setM); }, [s.ran_at]);
  if (!m) return null;

  const curve = m.reliability_curve.filter((r) => r.count > 0)
    .map((r) => ({ pred: r.avg_pred, obs: r.obs_rate, n: r.count }));

  const ext = m.extraction || {};
  const extVal = ext.method === "vlm"
    ? pct(ext.field_overall) : "100%*";
  const extSub = ext.method === "vlm"
    ? `${ext.model} · ${ext.sample} receipts` : "synthetic-truth (run VLM eval)";

  const tiles = [
    { label: "Match rate", value: pct(m.match_rate), sub: m.match_rate_detail, tone: "text-money" },
    { label: "Decision accuracy", value: pct(m.decision_accuracy_under_triage), sub: "under triage", tone: "text-ink" },
    { label: "Engine accuracy", value: pct(m.engine_accuracy_full_validation), sub: "full validation", tone: "text-ink" },
    { label: "17(5) precision / recall",
      value: m.section_17_5 ? `${pct(m.section_17_5.precision, 0)} / ${pct(m.section_17_5.recall, 0)}` : "—",
      sub: "blocked-credit classifier", tone: "text-ink" },
    { label: "State-trapped precision / recall",
      value: m.state_trapped ? `${pct(m.state_trapped.precision, 0)} / ${pct(m.state_trapped.recall, 0)}` : "—",
      sub: "over-flagging costs credits", tone: "text-ink" },
    { label: "Overclaim exposure", value: m.overclaim ? rupees(m.overclaim.exposure) : "—",
      sub: m.overclaim ? `${m.overclaim.claims} claims · +${rupees(m.overclaim.interest_24pc_yr)}/yr` : "", tone: "text-loss" },
    { label: "Calibration ECE", value: m.calibration_ece.toFixed(3), sub: "lower is better", tone: "text-ink" },
    { label: "Extraction accuracy", value: extVal, sub: extSub, tone: "text-ink" },
    { label: "False-block cost", value: rupees(m.false_block_cost), sub: `${m.false_block_count} claims`, tone: "text-money" },
    { label: "Exception rate", value: pct(m.exception_rate), sub: `${m.exception_count} claims`, tone: "text-risk" },
    { label: "Throughput", value: (m.throughput?.claims_per_min ? Math.round(m.throughput.claims_per_min).toLocaleString() : "—"), sub: "claims / min", tone: "text-ink" },
    { label: "GSP calls / claim", value: String(s.gsp_calls_per_claim ?? "—"), sub: `${s.efficiency?.live_calls ?? 0} live calls`, tone: "text-money" },
  ];

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {tiles.map((t) => (
          <Card key={t.label} className="p-4">
            <div className="text-xs font-medium text-muted">{t.label}</div>
            <div className={`mt-0.5 text-2xl font-semibold tnum ${t.tone}`}>{t.value}</div>
            <div className="text-[11px] text-muted">{t.sub}</div>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Card className="p-5">
          <SectionHead title="Calibration" sub="Predicted P(recover) vs observed 2B rate. On the diagonal = well calibrated." />
          <div className="h-72">
            <ResponsiveContainer>
              <ComposedChart data={curve} margin={{ top: 8, right: 12, bottom: 8, left: -12 }}>
                <CartesianGrid stroke="#2a2117" />
                <XAxis type="number" dataKey="pred" domain={[0, 1]} tickFormatter={(v) => v.toFixed(1)}
                  stroke="#9d8b71" fontSize={12} label={{ value: "predicted", position: "insideBottom", offset: -2, fontSize: 11, fill: "#9d8b71" }} />
                <YAxis type="number" domain={[0, 1]} tickFormatter={(v) => v.toFixed(1)} stroke="#9d8b71" fontSize={12} />
                <Tooltip contentStyle={{ background: "#17120c", border: "1px solid #2a2117", borderRadius: 10, color: "#f2e7d3" }}
                  formatter={(v: any) => (typeof v === "number" ? v.toFixed(2) : v)} />
                <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]} stroke="#3a2f20" strokeDasharray="4 4" />
                <Line type="monotone" dataKey="obs" stroke="#e9b357" strokeWidth={2} dot={{ r: 4, fill: "#e9b357" }} />
                <Scatter dataKey="obs" fill="#e9b357" />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="p-5">
          <SectionHead title="Triage — where cost concentrates" sub="Most claims cost zero. Live GSP calls only where money is at stake." />
          <div className="space-y-3 pt-2">
            {Object.entries(s.tiers).map(([k, v]) => {
              const meaning: Record<string, string> = {
                tier_0: "< ₹200 · auto-approve · 0 calls",
                tier_1: "₹200–2k · cached vendor data",
                tier_2: "> ₹2k · live GSP validation",
                tier_3: "> ₹2k & p<0.5 · chase vendor",
              };
              const w = (v / s.batch.claims) * 100;
              return (
                <div key={k}>
                  <div className="flex justify-between text-sm">
                    <span className="font-medium">{k.replace("_", " ")}</span>
                    <span className="text-muted">{v} · {meaning[k]}</span>
                  </div>
                  <div className="mt-1 h-2 rounded-full bg-paper">
                    <div className="h-2 rounded-full bg-accent" style={{ width: `${w}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
          <p className="mt-4 text-xs text-muted">
            Exception rate hitting zero would be a failure, not a win — an agent that always decides is
            an agent that guesses.
          </p>
        </Card>
      </div>
    </div>
  );
}
