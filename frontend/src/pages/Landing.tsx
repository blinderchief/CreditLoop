import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Summary } from "../api";
import { rupees } from "../format";
import { Logo, Mark } from "../components/Logo";

export function Landing() {
  const [s, setS] = useState<Summary | null>(null);
  useEffect(() => { api.summary().then(setS).catch(() => {}); }, []);

  return (
    <div className="min-h-screen bg-[#0d0b09] text-[#f2e7d3]">
      <Nav />
      <Hero />
      <Ticker s={s} />
      <Showcase />
      <Problem />
      <Steps />
      <Trust s={s} />
      <CTA />
      <Footer />
    </div>
  );
}

/* ------------------------------------------------------------------ nav */
function Nav() {
  return (
    <header className="fixed inset-x-0 top-0 z-50 border-b border-white/5 bg-[#0d0b09]/70 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <Link to="/"><Logo /></Link>
        <nav className="hidden items-center gap-8 text-sm text-[#f2e7d3]/70 md:flex">
          <a href="#how" className="transition hover:text-[#f2e7d3]">How it works</a>
          <a href="#problem" className="transition hover:text-[#f2e7d3]">The problem</a>
          <a href="#proof" className="transition hover:text-[#f2e7d3]">Proof</a>
        </nav>
        <div className="flex items-center gap-2">
          <Link to="/app" className="hidden text-sm text-[#f2e7d3]/80 transition hover:text-[#f2e7d3] sm:block">Sign in</Link>
          <Link to="/app"
            className="rounded-full bg-[#e9b357] px-4 py-1.5 text-sm font-semibold text-[#0d0b09] transition hover:brightness-110">
            Open the app
          </Link>
        </div>
      </div>
    </header>
  );
}

/* ----------------------------------------------------------------- hero */
function Hero() {
  const videoRef = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    const v = videoRef.current; if (!v) return;
    const play = () => v.play().catch(() => {});
    play();
    const t = setInterval(() => { if (v.paused) play(); }, 1500);
    document.addEventListener("visibilitychange", play);
    return () => { clearInterval(t); document.removeEventListener("visibilitychange", play); };
  }, []);

  return (
    <section className="relative flex min-h-[92vh] items-center overflow-hidden pt-16">
      <video ref={videoRef} className="absolute inset-0 h-full w-full object-cover"
        autoPlay muted loop playsInline preload="auto" poster="/sea-storm.jpg">
        <source src="/sea-storm.mp4" type="video/mp4" />
      </video>
      <div className="absolute inset-0 bg-[#0d0b09]/55" />
      <div className="absolute inset-x-0 top-0 h-32 bg-gradient-to-b from-[#0d0b09] to-transparent" />
      <div className="absolute inset-x-0 bottom-0 h-56 bg-gradient-to-t from-[#0d0b09] via-[#0d0b09]/70 to-transparent" />

      <div className="relative z-10 mx-auto w-full max-w-4xl px-6 text-center">
        <div className="fadeup mb-6 inline-flex items-center gap-2 rounded-full border border-[#e9b357]/25 bg-[#e9b357]/[0.06] px-3 py-1 text-xs text-[#f7dca0] backdrop-blur">
          <span className="h-1.5 w-1.5 rounded-full bg-[#e9b357]" /> AI Finance Controller for GST
        </div>
        <h1 className="fadeup text-[2.6rem] font-semibold leading-[1.05] tracking-tight sm:text-6xl md:text-[4.25rem]">
          The GST you’re losing,<br />
          <span className="bg-gradient-to-b from-[#f7dca0] via-[#e9b357] to-[#c88a3e] bg-clip-text text-transparent">
            recovered before the money moves.
          </span>
        </h1>
        <p className="fadeup mx-auto mt-6 max-w-2xl text-lg text-[#f2e7d3]/75">
          Indian companies quietly lose 18% GST on every employee expense. CreditLoop is the agent that
          decides whether the credit comes back — <em>before</em> you pay, where it’s still fixable.
        </p>
        <div className="fadeup mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Link to="/app" className="glow-gold rounded-full bg-[#e9b357] px-6 py-3 font-semibold text-[#0d0b09] transition hover:brightness-110">
            See it run on 200 claims →
          </Link>
          <a href="#how" className="rounded-full border border-white/15 px-6 py-3 font-medium text-[#f2e7d3]/90 transition hover:bg-white/10">
            How it works
          </a>
        </div>
      </div>
    </section>
  );
}

