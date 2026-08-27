import { useEffect, useState } from "react";
import { api, type Overclaim, type RegistrationRoi } from "../api";
import { rupees } from "../format";
import { Card } from "./ui";

// The loudest number in the product: dead credit already claimed in GSTR-3B →
// money you owe back, with 24% interest.
export function OverclaimPanel({ reloadKey }: { reloadKey?: unknown }) {
  const [o, setO] = useState<Overclaim | null>(null);
  useEffect(() => { api.overclaim().then(setO).catch(() => {}); }, [reloadKey]);
  if (!o) return null;

  return (
    <Card className="border-loss/25 bg-loss-soft p-5">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-loss">⚠ Overclaim exposure</div>
          <div className="mt-1 text-3xl font-semibold text-loss tnum">{rupees(o.exposure)}</div>
          <div className="mt-0.5 text-xs text-muted">
            {o.claims} claims already filed in GSTR-3B
            {o.interest_accrued ? ` · ${rupees(o.interest_accrued)} interest accrued so far` : ""}
            {" "}· +{rupees(o.interest_24pc_yr)}/yr at 24%
          </div>
        </div>
      </div>
      <div className="mt-4 space-y-2">
        {o.breakdown.map((b) => (
          <div key={b.label} className="flex items-center justify-between border-t border-loss/10 pt-2 text-sm">
            <span className="text-ink/80">{b.label} <span className="text-muted">· {b.claims}</span></span>
            <span className="tnum font-medium text-loss">{rupees(b.amount)}</span>
          </div>
        ))}
      </div>
      <p className="mt-3 text-[11px] text-muted">Reverse these in your next return before interest compounds.</p>
    </Card>
  );
}

// The decision no Indian CFO has the data to make: which new state registration
// pays for itself.
export function RegistrationRoiPanel({ reloadKey }: { reloadKey?: unknown }) {
  const [r, setR] = useState<RegistrationRoi | null>(null);
  useEffect(() => { api.registrationRoi().then(setR).catch(() => {}); }, [reloadKey]);
  if (!r) return null;

  const max = Math.max(...r.by_state.map((s) => s.trapped), 1);
  return (
    <Card className="p-5">
      <div className="text-sm font-semibold">Registration ROI — trapped credit by state</div>
      <div className="text-xs text-muted">
        Registered in {r.registered_states.map((s) => s.name).join(", ")}. A new registration costs ~{rupees(r.cost_per_registration_yr)}/yr.
      </div>
      <div className="mt-4 space-y-2.5">
        {r.by_state.slice(0, 6).map((s) => (
          <div key={s.state_code}>
            <div className="flex justify-between text-sm">
              <span className="font-medium">{s.state_name}</span>
              <span className="tnum text-muted">{rupees(s.trapped)} trapped{s.worth_it ? " · worth registering" : ""}</span>
            </div>
            <div className="mt-1 h-2 rounded-full bg-paper">
              <div className={`h-2 rounded-full ${s.worth_it ? "bg-money" : "bg-risk"}`}
                style={{ width: `${(s.trapped / max) * 100}%` }} />
            </div>
          </div>
        ))}
      </div>
      <p className="mt-3 text-[11px] text-muted">
        Total trapped across unregistered states: <span className="text-ink">{rupees(r.total_trapped)}</span>.
        Where trapped credit &gt; cost, the registration pays for itself.
      </p>
    </Card>
  );
}
