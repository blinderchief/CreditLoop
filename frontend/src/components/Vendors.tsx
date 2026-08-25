import { useEffect, useState } from "react";
import { api, type Vendor } from "../api";
import { pct } from "../format";
import { Card, Badge, Spinner } from "./ui";

// The moat: which vendors reliably issue compliant B2B invoices. Learned free
// from every 2B statement, forever.
export function Vendors() {
  const [v, setV] = useState<Vendor[] | null>(null);
  useEffect(() => { api.vendors().then(setV); }, []);
  if (!v) return <Spinner />;

  return (
    <Card className="overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
            <th className="px-4 py-2 font-medium">Vendor</th>
            <th className="px-4 py-2 font-medium">GSTIN</th>
            <th className="px-4 py-2 font-medium">Filing</th>
            <th className="px-4 py-2 font-medium">Reliability</th>
            <th className="px-4 py-2 text-right font-medium">Observations</th>
          </tr>
        </thead>
        <tbody>
          {v.map((x) => (
            <tr key={x.gstin} className="border-b border-line/60">
              <td className="px-4 py-2.5 font-medium">
                {x.legal_name}
                {!x.active && <Badge tone="loss">cancelled</Badge>}
              </td>
              <td className="px-4 py-2.5 font-mono text-xs text-muted">{x.gstin}</td>
              <td className="px-4 py-2.5">
                <Badge tone={x.filing_frequency === "QRMP" ? "risk" : "muted"}>{x.filing_frequency}</Badge>
              </td>
              <td className="px-4 py-2.5">
                <div className="flex items-center gap-2">
                  <div className="h-2 w-28 rounded-full bg-paper">
                    <div className="h-2 rounded-full bg-money"
                      style={{ width: `${x.reliability_score * 100}%` }} />
                  </div>
                  <span className="tnum text-xs">{pct(x.reliability_score)}</span>
                </div>
              </td>
              <td className="px-4 py-2.5 text-right tnum text-muted">{x.observation_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}
