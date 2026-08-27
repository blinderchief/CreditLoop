"""Central configuration. Everything is env-overridable but ships with sane
defaults so `make demo` works with zero setup."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

from .gstin import compute_checksum

# backend/  (this file lives in backend/app/config.py)
BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
RECEIPTS_DIR = DATA_DIR / "receipts"

# State-code → name (only the states this demo touches).
STATE_NAMES = {
    "29": "Karnataka", "27": "Maharashtra", "07": "Delhi", "33": "Tamil Nadu",
    "24": "Gujarat", "36": "Telangana", "19": "West Bengal", "09": "Uttar Pradesh",
    "06": "Haryana", "23": "Madhya Pradesh",
}


def _company_gstin(state_code: str, pan: str = "AABCA1234A", entity: str = "1") -> str:
    """Same company (same PAN) registered in several states → one GSTIN each.
    Only the 2-digit state prefix changes; the checksum is recomputed."""
    first14 = f"{state_code}{pan}{entity}Z"
    return first14 + compute_checksum(first14)


# CreditLoop's company is registered in TWO states — this is what makes the
# place-of-supply "state trap" (and the fixable WRONG_GSTIN_USED case) real.
COMPANY_REGISTRATIONS = [
    {"state_code": "29", "state_name": "Karnataka", "gstin": _company_gstin("29"), "is_primary": True},
    {"state_code": "27", "state_name": "Maharashtra", "gstin": _company_gstin("27"), "is_primary": False},
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CREDITLOOP_", env_file=".env", extra="ignore")

    # --- Identity of the company running CreditLoop -----------------------
    # Multi-state by design: the company holds a GSTIN per registered state.
    # A claim is recoverable only if the place-of-supply state is one we're
    # registered in — and the invoice used that state's GSTIN.
    company_name: str = "Acme India Pvt Ltd"
    company_registrations: list[dict] = COMPANY_REGISTRATIONS
    company_gstin: str = COMPANY_REGISTRATIONS[0]["gstin"]   # primary (Karnataka)
    company_state_code: str = COMPANY_REGISTRATIONS[0]["state_code"]

    @property
    def registered_states(self) -> set[str]:
        return {r["state_code"] for r in self.company_registrations}

    @property
    def company_gstins(self) -> set[str]:
        return {r["gstin"] for r in self.company_registrations}

    def gstin_for_state(self, state_code: str) -> Optional[str]:
        for r in self.company_registrations:
            if r["state_code"] == state_code:
                return r["gstin"]
        return None

    # --- Triage thresholds (PRD section 9) --------------------------------
    tier0_max_tax: float = 200.0      # below this, auto-approve, spend 0 API calls
    tier1_max_tax: float = 2000.0     # below this, cached vendor data only
    intervene_p_below: float = 0.5    # tier_3: if p_recoverable < this, chase vendor
    cost_per_api_call: float = 0.50   # rupee cost assumption, for expected-value math

    # --- Storage ----------------------------------------------------------
    db_path: Path = DATA_DIR / "creditloop.db"
    receipts_dir: Path = RECEIPTS_DIR

    # --- External integrations (mock by default; PRD says mock honestly) --
    gsp_mode: str = "mock"            # "mock" | "live"
    razorpay_mode: str = "mock"       # "mock" | "test"

    # --- LLM provider (Gemini — free-tier vision). Env: CREDITLOOP_GEMINI_API_KEY.
    # Empty key => the app falls back to synthetic-truth / templates, so it runs
    # with or without a key and "lights up" when you add one.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-latest"     # vision + text; alias always points to a current Flash
    llm_extract_sample: int = 24                  # how many receipts to VLM-read (rate-limit friendly)

    # --- RazorpayX (test mode). Empty => mock payouts. -------------------
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_fund_account: str = ""   # RazorpayX fund_account_id to pay into (test)
    razorpay_account_number: str = "" # RazorpayX virtual account number (test)

    @property
    def llm_enabled(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def razorpay_live(self) -> bool:
        return bool(self.razorpay_key_id and self.razorpay_key_secret)

    # --- Synthetic dataset knobs ------------------------------------------
    seed: int = 42
    n_vendors: int = 40
    n_claims: int = 200

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.db_path}"


settings = Settings()

# Make sure the on-disk directories exist the moment config is imported.
DATA_DIR.mkdir(parents=True, exist_ok=True)
RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
