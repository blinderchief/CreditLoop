"""CreditLoop — an agent that decides whether the GST on an employee expense
claim will ever come back, before a rupee leaves the company.

Three strictly separated layers:
  Layer 1  the Ledger  — immutable join: claim -> invoice -> GSTIN -> 2B -> payout
  Layer 2  Judgment    — deterministic (the law) + learned (the prediction)
  Layer 3  Action      — approve / hold / pay / chase / flag, every move logged
"""

__version__ = "0.1.0"
