# CreditLoop — Architecture

## The one decision everything hangs on

**Deterministic judgment and learned judgment are kept in separate engines that never mix.**

| | DETERMINISTIC (the law) | LEARNED (the prediction) |
|---|---|---|
| Question | Is this ITC *eligible*? | Will this invoice *appear in 2B*? |
| Examples | invoice in company GSTIN? blocked u/s 17(5)? GSTIN valid & active? arithmetic foots? | P(supplier files), vendor reliability, QRMP lag risk |
| Implementation | pure function, versioned rules-as-data (`engine.py`, `rule_registry.py`) | calibrated heuristic, advisory (`predict.py`) |
| Can an LLM change it? | **Never** | It *is* a model output, but it can't decide eligibility or move money |
| Output | a verdict citing `rule_id + version` | a probability in [0,1] feeding triage |

Wrong ITC carries 24% annual interest plus penalties of 10–100%. If a language model can silently flip a tax verdict, no CA signs off and the product is unsellable. So the LLM is confined to what it's genuinely good at — reading messy receipts, drafting vendor requests in the right language, and *proposing* rule diffs a human approves — and is architecturally barred from the verdict and the payout.

## The three layers

```
┌─ LAYER 3 · ACTION ───────────────────────────────────────────────┐
│ approve · hold · pay · chase vendor · flag exception             │
│ every money move idempotent, gated, and written to the audit log │
│  actions.py · tools/razorpay.py                                   │
└───────────────────────────────┬──────────────────────────────────┘
┌─ LAYER 2 · JUDGMENT ──────────┴──────────────────────────────────┐
│ DETERMINISTIC engine.py     │     LEARNED predict.py (advisory)   │
│ + rule_registry.py          │     + triage.py (expected value)    │
│ orchestrated by pipeline.py: extract → rules → predict → triage   │
└───────────────────────────────┬──────────────────────────────────┘
┌─ LAYER 1 · THE LEDGER ────────┴──────────────────────────────────┐
│ claim → invoice → GSTIN → 2B line → payout → book entry           │
│ append-only Verdict + AuditEvent. models.py. THIS IS THE ASSET.   │
└───────────────────────────────────────────────────────────────────┘
```

## Layer 1 — the data model (`app/models.py`)

- **Claim** — the money-pipeline view (employee, amount, category, tier, EV score).
- **Invoice** — the tax-pipeline view (supplier GSTIN, invoice no, tax split, **buyer GSTIN** — the join test), plus extraction confidence + method.
- **Verdict** — *append-only*. decision, `rule_ids[] + rule_versions[]`, reason code, predicted P, reasoning. Never updated; re-evaluation inserts a new row, so history is intact.
- **Vendor** — the moat. filing frequency, reliability score, observation count. Updated free from every 2B statement.
- **TwoBLine** — a line from GSTR-2B; `matched_claim_id` is the free supervised label.
- **Payout** — idempotency key mandatory; status machine including `TIMEOUT`/`RECONCILED`.
- **AuditEvent** — *append-only*. Every verdict and money action is reconstructible from this log.

`matched_claim_id` is the whole trick: every month reality tells us whether each prediction was right, on every transaction, forever. Nobody in India has this dataset because nobody stitches the two pipelines.

## Layer 2 — the agent loop (`app/pipeline.py`)

For each claim: `extract_invoice` → assign a triage band by tax at stake → (only if high-value) a live GSP call to validate registration → `evaluate` the deterministic rules → `predict_recoverability` (advisory) → persist the verdict + an audit event.

**Triage math** (`triage.py`):

```
expected_value = tax_at_stake × P(recoverable) − cost_to_process
tier_0  tax < ₹200                    → auto-approve, 0 live calls
tier_1  ₹200–₹2,000                   → our cached vendor data only (free)
tier_2  > ₹2,000                      → live GSP validation
tier_3  > ₹2,000 AND P < 0.5          → intervene: chase / draft vendor request
```

