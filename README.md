# CreditLoop

**The GST you're losing — and the GST you shouldn't have claimed.**

CreditLoop is an AI finance agent that sorts the GST on every employee expense into three fates — recoverable, structurally dead, or already overclaimed — and decides *before* the money moves.

Razorpay AI Buildathon 2026 · Track 04 (AI Finance Controller).

![Landing](docs/screenshots/landing.png)

---

## What is this, in plain words?

Priya travels to Mumbai for a client meeting. Hotel bill: ₹10,000 + ₹1,800 GST. She does **everything right** — bill in the company's name, correct GSTIN, hotel files its return on time.

**The ₹1,800 is still dead.** Hotels charge the GST of the state they stand in. Your company is registered in Karnataka. That's *Maharashtra* tax, and a Karnataka registration can't touch it (place of supply = the hotel's state, s.12(3) IGST Act; registration is state-wise).

Your finance team knows this rule. What they can't do is apply it to 3,000 claims a year, one line at a time, before the money moves. So the ₹1,800 got claimed anyway — along with ₹47,000 of others like it. **That's not lost money. That's money you owe back, with 24% interest.**

> **We're not smarter than your CA.** A CA answers "can I claim a Mumbai hotel from a Karnataka registration?" in two seconds. The gap isn't knowledge — it's **coverage** (every line, not a sample), **the join** (claim ↔ 2B), **timing** (verdict *before* payout), and **memory** (400 vendors' filing behaviour). *"You already know the answer. We apply it to every line, on time, and we remember."*

So there are **three fates**, not two, and every existing tool only thinks about the first:

| Fate | Meaning | What CreditLoop does |
|---|---|---|
| **Recoverable** | Credit is yours (or becomes yours once a wrong-GSTIN mistake is fixed) | Claim it; chase the vendor if unfiled |
| **Structurally dead** | Credit never existed (out-of-state hotel, blocked u/s 17(5)) | Stop chasing. Book as cost. **Don't claim.** |
| **Overclaim risk** | You already claimed dead credit | Flag it, quantify the interest, reverse it |

**CreditLoop is the layer that knows the difference** — and it decides before the payout, where it's still fixable. The place of supply comes free from the first two digits of the supplier's GSTIN; no API call.

---

## See it working

The dashboard shows one number that exists nowhere else in an Indian finance stack: **₹ recovered vs ₹ lost**, for a batch of claims, before a rupee moves.

![Dashboard](docs/screenshots/dashboard.png)

Click any claim for the full trail — the receipt, the extracted invoice, the verdict with the exact rule it cited, the payout, the 2B match, and a one-click **vendor reissue request** (in English or Hinglish):

![Claim detail](docs/screenshots/claim.png)

Honest, measured results — including a live calibration curve and the exception list as a *feature*:

![Metrics](docs/screenshots/metrics.png)

And a **Dynamic Compliance Engine**: an agent reads GST advisories and *drafts* a rule change; a human approves before anything goes live, then history recomputes:

![Compliance](docs/screenshots/compliance.png)

---

## The loop, in three steps

| | |
|---|---|
| **1 · Read the receipt** | A vision model pulls GSTIN, invoice number and tax split off a crumpled photo — and *refuses to guess* when it can't read one. |
| **2 · Judge with the law** | A deterministic engine (never an LLM) decides eligibility, citing the exact rule + version. Wrong-entity, blocked, or recoverable — before payout. |
| **3 · Chase · pay · reconcile** | Pay on time, chase the vendor while it's still fixable, then match against GSTR-2B. Every rupee has an audit trail. |

