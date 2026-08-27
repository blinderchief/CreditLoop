"""Synthetic dataset generator (PRD section 14).

Builds a deliberately HARD batch so the metrics mean something:
  * 40 vendors: 10 compliant, 10 QRMP-with-lag, 10 erratic, 10 never-file
  * 200 claims across 8 categories
  * ~30% invoices in the employee's personal name (wrong entity)
  * ~15% missing GSTIN, ~10% blocked u/s 17(5)
  * arithmetic that doesn't add up, duplicates, an inactive GSTIN, an invalid
    checksum, unreadable receipts, and a 2B line whose amount mismatches
  * a ground-truth GSTR-2B statement generated FROM vendor filing behaviour,
    so match rate is objectively measurable

Every claim is tagged with the scenario that produced it and its ground-truth
label is written to data/ground_truth.json — a reviewer can regenerate the set
and check our numbers. Publish the generator; trust follows.
"""

from __future__ import annotations

import json
import random
from datetime import date, datetime, timedelta, timezone

from .config import settings
from .db import get_session, reset_db
from .domain import (
    ExpenseCategory,
    ExtractionMethod,
    FilingFrequency,
    POS_BY_CATEGORY,
    PlaceOfSupply,
)
from .gstin import make_valid_gstin
from .log import banner, console, log, rupees, step
from .models import Claim, Invoice, TwoBLine, Vendor

# --- Reference pools ------------------------------------------------------

EMPLOYEES = [
    ("emp_priya", "Priya Sharma"), ("emp_rahul", "Rahul Verma"),
    ("emp_anjali", "Anjali Nair"), ("emp_vikram", "Vikram Iyer"),
    ("emp_sneha", "Sneha Reddy"), ("emp_arjun", "Arjun Mehta"),
    ("emp_kavya", "Kavya Rao"), ("emp_rohan", "Rohan Gupta"),
    ("emp_divya", "Divya Menon"), ("emp_karan", "Karan Singh"),
    ("emp_meera", "Meera Joshi"), ("emp_aditya", "Aditya Kulkarni"),
    ("emp_isha", "Isha Bhatia"), ("emp_nikhil", "Nikhil Deshpande"),
    ("emp_tanvi", "Tanvi Shah"),
]

# vendor name pools by category
VENDOR_NAMES: dict[ExpenseCategory, list[str]] = {
    ExpenseCategory.HOTEL: ["Taj Palace Hotels Ltd", "Oberoi Grand Hospitality", "ITC Grand Central",
                            "Lemon Tree Hotels Ltd", "Ginger Hotels Pvt Ltd"],
    ExpenseCategory.FLIGHT: ["InterGlobe Aviation Ltd", "Air India Ltd", "TATA SIA Airlines Ltd",
                             "SpiceJet Ltd", "Akasa Air Pvt Ltd"],
    ExpenseCategory.CAB: ["ANI Technologies Pvt Ltd", "Uber India Systems", "Meru Mobility Tech",
                          "BluSmart Mobility", "Namma Yatri Ltd"],
    ExpenseCategory.MEALS: ["Barbeque Nation Hospitality", "Haldiram Foods Pvt Ltd", "Cafe Coffee Day",
                            "Social Offline Dining", "Mainland China Restaurant"],
    ExpenseCategory.SAAS: ["Zoho Corporation Pvt Ltd", "Freshworks Technologies", "Chargebee Inc India",
                           "Postman API Tools Pvt Ltd", "Razorpay Software Pvt Ltd"],
    ExpenseCategory.EQUIPMENT: ["Infiniti Retail Ltd (Croma)", "Reliance Digital Retail", "Vijay Sales India",
                                "Ingram Micro India", "Redington India Ltd"],
    ExpenseCategory.TELECOM: ["Bharti Airtel Ltd", "Reliance Jio Infocomm", "Vodafone Idea Ltd",
                              "Tata Teleservices Ltd", "BSNL Cellular"],
    ExpenseCategory.COWORKING: ["WeWork India Management", "Awfis Space Solutions", "91Springboard Business Hub",
                                "Innov8 Coworking Pvt Ltd", "Smartworks Coworking"],
}

