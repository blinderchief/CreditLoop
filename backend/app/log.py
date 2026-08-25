"""Backend observability. The PRD wants the agent to *show its work* — every
triage decision, every rule fired, every rupee at stake printed as it happens.

This module gives us one shared rich console plus a few semantic helpers so the
backend log reads like a narration of what the agent is thinking."""

from __future__ import annotations

import logging

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

THEME = Theme(
    {
        "loop.money": "bold green",
        "loop.loss": "bold red",
        "loop.risk": "bold yellow",
        "loop.rule": "cyan",
        "loop.tier": "magenta",
        "loop.step": "bold blue",
        "loop.dim": "dim",
    }
)

console = Console(theme=THEME, highlight=False)

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False, markup=True)],
)

log = logging.getLogger("creditloop")
log.setLevel(logging.INFO)


def rupees(x: float) -> str:
    """Format a rupee amount the Indian way: ₹1,23,456.78."""
    neg = x < 0
    x = abs(x)
    whole = int(x)
    frac = round(x - whole, 2)
    s = str(whole)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        # group the head in 2s (Indian numbering)
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    out = f"₹{s}"
    if frac:
        out += f"{frac:.2f}"[1:]  # ".xx"
    return ("-" if neg else "") + out


def step(title: str) -> None:
    """Announce a major pipeline step with a rule so the log is scannable."""
    console.rule(f"[loop.step]{title}[/]", style="blue")


def banner(title: str, subtitle: str = "") -> None:
    console.print()
    console.print(f"[loop.step]● {title}[/]")
    if subtitle:
        console.print(f"  [loop.dim]{subtitle}[/]")