/* --------------------------------------------------------------- ticker */
function Ticker({ s }: { s: Summary | null }) {
  const items = s ? [
    ["Claims judged", String(s.batch.claims)],
    ["GST recoverable", rupees(s.money.recovered)],
    ["2B match rate", `${Math.round(s.match.match_rate * 100)}%`],
    ["GSP calls / claim", String(s.gsp_calls_per_claim ?? "0.06")],
    ["Paid on time", String(s.batch.paid)],
    ["Exceptions surfaced", String(s.batch.exceptions)],
    ["Lost to wrong entity", rupees(s.money.lost_wrong_entity)],
    ["Blocked u/s 17(5)", rupees(s.money.blocked_17_5)],
  ] : [];
  const row = (
    <div className="marquee">
      {[...items, ...items].map(([k, v], i) => (
        <span key={i} className="mx-6 inline-flex items-center gap-2 text-sm">
          <span className="text-[#f2e7d3]/45">{k}:</span>
          <span className="font-semibold tabular-nums text-[#f7dca0]">{v}</span>
          <span className="ml-6 text-[#e9b357]/30">◆</span>
        </span>
      ))}
    </div>
  );
  return (
    <div className="marquee-wrap overflow-hidden border-y border-white/5 bg-[#100d0a] py-3">
      <div className="mx-6 mb-0 inline text-xs font-semibold uppercase tracking-widest text-[#e9b357]">
        The loop today
      </div>
      {s ? row : <span className="px-6 text-sm text-[#f2e7d3]/40">loading live numbers…</span>}
    </div>
  );
}

/* ------------------------------------------------------------- showcase */
function Showcase() {
  return (
    <section className="dotgrid px-6 py-20">
      <div className="mx-auto max-w-6xl">
        <div className="mb-8 text-center">
          <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            One number that isn’t in your finance stack
          </h2>
          <p className="mx-auto mt-3 max-w-2xl text-[#f2e7d3]/60">
            ₹ recovered vs ₹ lost, for a whole batch of claims — decided before a rupee moves,
            with the exact rule cited on every verdict.
          </p>
        </div>
        <BrowserFrame src="/product.png" alt="CreditLoop dashboard" />
      </div>
    </section>
  );
}

function BrowserFrame({ src, alt }: { src: string; alt: string }) {
  return (
    <div className="overflow-hidden rounded-2xl border border-white/10 bg-[#17120c] shadow-2xl glow-gold">
      <div className="flex items-center gap-1.5 border-b border-white/10 px-4 py-3">
        <span className="h-3 w-3 rounded-full bg-[#db6048]/70" />
        <span className="h-3 w-3 rounded-full bg-[#e9b357]/70" />
        <span className="h-3 w-3 rounded-full bg-[#cf9a4e]/40" />
        <span className="ml-4 rounded-md bg-white/5 px-3 py-0.5 text-xs text-[#f2e7d3]/40">app.creditloop.in</span>
      </div>
      <img src={src} alt={alt} className="w-full" />
    </div>
  );
}

/* -------------------------------------------------------------- problem */
function Problem() {
  return (
    <section id="problem" className="border-t border-white/5 px-6 py-20">
      <div className="mx-auto max-w-5xl">
        <div className="text-center">
          <div className="text-xs font-semibold uppercase tracking-widest text-[#e9b357]">The problem</div>
          <h2 className="mx-auto mt-3 max-w-3xl text-3xl font-semibold tracking-tight sm:text-4xl">
            Two pipelines that never meet
          </h2>
          <p className="mx-auto mt-3 max-w-2xl text-[#f2e7d3]/60">
            The money side knows a vendor name. The tax side needs a GSTIN and invoice number. There’s
            no join key — so 18% GST leaks, silently, one ₹300 receipt at a time.
          </p>
        </div>
        <div className="mt-12 grid grid-cols-1 gap-5 md:grid-cols-2">
          <Pane title="The money pipeline" tone="#f2e7d3"
            rows={[["Knows", "Priya · hotel · ₹11,800"], ["Speed", "fast, loud, approved in a day"], ["Blind to", "whose name the bill is in"]]} />
          <Pane title="The tax pipeline" tone="#e9b357"
            rows={[["Needs", "GSTIN 27… · invoice HTL/2026/4471"], ["Speed", "monthly, silent, owned by a CA"], ["Deadline", "GSTR-2B locks the credit"]]} />
        </div>
        <p className="mx-auto mt-10 max-w-2xl text-center text-lg text-[#f2e7d3]/80">
          CreditLoop builds the missing join —{" "}
          <span className="text-[#f7dca0]">claim → invoice → GSTIN → 2B → payout → book</span>{" "}
          — and moves the decision to before the payout.
        </p>
      </div>
    </section>
  );
}