# GST rate (%) and typical gross-amount range by category.
CATEGORY_META: dict[ExpenseCategory, dict] = {
    ExpenseCategory.HOTEL: {"rate": 12, "lo": 6000, "hi": 25000},
    ExpenseCategory.FLIGHT: {"rate": 5, "lo": 3500, "hi": 18000},
    ExpenseCategory.CAB: {"rate": 5, "lo": 150, "hi": 1600},
    ExpenseCategory.MEALS: {"rate": 5, "lo": 120, "hi": 3000},      # blocked u/s 17(5)
    ExpenseCategory.SAAS: {"rate": 18, "lo": 500, "hi": 9000},
    ExpenseCategory.EQUIPMENT: {"rate": 18, "lo": 2500, "hi": 45000},
    ExpenseCategory.TELECOM: {"rate": 18, "lo": 300, "hi": 3500},
    ExpenseCategory.COWORKING: {"rate": 18, "lo": 3000, "hi": 16000},
}

ARCHETYPES = ["compliant", "qrmp", "erratic", "never"]
COMPANY_STATE = settings.company_state_code  # "29" Karnataka (primary)
REGISTERED_STATES = sorted(settings.registered_states)          # ["27","29"]
NONREG_STATES = ["07", "33", "24", "19", "09", "06", "23"]       # DL, TN, GJ, WB, UP, HR, MP
OTHER_STATES = ["27", "07", "06", "33", "24", "36", "19", "09"]

# Place-of-supply category groups (PRD v2).
SUPPLY_CATS = [c for c in ExpenseCategory if POS_BY_CATEGORY[c] == PlaceOfSupply.LOCATION_OF_SUPPLY
               and c != ExpenseCategory.MEALS]   # hotel, cab, coworking (meals is 17(5))
RECIPIENT_CATS = [c for c in ExpenseCategory if POS_BY_CATEGORY[c] == PlaceOfSupply.LOCATION_OF_RECIPIENT]

# The batch we reconcile against.
RETURN_PERIOD = "072026"
BATCH_MONTH_START = date(2026, 7, 1)
BATCH_MONTH_END = date(2026, 7, 28)

# Scenario mix -> counts (sums to n_claims=200). PRD v2 adds the state-trap,
# wrong-GSTIN (fixable), IGST-recoverable, and overclaim cases.
SCENARIO_COUNTS = {
    # recoverable (place-of-supply-safe: recipient-located or registered state)
    "clean_compliant": 22,
    "clean_qrmp": 10,
    "clean_erratic": 8,
    "clean_never": 6,
    "amount_mismatch_2b": 3,
    "recoverable_igst": 14,      # cross-state SaaS/equipment → IGST, claimable
    "karnataka_hotel": 6,        # in-state hotel → claimable (not all hotels are dead)
    # the state trap
    "state_trapped": 24,         # out-of-state accommodation/cab/coworking → dead
    "wrong_gstin_used": 10,      # right state, wrong company GSTIN → FIXABLE
    "overclaim_trapped": 12,     # state-trapped AND already claimed → owe back + interest
    # existing hard / exception cases
    "wrong_entity": 25,
    "missing_gstin": 16,
    "blocked_175": 16,
    "corrupted_invoice": 10,     # totals don't foot, or IGST+CGST/SGST both set
    "duplicate": 4,
    "low_confidence": 6,
    "invalid_gstin": 4,
    "inactive_gstin": 4,
}

# Scenarios that must reach the recoverable fallthrough → force recipient-located
# categories so place-of-supply never traps them.
RECIPIENT_ONLY_SCENARIOS = {
    "clean_compliant", "clean_qrmp", "clean_erratic", "clean_never", "amount_mismatch_2b",
}


def _rng() -> random.Random:
    return random.Random(settings.seed)


def _iso(d: date) -> str:
    return d.isoformat()


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- Vendor generation ----------------------------------------------------

