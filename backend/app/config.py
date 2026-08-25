"""Central configuration. Everything is env-overridable but ships with sane
defaults so `make demo` works with zero setup."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/  (this file lives in backend/app/config.py)
BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
RECEIPTS_DIR = DATA_DIR / "receipts"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CREDITLOOP_", env_file=".env", extra="ignore")

    # --- Identity of the company running CreditLoop -----------------------
    # Every claim is judged against THIS entity's GSTIN. An invoice in any
    # other name is UNRECOVERABLE_WRONG_ENTITY.
    company_name: str = "Acme India Pvt Ltd"
    company_gstin: str = "29AABCA1234A1Z5"  # Karnataka (state code 29)
    company_state_code: str = "29"

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
