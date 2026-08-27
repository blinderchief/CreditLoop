# What broke

The application asks for this explicitly, so here it is — specific and unflattering.

## Bugs we hit and fixed

**0. The opening story was right for the wrong reason.**
v1 said Priya's hotel GST dies because the bill was in her personal name. True conclusion, wrong mechanism — and checkable in thirty seconds by anyone who knows GST. The real rule: hotel accommodation's *place of supply* is the hotel's state (s.12(3), IGST Act), and registration is state-wise, so a Mumbai hotel is Maharashtra CGST+SGST that a Karnataka-only company can't claim *even with a perfect invoice*. We didn't quietly patch the README; we made the state trap the headline, built the multi-state engine behind it (`STATE_TRAPPED`, the fixable `WRONG_GSTIN_USED`, `RECOVERABLE_IGST`), and it made the product sharper — it surfaced a whole third failure mode: credit you already *overclaimed* and now owe back with interest. Having the right conclusion for the wrong reason, finding the actual law, and letting it improve the product is the most useful thing on this page.

**1. The synthetic data lied to the engine (81.5% → 100%).**
First end-to-end run, the deterministic engine "disagreed" with ground truth on 37/200 claims. Every single mismatch was a **generator bug**, not an engine bug: `clean_compliant` claims were being assigned QRMP vendors (so the engine correctly said `PENDING_QRMP` while the label said `RECOVERABLE`); "clean" claims were landing on the `meals` category (correctly `BLOCKED_17_5`); wrong-entity claims were drawing inactive vendors, so `GSTIN_NOT_ACTIVE` fired before the entity check. Fix: each scenario now isolates exactly one failure — active suppliers everywhere except the inactive scenario, no meals on recoverable scenarios, and the archetype filter can't resurrect an inactive vendor. Lesson: when the model and the labels disagree, suspect the labels first.

**2. Match rate looked terrible (71%) for a good reason.**
The reconciler only tried to link *recoverable* claims to 2B lines — but a blocked invoice can still physically appear in the 2B. 14 lines went unmatched not because matching failed but because we never attempted them. Split the two axes: match *every* claim's invoice to its line (matching quality → 100%), track recoverability separately.

**3. Calibration was off (ECE 0.16) because we were cheap in the wrong place.**
Cheap claims fell back to a flat P=0.7 prior, so a bucket of "0.72-predicted" claims mixed vendors whose true rates ran 0.05–0.99. The fix was conceptual, not numerical: reading our *own* vendor-reliability table is free (it's the moat, not an external GSP call), so tier-1 claims now predict from real vendor history. Only the live registration-status check costs a call. ECE dropped to 0.126 — still mediocre. Two further fixes brought it to **0.069**: forcing P=0 on structurally-dead verdicts (state-trapped / blocked / wrong-entity credits can't appear in our 2B, so a non-zero prediction there was pure noise), and P≈0.1 on the fixable `WRONG_GSTIN_USED` (recoverable, but not until it's reissued). We're calling the number out ourselves rather than letting a judge find a soft 0.13.

**4. The rule-version bump didn't propagate.**
The engine bound the rule registry at import time, so a version bump saved to disk but new verdicts still cited the old version, and repeated bumps compounded. Made the registry a dynamic lookup with an explicit reset-to-baseline, so "the law moved, recompute history" is correct and repeatable.

**5. SQLModel detached instances.**
`expire_on_commit` defaulted true, so reading an ORM object after the session closed threw `DetachedInstanceError` in the report code. Set `expire_on_commit=False`.

## What is honestly not real yet

- **"Engine accuracy 100%" is close to tautological — we say so.** The deterministic engine is graded against ground truth generated from the same rules it applies, so 100% measures *implementation correctness*, not legal judgment. The place-of-supply logic made the test genuinely harder (a perfect-looking invoice can still be `STATE_TRAPPED`), and it still holds — but the honest reading is "the code faithfully applies the law we encoded," and the law itself needs a CA to vet. The numbers that aren't self-graded — 2B match rate, calibration, real VLM extraction — are the ones to trust.
- **Extraction is real *if you add a key*, synthetic otherwise.** With `CREDITLOOP_GEMINI_API_KEY` set, receipts are read by Gemini vision and `POST /api/eval/extraction` scores it per-field against ground truth. With no key it's synthetic-truth, where "100%" is true *by construction* and clearly labelled as such in the UI (`100%*`). We refuse to show a real-looking extraction number that isn't.
- **GSP and RazorpayX are mocks by default.** RazorpayX has a real test-mode path behind an env flag (`tools/razorpay.py`), but the GST provider (GSP) is still a mock with recorded behaviour — a labelled mock beats a broken live integration for a demo. Real GSP access needs a sandbox account (Sandbox.co.in / MasterGST), which is the day-1 blocker the PRD calls out.
- **The vendor graph is single-customer.** The compounding-moat argument is real but unproven until multiple customers share vendors.
- **The pre-spend trigger is unbuilt.** v1 intervenes at claim *submission*, which is already late — the money died at the hotel counter. Booking-moment routing is the real answer and it is explicitly out of scope for v1. We are not pretending otherwise.
- **The hardest input is a person, not a model.** This is a compliance-depth product. A CA who will take the calls matters more than the AI, and we don't have one on the team yet.