The agent's real job is deciding *which claims deserve attention*, not reading receipts. Result: 0.06 live GSP calls per claim.

## Layer 3 — bounded actions (`app/actions.py`)

Payouts are idempotent at the ledger, not just the API — the key is `payout_<claim_id>`, so a retry, a re-run, or a double-click cannot pay twice. A tax problem is the company's problem, so wrong-entity/blocked claims are still paid on time; only `DUPLICATE_CLAIM` and `ARITHMETIC_MISMATCH` (which affect the reimbursement's legitimacy) hold payment for review.

## The Dynamic Compliance Engine

```
GST sources → [Change Detection] → [Rule Diff Proposal] → [Human/CA Approval Gate]
            → [Rule Registry vN+1] → [Re-evaluation of affected history]
```

Detection is autonomous and cheap; *application* is gated behind human approval — the guardrail that stops an LLM's reading of a circular from generating wrong ITC at scale. Because verdicts cite `rule_id + version` and the table is append-only, a version bump can re-run history and report exactly which past claims changed (see the "Simulate a GST rule change" control).

## Where the LLM lives (and where it doesn't)

Gemini (`llm.py`) powers exactly the three jobs the PRD earmarks for an LLM, each with a non-LLM fallback so the system runs without a key:

- **Read a receipt image → structured fields** (`tools/extract.py`) — vision; schema-validated, one retry, then fall back to the deterministic path. Never guesses a GSTIN.
- **Draft a vendor reissue / filing request** (`drafting.py`) — Hinglish + English; template fallback.
- **Propose a rule diff from a GST advisory** (`compliance.py`) — into the review queue only; a human approves before it goes live.

It is never on the path that decides eligibility or moves money.

## Multi-state / place of supply — built (a documented change of mind)

**This started in "architected for, not built." That call was wrong, and we changed it deliberately.** While hardening the demo's opening story we found the actual rule: hotel accommodation's *place of supply* is the hotel's state (s.12(3), IGST Act; CBIC 2019 clarification; multiple AAR rulings), and GST registration is state-wise. So a Mumbai hotel bill is Maharashtra CGST+SGST — a Karnataka-only company can't claim it *even if the invoice is perfect*. That isn't an edge case; it's the centre of the domain. Leaving multi-state out would have made the whole "we understand GST, not just the workflow" claim hollow.

So the company is now a **list of `CompanyRegistration`s** (Karnataka + Maharashtra), and the deterministic engine carries two new state-aware rules (`POS_STATE_REGISTERED` → `STATE_TRAPPED`, `POS_CORRECT_GSTIN` → the *fixable* `WRONG_GSTIN_USED`), plus `RECOVERABLE_IGST` for supplies that follow the recipient. The place of supply comes free from the first two digits of the supplier GSTIN — no API call. This turned "two fates" (recoverable / not) into **three** (recoverable / structurally dead / already overclaimed), and unlocked the overclaim scanner and registration-ROI report. The rule that an LLM never touches this path is unchanged.

Showing you promoted a P2 item *because you found the actual law* reads better than a doc that happened to be right.

## P2 — still architected for, deliberately not built

**Booking-moment routing** (intervening at the hotel counter, not at claim submission — the GSTIN picker at `/api/gstin-picker` is the read-only half of this; the write half is real-time capture), **corporate-card real-time capture**, **cross-customer vendor-graph federation** (the `Vendor` table is already the shared moat, single-tenant for now), and **ERP write-back** (Tally / Zoho Books — the ledger is the clean source for it). Each has a seam in the code or data model; none is faked in the demo.

## What runs where

Backend: FastAPI + `uv` + SQLModel over SQLite (file-based — zero services to run), `rich` for the narrated backend log. Frontend: Vite + React + TypeScript + Tailwind + Recharts. Integrations (GSP, RazorpayX, VLM extraction) are mocks with clearly-marked slots for live keys.
