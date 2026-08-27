import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Summary, type ClaimRow } from "./api";
import { rupees } from "./format";
import { Counter } from "./components/Counter";
import { Controls } from "./components/Controls";
import { ClaimsTable } from "./components/ClaimsTable";
import { ClaimDrawer } from "./components/ClaimDrawer";
import { Metrics } from "./components/Metrics";
import { Vendors } from "./components/Vendors";
import { Compliance } from "./components/Compliance";
import { OverclaimPanel, RegistrationRoiPanel } from "./components/Insights";
import { Mark } from "./components/Logo";
import { Card, Badge, Spinner, SectionHead } from "./components/ui";

type Tab = "overview" | "claims" | "exceptions" | "metrics" | "vendors" | "compliance";

export function App() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [status, setStatus] = useState<{ llm: any; razorpay: any } | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [openId, setOpenId] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const refresh = () => {
    api.summary().then(setSummary);
    setReloadKey((k) => k + 1);
  };
  useEffect(() => { api.summary().then(setSummary); api.status().then(setStatus); }, []);

  const tabs: [Tab, string][] = [
    ["overview", "Overview"], ["claims", "Claims"], ["exceptions", "Exceptions"],
    ["metrics", "Metrics"], ["vendors", "Vendors"], ["compliance", "Compliance"],
  ];

  return (
    <div className="min-h-screen">
      {/* header */}
      <header className="sticky top-0 z-30 border-b border-line bg-paper/85 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-3">
          <Link to="/" className="flex items-center gap-2.5">
            <Mark size={26} />
            <div>
              <div className="font-semibold leading-tight">CreditLoop</div>
              <div className="text-[11px] text-muted">close the GST loop before the money moves</div>
            </div>
          </Link>
          <div className="flex items-center gap-3 text-right">
            {status && (
              <div className="hidden items-center gap-1.5 sm:flex">
                <Badge tone={status.llm?.enabled ? "money" : "muted"}>
                  {status.llm?.enabled ? `AI: ${status.llm.model}` : "AI: synthetic"}
                </Badge>
                <Badge tone={status.razorpay?.live ? "money" : "muted"}>
                  {status.razorpay?.live ? "RazorpayX: test" : "Payouts: mock"}
                </Badge>
              </div>
            )}
            {summary && (
              <div className="hidden sm:block text-right">
                <div className="text-[11px] text-muted">{summary.company.name}</div>
                <div className="font-mono text-[11px] text-muted">
                  {(summary.company.registrations ?? []).map((r) => r.state_name).join(" · ")}
                  {" "}({(summary.company.registrations ?? []).length} GSTINs)
                </div>
              </div>
            )}
            {summary?.failure_flags?.gsp_down && <Badge tone="risk">GSP offline</Badge>}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-5 py-6">
        {!summary ? <Spinner /> : (
          <>
            <Counter s={summary} />

            <div className="mt-5">
              <Controls onDone={refresh} />
            </div>

            {/* tabs */}
            <nav className="mt-6 flex gap-1 border-b border-line">
              {tabs.map(([id, label]) => (
                <button
                  key={id}
                  onClick={() => setTab(id)}
                  className={`relative px-4 py-2 text-sm font-medium transition ${
                    tab === id ? "text-ink" : "text-muted hover:text-ink"
                  }`}
                >
                  {label}
                  {id === "exceptions" && (
                    <span className="ml-1.5 rounded-full bg-risk-soft px-1.5 py-0.5 text-[10px] text-risk">
                      {summary.batch.exceptions}
                    </span>
                  )}
                  {tab === id && <span className="absolute inset-x-2 -bottom-px h-0.5 rounded bg-accent" />}
                </button>
              ))}
            </nav>

            <div className="py-5">
              {tab === "overview" && <Overview s={summary} onOpen={setOpenId} />}
              {tab === "claims" && <ClaimsTable onOpen={setOpenId} reloadKey={reloadKey} />}
              {tab === "exceptions" && <Exceptions reloadKey={reloadKey} onOpen={setOpenId} />}
              {tab === "metrics" && <Metrics s={summary} />}
              {tab === "vendors" && <Vendors />}
              {tab === "compliance" && <Compliance onChanged={refresh} />}
            </div>
          </>
        )}
      </main>

      <ClaimDrawer id={openId} onClose={() => setOpenId(null)} />

      <footer className="mx-auto max-w-6xl px-5 py-8 text-center text-xs text-muted">
        CreditLoop · deterministic law + calibrated prediction, strictly separated · read, never file · money never touched
      </footer>
    </div>
  );
}

