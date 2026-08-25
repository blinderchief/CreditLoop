// CreditLoop mark: an almost-closed loop with a single dot at the seam —
// "the loop closes, and the credit (the dot) comes back." Minimal, geometric,
// high-contrast; works in gold on dark or ink on light.

export function Mark({ size = 28, color = "#e9b357" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden>
      <circle
        cx="16" cy="16" r="11" stroke={color} strokeWidth="3.4" fill="none"
        strokeDasharray="55 16" strokeLinecap="round" transform="rotate(-90 16 16)"
      />
      <circle cx="16" cy="5" r="2.4" fill={color} />
    </svg>
  );
}

export function Logo({ color = "#f2e7d3", mark = "#e9b357", size = 28 }:
  { color?: string; mark?: string; size?: number }) {
  return (
    <span className="inline-flex items-center gap-2.5 select-none">
      <Mark size={size} color={mark} />
      <span className="text-[1.05rem] font-semibold tracking-tight" style={{ color }}>
        CreditLoop
      </span>
    </span>
  );
}
