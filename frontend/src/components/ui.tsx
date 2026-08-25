import type { ReactNode } from "react";
import { toneClasses } from "../format";

export function Badge({ tone = "muted", children }: { tone?: string; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${toneClasses[tone] ?? toneClasses.muted}`}>
      {children}
    </span>
  );
}

export function Card({ className = "", children }: { className?: string; children: ReactNode }) {
  return <div className={`card ${className}`}>{children}</div>;
}

export function TierPill({ tier }: { tier: number }) {
  const map = ["bg-elevated text-muted", "bg-elevated text-muted",
    "bg-accent-soft text-accent", "bg-risk-soft text-risk"];
  return (
    <span className={`inline-flex h-6 w-8 items-center justify-center rounded-md text-xs font-semibold ${map[tier] ?? map[0]}`}>
      T{tier}
    </span>
  );
}

export function Spinner() {
  return (
    <div className="flex items-center justify-center py-20 text-muted">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-line border-t-accent" />
    </div>
  );
}

export function SectionHead({ title, sub }: { title: string; sub?: string }) {
  return (
    <div className="mb-4">
      <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
      {sub && <p className="text-sm text-muted">{sub}</p>}
    </div>
  );
}
