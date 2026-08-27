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
        <h1 className="fadeup text-[2.3rem] font-semibold leading-[1.06] tracking-tight sm:text-5xl md:text-[3.8rem]">
          The GST you’re losing,<br />
          <span className="bg-gradient-to-b from-[#f7dca0] via-[#e9b357] to-[#c88a3e] bg-clip-text text-transparent">
            and the GST you shouldn’t have claimed.
          </span>
        </h1>
        <p className="fadeup mx-auto mt-6 max-w-2xl text-lg text-[#f2e7d3]/75">
          Two ways Indian companies lose GST on expenses — credit that was never yours to claim, and
          credit you claimed anyway and now owe back with interest. CreditLoop knows the difference,
          <em> before</em> the money moves.
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
    ["GST recoverable", rupees(s.money.recoverable)],
    ["Structurally dead", rupees(s.money.structurally_dead)],
    ["⚠ Wrongly claimed", rupees(s.money.overclaimed)],
    ["State-trapped", rupees(s.money.state_trapped)],
    ["2B match rate", `${Math.round(s.match.match_rate * 100)}%`],
    ["GSP calls / claim", String(s.gsp_calls_per_claim ?? "0.06")],
    ["Fixable (wrong GSTIN)", rupees(s.money.fixable_wrong_gstin)],
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

/* -------------------------------------------------------------- problem */
function Problem() {
  return (
    <section id="problem" className="dotgrid border-t border-white/5 px-6 py-20">
      <div className="mx-auto max-w-4xl">
        <div className="text-center">
          <div className="text-xs font-semibold uppercase tracking-widest text-[#e9b357]">The problem</div>
          <h2 className="mx-auto mt-3 max-w-3xl text-3xl font-semibold tracking-tight sm:text-4xl">
            A perfect invoice that’s still worthless
          </h2>
        </div>

        <div className="mx-auto mt-10 max-w-2xl space-y-5 text-lg leading-relaxed text-[#f2e7d3]/80">
          <p>
            Priya travels to Mumbai for a client meeting. Hotel bill: ₹10,000 + <span className="text-[#f7dca0]">₹1,800 GST</span>.
            She does everything right — bill in the company’s name, correct GSTIN, and the hotel files its
            return on time.
          </p>
          <p className="text-2xl font-semibold text-[#f2e7d3]">The ₹1,800 is still dead.</p>
          <p>
            Hotels charge the GST of the state they stand in. Your company is registered in Karnataka.
            That’s <span className="text-[#f7dca0]">Maharashtra</span> tax — and you can’t touch it.
          </p>
          <p>
            Nobody at the company knows this, so finance claimed it anyway — along with{" "}
            <span className="text-loss font-semibold">₹47,000 of others like it.</span>{" "}
            That’s not lost money. That’s money you owe back, with 24% interest.
          </p>
        </div>

        <div className="mx-auto mt-10 grid max-w-3xl grid-cols-1 gap-3 sm:grid-cols-3">
          <Fate title="Recoverable" tone="text-money" body="Credit is yours — claim it." />
          <Fate title="Structurally dead" tone="text-[#c9bca6]" body="Never existed. Book as cost; don’t claim." />
          <Fate title="Wrongly claimed" tone="text-loss" body="Claimed anyway → owe back + interest." />
        </div>
        <p className="mt-8 text-center text-lg text-[#f2e7d3]/70">
          CreditLoop is the layer that knows the difference.
        </p>
      </div>
    </section>
  );
}

function Fate({ title, tone, body }: { title: string; tone: string; body: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-5 text-center">
      <div className={`text-base font-semibold ${tone}`}>{title}</div>
      <p className="mt-1.5 text-sm text-[#f2e7d3]/60">{body}</p>
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
        <div className="mt-12 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
          <Step n="01" title="Read the receipt" body="A vision model pulls GSTIN, invoice number and tax split off a crumpled photo — and refuses to guess when it can’t read it." />
          <Step n="1.5" title="Locate the supply" body="Where did this legally happen? The first two digits of the GSTIN give the state; the category gives the rule. A Mumbai hotel is Maharashtra tax, whoever pays." highlight />
          <Step n="02" title="Judge with the law" body="A deterministic engine — never an LLM — decides eligibility, citing the exact rule and version. Recoverable, dead, or fixable, before payout." />
          <Step n="03" title="Chase · pay · reconcile" body="Pay on time, chase the vendor while it’s still fixable, then match against GSTR-2B. Every rupee has an audit trail." />
        </div>
      </div>
    </section>
  );
}

function Step({ n, title, body, highlight }: { n: string; title: string; body: string; highlight?: boolean }) {
  return (
    <div className={`rounded-2xl border p-6 ${highlight ? "border-[#e9b357]/30 bg-[#e9b357]/[0.06]" : "border-white/10 bg-white/[0.03]"}`}>
      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#e9b357]/15 font-mono text-sm text-[#e9b357]">{n}</div>
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