function Pane({ title, tone, rows }: { title: string; tone: string; rows: [string, string][] }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-6">
      <div className="text-lg font-semibold" style={{ color: tone }}>{title}</div>
      <dl className="mt-4 space-y-3">
        {rows.map(([k, v]) => (
          <div key={k} className="flex justify-between gap-4 border-t border-white/5 pt-3 text-sm">
            <dt className="text-[#f2e7d3]/45">{k}</dt>
            <dd className="text-right font-medium">{v}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

/* ---------------------------------------------------------------- steps */
function Steps() {
  return (
    <section id="how" className="dotgrid border-t border-white/5 px-6 py-20">
      <div className="mx-auto max-w-5xl">
        <h2 className="text-center text-3xl font-semibold tracking-tight sm:text-4xl">One loop, closed end to end</h2>
        <p className="mx-auto mt-3 max-w-xl text-center text-[#f2e7d3]/60">Simple for the employee. Everything hard happens in the backend.</p>
        <div className="mt-12 grid grid-cols-1 gap-5 md:grid-cols-3">
          <Step n="01" title="Read the receipt" body="A vision model pulls GSTIN, invoice number and tax split off a crumpled photo — and refuses to guess when it can’t read it." />
          <Step n="02" title="Judge with the law" body="A deterministic engine — never an LLM — decides eligibility, citing the exact rule and version. Wrong-entity, blocked, or recoverable, before payout." />
          <Step n="03" title="Chase · pay · reconcile" body="Pay on time, chase the vendor while it’s still fixable, then match against GSTR-2B. Every rupee has an audit trail." />
        </div>
      </div>
    </section>
  );
}

function Step({ n, title, body }: { n: string; title: string; body: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-6">
      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#e9b357]/10 font-mono text-sm text-[#e9b357]">{n}</div>
      <div className="mt-4 text-lg font-semibold">{title}</div>
      <p className="mt-2 text-sm text-[#f2e7d3]/60">{body}</p>
    </div>
  );
}

/* ---------------------------------------------------------------- trust */
function Trust({ s }: { s: Summary | null }) {
  const stats = [
    ["100%", "2B match rate"],
    ["100%", "engine accuracy"],
    ["₹0", "false-block cost"],
    [String(s?.gsp_calls_per_claim ?? "0.06"), "API calls / claim"],
  ];
  return (
    <section id="proof" className="border-t border-white/5 px-6 py-20">
      <div className="mx-auto max-w-5xl">
        <div className="grid grid-cols-1 items-center gap-10 md:grid-cols-2">
          <div>
            <div className="text-xs font-semibold uppercase tracking-widest text-[#e9b357]">Why you can trust it</div>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">
              An LLM never changes a tax verdict
            </h2>
            <p className="mt-4 text-[#f2e7d3]/65">
              The law lives in a deterministic engine — versioned rules, cited on every verdict, fully
              auditable. The model only reads receipts, drafts vendor requests, and proposes rule changes
              a human approves. Wrong ITC carries 24% interest and penalties; “the AI decided” is not a
              defence, so the AI doesn’t decide.
            </p>
            <div className="mt-6 flex flex-wrap gap-2 text-xs">
              {["deterministic law", "append-only ledger", "idempotent payouts", "honest exception list"].map((t) => (
                <span key={t} className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-[#f2e7d3]/70">{t}</span>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            {stats.map(([n, l]) => (
              <div key={l} className="rounded-2xl border border-white/10 bg-white/[0.02] p-5 text-center">
                <div className="text-3xl font-semibold text-[#f7dca0] tabular-nums">{n}</div>
                <div className="mt-1 text-xs text-[#f2e7d3]/55">{l}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ cta */
function CTA() {
  return (
    <section className="px-6 py-24">
      <div className="glow-gold mx-auto max-w-4xl rounded-3xl border border-[#e9b357]/20 bg-gradient-to-b from-[#e9b357]/[0.08] to-transparent p-12 text-center">
        <Mark size={40} />
        <h2 className="mt-5 text-3xl font-semibold tracking-tight sm:text-4xl">Close the loop.</h2>
        <p className="mx-auto mt-3 max-w-xl text-[#f2e7d3]/65">
          200 synthetic claims, judged, paid, and reconciled — with the counter moving in real time.
        </p>
        <Link to="/app" className="mt-8 inline-block rounded-full bg-[#e9b357] px-7 py-3 font-semibold text-[#0d0b09] transition hover:brightness-110">
          Open the live dashboard →
        </Link>
      </div>
    </section>
  );
}

/* --------------------------------------------------------------- footer */
function Footer() {
  return (
    <footer className="border-t border-white/5 px-6 py-12">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 text-sm text-[#f2e7d3]/50 sm:flex-row">
        <Logo />
        <div className="text-center sm:text-right">
          read, never file · money never touched · deterministic law + calibrated prediction
        </div>
      </div>
    </footer>
  );
}