def build_vendors(rng: random.Random) -> list[Vendor]:
    vendors: list[Vendor] = []
    cats = list(ExpenseCategory)
    idx = 0
    for cat in cats:
        for name in VENDOR_NAMES[cat]:
            archetype = ARCHETYPES[idx % 4]
            same_state = rng.random() < 0.45
            state = COMPANY_STATE if same_state else rng.choice(OTHER_STATES)
            seed = "".join(c for c in name.upper() if c.isalpha())[:5] or "ACMEX"
            gstin = make_valid_gstin(state, seed, entity=str(rng.randint(1, 9)))

            if archetype == "compliant":
                freq, rel = FilingFrequency.MONTHLY, rng.uniform(0.94, 0.99)
                hist = ["042026", "052026", "062026", "072026"]
                active = True
            elif archetype == "qrmp":
                freq, rel = FilingFrequency.QRMP, rng.uniform(0.85, 0.95)
                hist = ["062026"]  # quarter-end filing; July invoices lag
                active = True
            elif archetype == "erratic":
                freq, rel = FilingFrequency.MONTHLY, rng.uniform(0.35, 0.6)
                hist = rng.sample(["042026", "052026", "062026", "072026"], k=rng.randint(1, 2))
                active = True
            else:  # never
                freq, rel = FilingFrequency.MONTHLY, rng.uniform(0.0, 0.1)
                hist = []
                active = True  # set below — guarantee a stable inactive pool

            vendors.append(Vendor(
                gstin=gstin, legal_name=name, filing_frequency=freq,
                gstr1_filing_history=hist, reliability_score=round(rel, 3),
                active=active, observation_count=0, last_refreshed_at=_now(),
            ))
            idx += 1

    # Guarantee exactly 5 cancelled registrations from the never-file pool.
    # Prefer NON-meals vendors so an inactive_gstin claim is unambiguous (meals
    # would otherwise be blocked u/s 17(5) regardless of registration status).
    def _cat(v: Vendor) -> str:
        for cat, names in VENDOR_NAMES.items():
            if v.legal_name in names:
                return cat.value
        return "other"

    never_pool = [v for v in vendors if v.reliability_score < 0.15]
    never_pool.sort(key=lambda v: _cat(v) == ExpenseCategory.MEALS.value)  # meals last
    for v in never_pool[:5]:
        v.active = False
    return vendors


# --- Tax split ------------------------------------------------------------

def _split_tax(taxable: float, rate: int, intra_state: bool) -> tuple[float, float, float]:
    tax = round(taxable * rate / 100, 2)
    if intra_state:
        half = round(tax / 2, 2)
        return half, tax - half, 0.0  # cgst, sgst, igst
    return 0.0, 0.0, tax


# --- Claim + invoice materialisation --------------------------------------

def _pick_vendor(vendors: list[Vendor], cat: ExpenseCategory, archetype: str | None,
                 rng: random.Random, active: bool | None = None) -> Vendor:
    pool = [v for v in vendors if v.legal_name in VENDOR_NAMES[cat]]
    # Activity is authoritative: filter it FIRST so the archetype fallback can
    # never resurrect an inactive vendor when an active one was requested.
    if active is not None:
        pool = [v for v in pool if v.active == active] or pool
    if archetype:
        if archetype == "qrmp":
            pool = [v for v in pool if v.filing_frequency == FilingFrequency.QRMP] or pool
        elif archetype == "compliant":
            pool = [v for v in pool
                    if v.reliability_score > 0.9 and v.filing_frequency == FilingFrequency.MONTHLY] or pool
        elif archetype == "erratic":
            monthly = [v for v in pool if v.filing_frequency == FilingFrequency.MONTHLY]
            pool = [v for v in pool if 0.3 < v.reliability_score < 0.7] or monthly or pool
        elif archetype == "never":
            # never/erratic/compliant are all MONTHLY filers; if the exact
            # archetype is unavailable, keep MONTHLY so the verdict stays
            # RECOVERABLE rather than flipping to PENDING_QRMP.
            monthly = [v for v in pool if v.filing_frequency == FilingFrequency.MONTHLY]
            pool = [v for v in pool if v.reliability_score < 0.15] or monthly or pool
    return rng.choice(pool)


def _vendor_category(vendor: Vendor) -> ExpenseCategory:
    for cat, names in VENDOR_NAMES.items():
        if vendor.legal_name in names:
            return cat
    return ExpenseCategory.EQUIPMENT


def _branch_vendor(branch_map: dict, cat: ExpenseCategory, state: str) -> Vendor:
    """A state-branch supplier: the same chain registered in `state` has its own
    GSTIN. Deterministic per (category, state) so the set is reproducible, and
    added to the vendor table so reliability + 2B matching stay consistent."""
    key = (cat, state)
    if key in branch_map:
        return branch_map[key]
    names = VENDOR_NAMES[cat]
    name = names[sum(ord(c) for c in state) % len(names)]
    seed = "".join(c for c in name.upper() if c.isalpha())[:5] or "ACMEX"
    gstin = make_valid_gstin(state, seed, entity="1")
    v = Vendor(gstin=gstin, legal_name=name, filing_frequency=FilingFrequency.MONTHLY,
               gstr1_filing_history=["052026", "062026", "072026"], reliability_score=0.96,
               active=True, observation_count=0, last_refreshed_at=_now())
    branch_map[key] = v
    return v