function Overview({ s, onOpen }: { s: Summary; onOpen: (id: string) => void }) {
  const [recent, setRecent] = useState<ClaimRow[] | null>(null);
  useEffect(() => {
    api.claims("?limit=8").then((r) =>
      setRecent([...r].sort((a, b) => b.tax_at_stake - a.tax_at_stake).slice(0, 8)));
  }, [s.ran_at]);

  const r = s.reconcile || {};
  return (
    <div className="space-y-5">
     {s.money.overclaimed > 0 && (
       <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
         <div className="lg:col-span-2"><OverclaimPanel reloadKey={s.ran_at} /></div>
         <RegistrationRoiPanel reloadKey={s.ran_at} />
       </div>
     )}
     <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
      <Card className="p-5 lg:col-span-2">
        <SectionHead title="Highest tax at stake" sub="Where the agent spends attention — click any row for the full trail." />
        {!recent ? <Spinner /> : (
          <div className="divide-y divide-line/60">
            {recent.map((c) => (
              <button key={c.claim_id} onClick={() => onOpen(c.claim_id)}
                className="flex w-full items-center justify-between py-2.5 text-left hover:bg-paper">
                <div>
                  <div className="text-sm font-medium">{c.employee_name} · <span className="text-muted">{c.supplier_name}</span></div>
                  <div className="text-xs text-muted">{c.category} · {rupees(c.amount_gross)}</div>
                </div>
                <div className="text-right">
                  <div className="tnum text-sm font-semibold">{rupees(c.tax_at_stake)}</div>
                  <div className="text-[11px] text-muted">{c.decision}</div>
                </div>
              </button>
            ))}
          </div>
        )}
      </Card>

      <div className="space-y-4">
        <Card className="p-5">
          <SectionHead title="The loop closed" />
          <ul className="space-y-2 text-sm">
            <LoopRow k="Claims judged" v={String(s.batch.claims)} />
            <LoopRow k="Paid on time" v={String(s.batch.paid)} tone="text-money" />
            <LoopRow k="2B match rate" v={`${(s.match.match_rate * 100).toFixed(0)}% (${s.match.matched}/${s.match.total_lines})`} tone="text-money" />
            <LoopRow k="Confirmed in 2B" v={`${r.confirmed ?? "—"}`} />
            <LoopRow k="Pending (QRMP lag)" v={`${r.pending_qrmp ?? "—"}`} tone="text-risk" />
            <LoopRow k="Unconfirmed — chase" v={`${r.unconfirmed ?? "—"}`} tone="text-loss" />
            <LoopRow k="Live GSP calls" v={`${s.efficiency?.live_calls ?? "—"} (${s.gsp_calls_per_claim ?? "—"}/claim)`} tone="text-money" />
            <LoopRow k="Vendors learned" v={`${r.vendors_updated ?? "—"}`} />
          </ul>
        </Card>
      </div>
     </div>
    </div>
  );
}

function LoopRow({ k, v, tone = "" }: { k: string; v: string; tone?: string }) {
  return (
    <li className="flex justify-between">
      <span className="text-muted">{k}</span>
      <span className={`font-medium tnum ${tone}`}>{v}</span>
    </li>
  );
}

function Exceptions({ reloadKey, onOpen }: { reloadKey: number; onOpen: (id: string) => void }) {
  const [rows, setRows] = useState<ClaimRow[] | null>(null);
  useEffect(() => { setRows(null); api.exceptions().then(setRows); }, [reloadKey]);
  if (!rows) return <Spinner />;

  const groups: Record<string, ClaimRow[]> = {};
  for (const r of rows) (groups[r.reason_code ?? "OTHER"] ??= []).push(r);

  return (
    <div>
      <SectionHead title={`Exception list — ${rows.length} claims the agent refused to decide`}
        sub="Every one carries a machine-readable reason. Nothing fails silently. Lower is not automatically better." />
      <div className="space-y-4">
        {Object.entries(groups).map(([reason, rs]) => (
          <Card key={reason} className="overflow-hidden">
            <div className="flex items-center justify-between border-b border-line bg-paper px-4 py-2">
              <span className="font-mono text-sm text-risk">{reason}</span>
              <span className="text-xs text-muted">{rs.length} claims · {rupees(rs.reduce((a, b) => a + b.tax_at_stake, 0))} at stake</span>
            </div>
            <div className="divide-y divide-line/60">
              {rs.map((c) => (
                <button key={c.claim_id} onClick={() => onOpen(c.claim_id)}
                  className="flex w-full items-center justify-between px-4 py-2 text-left text-sm hover:bg-paper">
                  <span>{c.employee_name} · <span className="text-muted">{c.supplier_name || c.category}</span></span>
                  <span className="tnum text-muted">{rupees(c.tax_at_stake)}</span>
                </button>
              ))}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