The one architectural rule everything hangs on: **an LLM may never change a tax verdict or move money.** It reads, drafts, and proposes; the deterministic engine decides. (Wrong ITC carries 24% interest + penalties — "the AI decided" is not a defence.) Details in [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Run it

```bash
make install     # backend (uv) + frontend (npm)
make dev         # API on :8137 + dashboard on :5173  →  open http://localhost:5173
```

Or the whole loop in your terminal, no browser:

```bash
make demo
```

Nothing external is required — GST provider and payouts run on honest mocks, receipt reading uses a synthetic-truth mode. It all works out of the box; adding an API key (below) makes the AI real.

Try the failure modes (also buttons in the dashboard):

```bash
make -C backend fail-payout   # inject a payout timeout → auto-reconcile, never double-pay
make -C backend gsp-down      # GST provider offline → verdicts degrade to PROVISIONAL, payouts still run
```

---

## Turning on the real AI (Gemini)

Receipt reading needs a *vision* model. **Use Google Gemini** — its Flash models read images on the free tier, and one key powers all three AI jobs (reading receipts, drafting vendor messages, proposing rule changes). *(Cerebras only added vision on one model in private preview, so it can't reliably read receipts yet.)*

1. Get a free key at **https://aistudio.google.com/apikey**
2. `cp backend/.env.example backend/.env` and set `CREDITLOOP_GEMINI_API_KEY=...`
3. Restart. The header flips from **"AI: synthetic"** to **"AI: gemini-2.5-flash"**, vendor drafts become AI-written, and you can measure real extraction accuracy:

```bash
curl -X POST localhost:8137/api/eval/extraction   # scores Gemini's receipt reading vs ground truth
```

Without a key, everything still runs — receipts use ground-truth, drafts use good templates.

---

## Deploy

It's a **single service**: FastAPI serves the API *and* the built dashboard, so you deploy one thing.

```bash
cd frontend && npm run build      # produces frontend/dist
cd ../backend && uv run uvicorn app.api:app --host 0.0.0.0 --port 8137
```

`http://your-host:8137/` then serves the landing page **and** the app.

### Should I use Vercel?

**Short answer: no — use Render, Railway, or Fly.** CreditLoop's backend is a stateful Python server (SQLite + it runs the pipeline on boot). Vercel is built for stateless serverless functions and a static frontend, so it's a poor fit for the backend. Two clean options:

- **✅ Recommended — one container on Render / Railway / Fly / Cloud Run.** The repo ships a **`Dockerfile`** (builds the SPA + backend into one image) and a **`render.yaml`** blueprint. On Render: *New → Blueprint → pick this repo* and it deploys everything on one URL. On first boot it creates the SQLite DB and runs the loop once, so the dashboard is populated immediately. Set `CREDITLOOP_GEMINI_API_KEY` in the dashboard to turn on real AI.
- **Split (if you insist on Vercel):** put the **frontend on Vercel** (`root = frontend`, build `npm run build`, output `dist`) and the **backend on Render/Railway**. Then set an env var `VITE_API_BASE=https://your-backend-url` on the Vercel project so the SPA calls the backend. CORS is already open. This works but is two services to manage instead of one.

### Do I need anything else to deploy?

- **Login (Clerk / Supabase)? — No.** For the buildathon, keep it open so judges try it instantly. The app is built login-free. If you later want to gate it, Clerk is a ~10-minute drop-in around the `/app` route — but you don't need it now, and no code here depends on it.
- **Razorpay keys? — No, not to run.** Payouts use a safe mock. Only if you want *real* RazorpayX test-mode payout calls do you set `CREDITLOOP_RAZORPAY_KEY_ID/SECRET` (+ a test fund account) in `.env`; it falls back to mock on any error.
- **Gemini key? — Optional but recommended** (see above) to make the AI real.
- **A database? — No.** It's file-based SQLite; the Docker image is self-contained.

---

## Measured results (200-claim batch, seed 42 — regenerate with `make demo`)

| Metric | Value |
|---|---|
| **2B match rate** | **100%** (60/60 lines) |
| Deterministic engine accuracy | **100%** (vs ground truth — see the honest caveat in WHATBROKE.md) |
| Decision accuracy under triage | 97.5% |
| Section 17(5) precision / recall | 100% / 100% |
| **STATE_TRAPPED precision / recall** | **100% / 100%** (over-flagging costs real credits) |
| **Overclaim exposure identified** | **₹8,311** (16 claims, +₹1,995/yr interest) |
| Calibration (ECE) | **0.069** (was 0.13; see WHATBROKE.md) |
| False-block rate | **0 claims / ₹0** |
| Exception rate | 17.5% (35 claims, each with a machine reason code) |
| Live GST-provider calls / claim | 0.10 |

**Honest points for the panel:** the exception rate is a *feature* (an agent that always decides is guessing); "engine accuracy 100%" measures implementation correctness, not legal judgment, since it's graded against ground truth from the same rules — so trust the *not*-self-graded numbers (match rate, calibration, real VLM extraction); and the place-of-supply logic is CA-reviewable (verified against s.12, the CBIC 2019 clarification, and AAR rulings, but a domain expert should sign off before it's called authoritative).

---

## Repo layout

```
backend/    FastAPI + uv + SQLModel/SQLite
  app/
    models.py        the append-only ledger (the join)
    engine.py        deterministic verdicts — pure, no LLM
    rule_registry.py versioned rules as DATA, cited in every verdict
    predict.py       calibrated recoverability (advisory)
    triage.py        expected-value triage (spend calls only where they matter)
    pipeline.py      the agent loop
    actions.py       idempotent payouts (impossible to double-pay)
    reconcile.py     2B matching + the vendor-reliability learning loop
    metrics.py       the eval harness
    compliance.py    Dynamic Compliance Engine (detect → propose → approve)
    drafting.py      vendor reissue / filing requests (Hinglish + English)
    llm.py           Gemini provider (vision + text), graceful fallback
    synthetic.py     the 200-claim generator (published, so you can check us)
    tools/           extract (VLM), gsp (mock), razorpay (mock + real test)
frontend/   Vite + React + TS + Tailwind + Recharts (landing + dashboard)
```

## More

- [ARCHITECTURE.md](ARCHITECTURE.md) — the three layers and why deterministic ≠ learned.
- [WHATBROKE.md](WHATBROKE.md) — honest bugs and what's still mock, not real.