# Scenarios that must stay recoverable, so they may never land on meals (which
# is always blocked u/s 17(5)).
NO_MEALS_SCENARIOS = {
    "clean_compliant", "clean_qrmp", "clean_erratic", "clean_never", "amount_mismatch_2b",
}


def build_claims(vendors: list[Vendor], rng: random.Random):
    """Returns (claims, invoices, ground_truth, branch_vendors)."""
    claims: list[Claim] = []
    invoices: list[Invoice] = []
    truth: list[dict] = []
    branch_map: dict = {}   # (category, state) -> state-branch Vendor

    plan: list[str] = []
    for scen, n in SCENARIO_COUNTS.items():
        plan += [scen] * n
    assert len(plan) == settings.n_claims, f"plan={len(plan)} != {settings.n_claims}"
    rng.shuffle(plan)
    plan = [s for s in plan if s != "duplicate"] + [s for s in plan if s == "duplicate"]

    duplicate_source: dict = {}
    kar_gstin = settings.gstin_for_state("29")   # primary registration

    for scen in plan:
        emp_id, emp_name = rng.choice(EMPLOYEES)
        buyer_gstin = kar_gstin
        buyer_name = settings.company_name
        already_claimed = False

        # ---- category + supplier (state matters now) --------------------
        if scen == "inactive_gstin":
            vendor = rng.choice([v for v in vendors if not v.active])
            cat = _vendor_category(vendor)
        elif scen in ("state_trapped", "overclaim_trapped"):
            cat = rng.choice(SUPPLY_CATS)
            vendor = _branch_vendor(branch_map, cat, rng.choice(NONREG_STATES))
            already_claimed = scen == "overclaim_trapped"
        elif scen == "wrong_gstin_used":
            cat = rng.choice(SUPPLY_CATS)
            vendor = _branch_vendor(branch_map, cat, "27")   # Maharashtra: we ARE registered
        elif scen == "karnataka_hotel":
            cat = rng.choice(SUPPLY_CATS)
            vendor = _branch_vendor(branch_map, cat, "29")
        elif scen == "recoverable_igst":
            cat = rng.choice(RECIPIENT_CATS)
            vendor = _branch_vendor(branch_map, cat, rng.choice(NONREG_STATES))
        else:
            if scen == "blocked_175":
                cat = ExpenseCategory.MEALS
            elif scen in RECIPIENT_ONLY_SCENARIOS:
                cat = rng.choice(RECIPIENT_CATS)
            else:
                cat = rng.choice([c for c in ExpenseCategory if c != ExpenseCategory.MEALS] +
                                 [ExpenseCategory.MEALS])
            arche = {"clean_compliant": "compliant", "clean_qrmp": "qrmp",
                     "clean_erratic": "erratic", "clean_never": "never",
                     "amount_mismatch_2b": "compliant"}.get(scen)
            vendor = _pick_vendor(vendors, cat, arche, rng, active=True)

        supplier_gstin = vendor.gstin
        supplier_state = supplier_gstin[:2]
        meta = CATEGORY_META[cat]
        gross = round(rng.uniform(meta["lo"], meta["hi"]), 2)
        rate = meta["rate"]
        taxable = round(gross / (1 + rate / 100), 2)

        # tax split: supply-located is always CGST+SGST of the supply state;
        # recipient-located is IGST when the supplier isn't in our state.
        if POS_BY_CATEGORY[cat] == PlaceOfSupply.LOCATION_OF_SUPPLY:
            intra = True
        else:
            intra = supplier_state == COMPANY_STATE
        cgst, sgst, igst = _split_tax(taxable, rate, intra)
        inv_date = BATCH_MONTH_START + timedelta(days=rng.randint(0, 27))
        inv_no = f"{vendor.legal_name[:3].upper()}/{RETURN_PERIOD}/{rng.randint(1000, 9999)}"
        confidence = round(rng.uniform(0.9, 0.99), 3)
        in_2b = False
        two_b_amount = taxable

        # ---- expected decision + mutations ------------------------------
        if scen in ("clean_compliant", "clean_erratic", "clean_never"):
            expected_decision = "RECOVERABLE_IGST" if igst > 0 else "RECOVERABLE"
            in_2b = rng.random() < vendor.reliability_score
        elif scen == "clean_qrmp":
            expected_decision = "PENDING_QRMP"
        elif scen == "amount_mismatch_2b":
            expected_decision = "RECOVERABLE_IGST" if igst > 0 else "RECOVERABLE"
            in_2b = True
            two_b_amount = round(taxable * rng.uniform(0.8, 0.92), 2)
        elif scen == "recoverable_igst":
            expected_decision = "RECOVERABLE_IGST"
            in_2b = rng.random() < 0.9
        elif scen == "karnataka_hotel":
            expected_decision = "RECOVERABLE"
            in_2b = rng.random() < 0.9
        elif scen in ("state_trapped", "overclaim_trapped"):
            expected_decision = "STATE_TRAPPED"
        elif scen == "wrong_gstin_used":
            expected_decision = "WRONG_GSTIN_USED"
        elif scen == "wrong_entity":
            buyer_gstin = None
            buyer_name = emp_name
            expected_decision = "UNRECOVERABLE_WRONG_ENTITY"
        elif scen == "missing_gstin":
            supplier_gstin = None
            expected_decision = "EXCEPTION:MISSING_GSTIN"
        elif scen == "blocked_175":
            expected_decision = "BLOCKED_17_5"
            in_2b = rng.random() < vendor.reliability_score
            already_claimed = rng.random() < 0.35   # restaurant bills claimed despite 17(5)
        elif scen == "corrupted_invoice":
            if rng.random() < 0.5:
                gross = round(gross + rng.uniform(200, 900), 2)   # totals don't foot
            elif cgst > 0:
                igst = round(cgst, 2)                             # IGST + CGST/SGST both set
            else:
                cgst = sgst = round(igst / 2, 2)                  # both set (the interstate case)
            expected_decision = "EXCEPTION:CORRUPTED_INVOICE"
        elif scen == "invalid_gstin":
            supplier_gstin = supplier_gstin[:14] + ("A" if supplier_gstin[14] != "A" else "B")
            expected_decision = "EXCEPTION:INVALID_GSTIN"
        elif scen == "inactive_gstin":
            expected_decision = "EXCEPTION:GSTIN_NOT_ACTIVE"
        elif scen == "low_confidence":
            confidence = round(rng.uniform(0.2, 0.45), 3)
            expected_decision = "EXCEPTION:LOW_EXTRACTION_CONFIDENCE"
        elif scen == "duplicate":
            expected_decision = "EXCEPTION:DUPLICATE_CLAIM"
            if duplicate_source:
                supplier_gstin = duplicate_source["supplier_gstin"]
                inv_no = duplicate_source["invoice_no"]
                inv_date = date.fromisoformat(duplicate_source["invoice_date"])
        else:
            expected_decision = "RECOVERABLE"

        claim = Claim(
            seq=len(claims), employee_id=emp_id, employee_name=emp_name, amount_gross=gross,
            category=cat, description=f"{cat.value} — {vendor.legal_name.split(' (')[0]}",
            submitted_at=_now(), already_claimed=already_claimed,
            claimed_days_ago=rng.randint(45, 400) if already_claimed else 0,
        )
        invoice = Invoice(
            claim_id=claim.claim_id, supplier_gstin=supplier_gstin,
            supplier_name=vendor.legal_name, invoice_no=inv_no, invoice_date=_iso(inv_date),
            taxable_value=taxable, cgst=cgst, sgst=sgst, igst=igst,
            buyer_gstin=buyer_gstin, buyer_name=buyer_name,
            extraction_confidence=confidence, extraction_method=ExtractionMethod.SYNTHETIC_TRUTH,
            supplier_state_code=(supplier_gstin[:2] if supplier_gstin else None),
            buyer_gstin_used=buyer_gstin,
        )
        claims.append(claim)
        invoices.append(invoice)

        if scen == "clean_compliant" and not duplicate_source:
            duplicate_source = {"supplier_gstin": supplier_gstin, "invoice_no": inv_no,
                                "invoice_date": _iso(inv_date)}

        truth.append({
            "claim_id": claim.claim_id, "scenario": scen, "expected_decision": expected_decision,
            "in_2b": in_2b, "tax_amount": round(cgst + sgst + igst, 2),
            "two_b_taxable": round(two_b_amount, 2) if in_2b else None,
            "supplier_gstin": supplier_gstin, "invoice_no": inv_no, "invoice_date": _iso(inv_date),
            "already_claimed": already_claimed, "supplier_state": supplier_state,
        })

    return claims, invoices, truth, list(branch_map.values())


