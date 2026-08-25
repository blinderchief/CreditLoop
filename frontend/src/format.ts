// Indian-format rupees: ₹1,23,456
export function rupees(n: number | null | undefined, paise = false): string {
  if (n == null) return "—";
  const neg = n < 0;
  n = Math.abs(n);
  const [whole, frac] = paise ? n.toFixed(2).split(".") : [Math.round(n).toString(), ""];
  let s = whole;
  if (s.length > 3) {
    const head = s.slice(0, -3);
    const tail = s.slice(-3);
    const parts: string[] = [];
    let h = head;
    while (h.length > 2) {
      parts.unshift(h.slice(-2));
      h = h.slice(0, -2);
    }
    if (h) parts.unshift(h);
    s = parts.join(",") + "," + tail;
  }
  return (neg ? "-" : "") + "₹" + s + (frac ? "." + frac : "");
}

export const pct = (n: number | null | undefined, dp = 1): string =>
  n == null ? "—" : (n * 100).toFixed(dp) + "%";

export type DecisionKind =
  | "RECOVERABLE" | "PROVISIONAL" | "PENDING_QRMP"
  | "UNRECOVERABLE_WRONG_ENTITY" | "BLOCKED_17_5" | "EXCEPTION";

// tone: which colour a decision speaks in
export const decisionTone: Record<string, "money" | "risk" | "loss" | "muted"> = {
  RECOVERABLE: "money",
  PROVISIONAL: "risk",
  PENDING_QRMP: "risk",
  UNRECOVERABLE_WRONG_ENTITY: "loss",
  BLOCKED_17_5: "loss",
  EXCEPTION: "risk",
};

export const decisionLabel: Record<string, string> = {
  RECOVERABLE: "Recoverable",
  PROVISIONAL: "Provisional",
  PENDING_QRMP: "Pending (QRMP)",
  UNRECOVERABLE_WRONG_ENTITY: "Wrong entity",
  BLOCKED_17_5: "Blocked 17(5)",
  EXCEPTION: "Exception",
};

export const toneClasses: Record<string, string> = {
  money: "text-money bg-money-soft",
  risk: "text-risk bg-risk-soft",
  loss: "text-loss bg-loss-soft",
  muted: "text-muted bg-paper",
};

export const categoryEmoji: Record<string, string> = {
  hotel: "🏨", flight: "✈️", cab: "🚕", meals: "🍽️",
  saas: "💻", equipment: "🖥️", telecom: "📶", coworking: "🏢",
};
