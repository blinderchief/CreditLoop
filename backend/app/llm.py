"""LLM provider — Google Gemini (free-tier vision + text).

One key (`CREDITLOOP_GEMINI_API_KEY`) powers the three places an LLM genuinely
belongs (PRD section 9):
  * reading a crumpled receipt image  -> structured JSON  (vision)
  * drafting a vendor reissue request in the right language
  * proposing a rule diff from a new GST advisory

It NEVER decides tax eligibility or moves money — that stays in the
deterministic engine. Every method degrades gracefully: with no key, callers
fall back to synthetic-truth / templates, so the whole app runs either way.

We call the REST API directly with httpx — no SDK dependency, no lock-in.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Optional

import httpx

from .config import settings
from .log import log

_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class LLMUnavailable(Exception):
    pass


@dataclass
class LLMResult:
    text: str
    raw: dict


class GeminiClient:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or settings.gemini_api_key
        self.model = model or settings.gemini_model
        self.calls = 0

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _generate(self, parts: list[dict], *, json_out: bool = False,
                  temperature: float = 0.0, max_tokens: int = 1024) -> LLMResult:
        if not self.enabled:
            raise LLMUnavailable("no GEMINI_API_KEY set")
        body = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                **({"responseMimeType": "application/json"} if json_out else {}),
            },
        }
        url = f"{_BASE}/{self.model}:generateContent"
        self.calls += 1
        try:
            r = httpx.post(url, headers={"x-goog-api-key": self.api_key},
                           json=body, timeout=40)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise LLMUnavailable(f"Gemini request failed: {e}") from e
        data = r.json()
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as e:
            raise LLMUnavailable(f"unexpected Gemini response: {data}") from e
        return LLMResult(text=text, raw=data)

    # -- text ---------------------------------------------------------------
    def complete(self, prompt: str, *, json_out: bool = False, temperature: float = 0.2) -> str:
        return self._generate([{"text": prompt}], json_out=json_out, temperature=temperature).text

    # -- vision: read a receipt image into structured fields ---------------
    def extract_receipt(self, image_path: str) -> dict:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        prompt = (
            "You are reading an Indian GST tax invoice / receipt image. Extract ONLY what is "
            "printed. Return strict JSON with keys: supplier_name (string), supplier_gstin "
            "(15-char GSTIN or null if absent), invoice_no (string or null), invoice_date "
            "(YYYY-MM-DD or null), taxable_value (number), cgst (number), sgst (number), "
            "igst (number), buyer_name (string), buyer_gstin (15-char GSTIN or null if the bill "
            "is in an individual's name), confidence (0..1 for how legible the image was). "
            "Do NOT guess a GSTIN you cannot read — use null and lower the confidence."
        )
        res = self._generate(
            [{"text": prompt}, {"inline_data": {"mime_type": "image/png", "data": b64}}],
            json_out=True, temperature=0.0, max_tokens=512,
        )
        try:
            return json.loads(res.text)
        except json.JSONDecodeError as e:
            raise LLMUnavailable(f"Gemini returned non-JSON: {res.text[:200]}") from e


# module-level singleton, cheap to construct
client = GeminiClient()


def llm_status() -> dict:
    return {"provider": "gemini", "enabled": client.enabled,
            "model": client.model if client.enabled else None}
