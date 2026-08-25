"""GSTIN format + checksum. A GSTIN is 15 chars:

    2 state code | 10 PAN | 1 entity code | 'Z' | 1 checksum

The 15th character is a base-36 checksum over the first 14. We implement the
real algorithm so validate_gstin() is genuine, and so the synthetic generator
can mint GSTINs that actually pass validation (or deliberately fail it)."""

from __future__ import annotations

import re

_CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_CODE = {c: i for i, c in enumerate(_CHARSET)}
_FORMAT = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$")


def _checksum_char(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14):
        factor = 2 if i % 2 else 1
        prod = _CODE[ch] * factor
        total += prod // 36 + prod % 36
    return _CHARSET[(36 - (total % 36)) % 36]


def compute_checksum(first14: str) -> str:
    """Return the correct 15th character for a 14-char GSTIN prefix."""
    return _checksum_char(first14.upper())


def is_valid_gstin(gstin: str | None) -> bool:
    """Format check + checksum check. Empty/None -> False."""
    if not gstin:
        return False
    gstin = gstin.strip().upper()
    if not _FORMAT.match(gstin):
        return False
    return _checksum_char(gstin[:14]) == gstin[14]


def make_valid_gstin(state_code: str, pan_seed: str, entity: str = "1") -> str:
    """Build a checksum-valid GSTIN from parts. pan_seed is padded/truncated to
    the 10-char PAN block (5 letters, 4 digits, 1 letter)."""
    # Normalise a PAN-shaped 10-char block deterministically from the seed.
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    digits = "0123456789"
    s = (pan_seed.upper() + "AAAAA0000A")
    pan = (
        "".join(c if c in letters else "A" for c in s[:5])
        + "".join(c if c in digits else "1" for c in s[5:9])
        + (s[9] if s[9] in letters else "A")
    )
    first14 = f"{state_code}{pan}{entity}Z"
    return first14 + _checksum_char(first14)
