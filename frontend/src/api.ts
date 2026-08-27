// Thin typed client for the CreditLoop backend.
// Same-origin by default (single-service deploy). For a split deploy (e.g.
// frontend on Vercel + backend on Render), set VITE_API_BASE to the backend URL.
const BASE = (import.meta as any).env?.VITE_API_BASE?.replace(/\/$/, "") || "";

async function get<T>(path: string): Promise<T> {
  const r = await fetch(BASE + path);
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return r.json();
}
async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(BASE + path, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return r.json();
}

export interface Summary {
  company: { name: string; gstin: string; registrations: { state_code: string; state_name: string; gstin: string }[] };
  batch: { claims: number; exceptions: number; paid: number; held: number; overclaim_claims: number };
  money: {
    recoverable: number; structurally_dead: number; overclaimed: number;
    at_risk_chase: number; fixable_wrong_gstin: number; state_trapped: number;
    blocked_17_5: number; lost_wrong_entity: number; total_gst: number;
  };
  reissue_candidates: number;
  decisions: Record<string, number>;
  tiers: Record<string, number>;
  match: { matched: number; total_lines: number; match_rate: number };
  efficiency: { live_calls: number; cache_hits: number; available: boolean; mode: string };
  gsp_calls_per_claim: number | null;
  throughput: { claims_per_min: number | null; elapsed_s: number | null };
  reconcile: any;
  failure_flags: { fail_payout?: boolean; gsp_down?: boolean };
  ran_at: string | null;
}

export interface ClaimRow {
  claim_id: string; seq: number; employee_name: string; category: string;
  amount_gross: number; status: string; tier: number; supplier_name: string;
  decision: string | null; reason_code: string | null;
  tax_at_stake: number; p_recoverable: number;
}

export interface ClaimDetail {
  claim: any; invoice: any; verdicts: any[]; payout: any;
  two_b_line: any; audit: any[]; scenario: string | null;
}

export interface Metrics {
  claims: number;
  decision_accuracy_under_triage: number;
  engine_accuracy_full_validation: number;
  match_rate: number; match_rate_detail: string;
  calibration_ece: number;
  reliability_curve: { bin: number; avg_pred: number | null; obs_rate: number | null; count: number }[];
  false_block_count: number; false_block_cost: number;
  exception_rate: number; exception_count: number;
  section_17_5?: { precision: number; recall: number; tp: number; fp: number; fn: number };
  state_trapped?: { precision: number; recall: number };
  overclaim?: { exposure: number; interest_24pc_yr: number; claims: number; detection_recall: number };
  extraction: any; throughput: any;
  triage_deltas: any[];
}

export interface Vendor {
  gstin: string; legal_name: string; filing_frequency: string;
  reliability_score: number; active: boolean; observation_count: number;
}

export const api = {
  summary: () => get<Summary>("/api/summary"),
  claims: (qs = "") => get<ClaimRow[]>("/api/claims" + qs),
  claim: (id: string) => get<ClaimDetail>("/api/claims/" + id),
  exceptions: () => get<ClaimRow[]>("/api/exceptions"),
  metrics: () => get<Metrics>("/api/metrics"),
  vendors: () => get<Vendor[]>("/api/vendors"),
  rules: () => get<any[]>("/api/rules"),
  status: () => get<{ llm: any; gsp: any; razorpay: any }>("/api/status"),
  draft: (id: string) => get<Draft>("/api/claims/" + id + "/draft"),
  proposals: () => get<Proposal[]>("/api/compliance/proposals"),
  detect: () => post<{ proposals: Proposal[] }>("/api/compliance/detect", {}),
  approve: (id: string) => post<any>(`/api/compliance/proposals/${id}/approve`, {}),
  reject: (id: string) => post<any>(`/api/compliance/proposals/${id}/reject`, {}),
  evalExtraction: (sample = 0) => post<any>("/api/eval/extraction?sample=" + sample, {}),
  overclaim: () => get<Overclaim>("/api/overclaim"),
  registrationRoi: () => get<RegistrationRoi>("/api/registration-roi"),
  run: (body: { fail_payout?: boolean; gsp_down?: boolean; regenerate?: boolean }) =>
    post<any>("/api/run", body),
  reevaluate: (body: { rule_id?: string; block_category?: string; note?: string }) =>
    post<any>("/api/rules/reevaluate", body),
};

export interface Draft {
  kind: string; subject: string; english: string; hinglish: string; source: string;
}
export interface Overclaim {
  exposure: number; interest_24pc_yr: number; claims: number;
  breakdown: { label: string; amount: number; claims: number }[];
}
export interface RegistrationRoi {
  registered_states: { code: string; name: string }[];
  cost_per_registration_yr: number; total_trapped: number;
  by_state: { state_code: string; state_name: string; trapped: number; net_if_registered: number; worth_it: boolean }[];
}
export interface Proposal {
  id: string; source_title: string; source_excerpt: string; source_url: string;
  target_rule_id: string; action: string; payload: any; rationale: string;
  status: string; reviewed_by: string | null; changed_claim_count: number | null;
  created_at: string;
}