# --- Ground-truth 2B ------------------------------------------------------

def build_two_b(truth: list[dict]) -> list[TwoBLine]:
    lines: list[TwoBLine] = []
    for t in truth:
        if not t["in_2b"] or not t["supplier_gstin"]:
            continue
        taxable = t["two_b_taxable"] if t["two_b_taxable"] is not None else 0.0
        lines.append(TwoBLine(
            gstin=t["supplier_gstin"], invoice_no=t["invoice_no"],
            invoice_date=t["invoice_date"], taxable_value=taxable,
            tax=round(taxable * 0.1, 2), return_period=RETURN_PERIOD,
        ))
    return lines


# --- Orchestration --------------------------------------------------------

def generate() -> dict:
    step("STEP 1 — Synthetic dataset generation")
    rng = _rng()
    reset_db()
    log.info("[loop.dim]Reset ledger. Seed=%s. Company=%s (%s)[/]",
             settings.seed, settings.company_name, settings.company_gstin)

    vendors = build_vendors(rng)
    claims, invoices, truth, branch_vendors = build_claims(vendors, rng)
    two_b = build_two_b(truth)
    # A state-branch GSTIN can coincide with a base vendor's — dedupe, base wins.
    uniq: dict[str, Vendor] = {v.gstin: v for v in vendors}
    for v in branch_vendors:
        uniq.setdefault(v.gstin, v)
    all_vendors = list(uniq.values())

    with get_session() as s:
        for v in all_vendors:
            s.add(v)
        for c in claims:
            s.add(c)
        for inv in invoices:
            s.add(inv)
        for line in two_b:
            s.add(line)

    gt_path = settings.receipts_dir.parent / "ground_truth.json"
    gt_path.write_text(json.dumps(truth, indent=2))

    # Render receipt images so the extraction step reads a real artifact.
    from .receipts import render_all
    render_all()

    _report(vendors, claims, invoices, truth, two_b)
    return {
        "vendors": len(all_vendors), "claims": len(claims), "invoices": len(invoices),
        "two_b_lines": len(two_b), "ground_truth": str(gt_path),
    }


