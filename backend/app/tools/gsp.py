"""GSP client — the ride-along GST Suvidha Provider (PRD section 10).

We read, we never file. In `mock` mode the Vendor table stands in for the GSP's
view (it holds the filing history and registration status a GSP would return).
The client adds the three things that make the integration realistic:

  * aggressive caching  — the same GSTIN is never looked up twice
  * call counting       — so the demo can report GSP calls / claim
  * an availability flag — flip `available = False` to demo graceful
                            degradation to PROVISIONAL without blocking payouts
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlmodel import select

from ..config import settings
from ..db import get_session
from ..gstin import is_valid_gstin
from ..log import log
from ..models import Vendor


class GspUnavailable(Exception):
    """Raised when the GSP is down/rate-limited. Callers degrade, never crash."""


@dataclass
class GstinInfo:
    gstin: str
    format_valid: bool
    active: Optional[bool]
    filing_frequency: Optional[str]
    reliability_score: Optional[float]
    filing_history: list[str]
    from_cache: bool = False


class GspClient:
    def __init__(self, available: bool = True):
        self.available = available
        self.live_calls = 0
        self.cache_hits = 0
        self._cache: dict[str, GstinInfo] = {}

    # -- health ------------------------------------------------------------
    def set_available(self, ok: bool) -> None:
        self.available = ok
        log.warning("[loop.risk]GSP availability set to %s[/]", ok)

    # -- lookups -----------------------------------------------------------
    def lookup(self, gstin: Optional[str]) -> GstinInfo:
        """Validate + fetch registration/filing info for a GSTIN.

        Raises GspUnavailable when the provider is 'down' AND the answer isn't
        already cached — so cached data still serves during an outage.
        """
        fmt_ok = is_valid_gstin(gstin)
        if not gstin:
            return GstinInfo(gstin="", format_valid=False, active=None,
                             filing_frequency=None, reliability_score=None, filing_history=[])
        if not fmt_ok:
            # a bad checksum needs no network call — it's provably invalid
            return GstinInfo(gstin=gstin, format_valid=False, active=None,
                             filing_frequency=None, reliability_score=None, filing_history=[])

        if gstin in self._cache:
            self.cache_hits += 1
            info = self._cache[gstin]
            return GstinInfo(**{**info.__dict__, "from_cache": True})

        if not self.available:
            raise GspUnavailable(f"GSP down and {gstin} not cached")

        # live call (mock): the Vendor table is the GSP's view
        self.live_calls += 1
        with get_session() as s:
            vendor = s.exec(select(Vendor).where(Vendor.gstin == gstin)).first()
        if vendor is None:
            info = GstinInfo(gstin=gstin, format_valid=True, active=None,
                             filing_frequency=None, reliability_score=None, filing_history=[])
        else:
            info = GstinInfo(
                gstin=gstin, format_valid=True, active=vendor.active,
                filing_frequency=vendor.filing_frequency.value,
                reliability_score=vendor.reliability_score,
                filing_history=list(vendor.gstr1_filing_history),
            )
        self._cache[gstin] = info
        return info

    def cached(self, gstin: Optional[str]) -> Optional[GstinInfo]:
        """Return cached info WITHOUT a live call — used for cheap claims that
        triage decided not to validate. None means 'not looked up'."""
        if gstin and gstin in self._cache:
            self.cache_hits += 1
            return GstinInfo(**{**self._cache[gstin].__dict__, "from_cache": True})
        return None

    def stats(self) -> dict:
        return {"live_calls": self.live_calls, "cache_hits": self.cache_hits,
                "available": self.available, "mode": settings.gsp_mode}
