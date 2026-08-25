"""Render each synthetic invoice as a receipt PNG, so the extraction step has a
real image to read — not just a JSON row. Low-confidence claims get a
deliberately degraded receipt (rotation + noise + faded ink) so the pipeline
must genuinely route them to human review instead of guessing."""

from __future__ import annotations

import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .config import settings
from .log import log
from .models import Invoice

W, H = 520, 760
INK = (25, 25, 25)
PAPER = (250, 249, 245)


def _font(size: int, bold: bool = False):
    # Fall back to PIL's default bitmap font if no TTF is available.
    candidates = [
        "/System/Library/Fonts/Supplemental/Courier New Bold.ttf" if bold
        else "/System/Library/Fonts/Supplemental/Courier New.ttf",
        "/System/Library/Fonts/Menlo.ttc",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render(invoice: Invoice, degraded: bool = False, seed: int = 0) -> Image.Image:
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    f_big = _font(26, bold=True)
    f = _font(18)
    f_sm = _font(15)
    rng = random.Random(seed)

    y = 28

    def line(text: str, font=f, gap: int = 26, center: bool = False, ink=INK):
        nonlocal y
        if center:
            w = d.textlength(text, font=font)
            d.text(((W - w) / 2, y), text, font=font, fill=ink)
        else:
            d.text((30, y), text, font=font, fill=ink)
        y += gap

    line(invoice.supplier_name[:34], font=f_big, gap=34, center=True)
    line("TAX INVOICE", font=f_sm, gap=22, center=True)
    d.line((30, y, W - 30, y), fill=INK, width=1); y += 16

    gstin = invoice.supplier_gstin or "-- NOT PRINTED --"
    line(f"GSTIN : {gstin}", font=f_sm)
    line(f"Invoice#: {invoice.invoice_no or '-'}", font=f_sm)
    line(f"Date   : {invoice.invoice_date or '-'}", font=f_sm, gap=30)

    d.line((30, y, W - 30, y), fill=INK, width=1); y += 16
    line("BILL TO", font=f_sm, gap=22)
    line(invoice.buyer_name[:40], font=f)
    line(f"GSTIN : {invoice.buyer_gstin or '(individual / not provided)'}", font=f_sm, gap=30)

    d.line((30, y, W - 30, y), fill=INK, width=1); y += 16
    line(f"Taxable value      {invoice.taxable_value:>12,.2f}", font=f_sm)
    if invoice.igst:
        line(f"IGST               {invoice.igst:>12,.2f}", font=f_sm)
    else:
        line(f"CGST               {invoice.cgst:>12,.2f}", font=f_sm)
        line(f"SGST               {invoice.sgst:>12,.2f}", font=f_sm)
    d.line((30, y, W - 30, y), fill=INK, width=1); y += 12
    total = invoice.taxable_value + invoice.total_tax
    line(f"TOTAL              {total:>12,.2f}", font=f, gap=34)

    line("Thank you. Visit again.", font=f_sm, center=True, ink=(120, 120, 120))

    if degraded:
        img = _degrade(img, rng)
    return img


def _degrade(img: Image.Image, rng: random.Random) -> Image.Image:
    """Simulate a crumpled thermal receipt: fade, blur, rotate, speckle."""
    img = Image.blend(img, Image.new("RGB", img.size, PAPER), 0.35)  # faded ink
    img = img.filter(ImageFilter.GaussianBlur(radius=1.4))
    px = img.load()
    for _ in range(int(W * H * 0.02)):
        x, y = rng.randint(0, W - 1), rng.randint(0, H - 1)
        v = rng.randint(140, 210)
        px[x, y] = (v, v, v)
    img = img.rotate(rng.uniform(-7, 7), expand=False, fillcolor=PAPER)
    return img


def render_all() -> int:
    from .db import get_session
    from sqlmodel import select

    n = 0
    with get_session() as s:
        invoices = s.exec(select(Invoice)).all()
        for inv in invoices:
            degraded = inv.extraction_confidence < 0.5
            img = render(inv, degraded=degraded, seed=hash(inv.invoice_id) & 0xFFFF)
            path = settings.receipts_dir / f"{inv.claim_id}.png"
            img.save(path, "PNG")
            # store the receipt path back on the claim for the UI
            from .models import Claim
            claim = s.get(Claim, inv.claim_id)
            if claim:
                claim.receipt_path = f"receipts/{inv.claim_id}.png"
                s.add(claim)
            n += 1
    log.info("[loop.dim]Rendered %d receipt images -> %s[/]", n, settings.receipts_dir)
    return n


if __name__ == "__main__":
    render_all()