def _report(vendors, claims, invoices, truth, two_b) -> None:
    from collections import Counter

    from rich.table import Table

    arche = Counter(
        "compliant" if v.reliability_score > 0.9 and v.filing_frequency == FilingFrequency.MONTHLY
        else "qrmp" if v.filing_frequency == FilingFrequency.QRMP
        else "erratic" if v.reliability_score >= 0.15 else "never"
        for v in vendors
    )
    scen = Counter(t["scenario"] for t in truth)
    total_tax = sum(t["tax_amount"] for t in truth)
    at_risk_wrong = sum(t["tax_amount"] for t in truth
                        if t["expected_decision"] == "UNRECOVERABLE_WRONG_ENTITY")
    blocked = sum(t["tax_amount"] for t in truth if t["expected_decision"] == "BLOCKED_17_5")
    trapped = sum(t["tax_amount"] for t in truth if t["expected_decision"] == "STATE_TRAPPED")
    overclaim = sum(t["tax_amount"] for t in truth if t.get("already_claimed"))

    banner("Dataset built", f"{len(claims)} claims · {len(vendors)} vendors · {len(two_b)} 2B lines")

    tbl = Table(title="Vendor archetypes", show_edge=False, title_style="loop.step")
    tbl.add_column("archetype"); tbl.add_column("count", justify="right")
    for k in ARCHETYPES:
        tbl.add_row(k, str(arche.get(k, 0)))
    console.print(tbl)

    tbl2 = Table(title="Claim scenarios", show_edge=False, title_style="loop.step")
    tbl2.add_column("scenario"); tbl2.add_column("count", justify="right")
    for k in SCENARIO_COUNTS:
        tbl2.add_row(k, str(scen.get(k, 0)))
    console.print(tbl2)

    console.print(f"\n  Total GST across batch : [loop.money]{rupees(total_tax)}[/]")
    console.print(f"  State-trapped (dead)   : [loop.risk]{rupees(trapped)}[/]")
    console.print(f"  Overclaimed (owe back) : [loop.loss]{rupees(overclaim)}[/]")
    console.print(f"  Lost to wrong entity   : [loop.loss]{rupees(at_risk_wrong)}[/]")
    console.print(f"  Blocked u/s 17(5)      : [loop.risk]{rupees(blocked)}[/]")
    console.print(f"  Ground-truth 2B lines  : {len(two_b)}")


if __name__ == "__main__":
    result = generate()
    console.print(f"\n[loop.money]✓ Step 1 complete[/] — {result}")
