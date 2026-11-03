"""Versioned TDS rule table for resident, non-salary payments (India).

Design point: tax knowledge lives HERE (data + effective dates), never in the LLM.
When the law changes, someone adds/closes a row; no model is retrained or re-prompted.

IMPORTANT: every rule is marked verified=False. The values were assembled from
secondary sources (tax-portal articles) and the author's general knowledge, NOT yet
checked against the primary text of the Income-tax Act 2025 / 1961 or CBDT notifications.
A production system must make `verified=True` impossible without a named reviewer + source.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal as D
from typing import Optional

NEW_ACT_START = date(2026, 4, 1)


@dataclass(frozen=True)
class Rule:
    id: str
    category: str
    act: str                       # "1961" or "2025"
    valid_from: date
    valid_to: Optional[date]       # inclusive; None = still in force
    cite: str
    rate_individual: D             # rate when payee is individual/HUF
    rate_other: D                  # rate for every other payee
    threshold: int                 # annual aggregate (per payee, per payer) in INR
    single_threshold: Optional[int] = None   # per-payment/contract limit (contractors)
    verified: bool = False
    note: str = ""


def _r(id, cat, act, f, t, cite, ri, ro, thr, single=None, note=""):
    return Rule(id, cat, act, f, t, cite, D(ri), D(ro), thr, single, False, note)


A24, A25, A26 = date(2024, 4, 1), date(2025, 4, 1), date(2026, 4, 1)
E24, E25 = date(2025, 3, 31), date(2026, 3, 31)

RULES = [
    # --- Contractors (old 194C -> new 393(1) Sl. 6(i)) ---
    _r("C-1961", "contractor", "1961", A24, E25, "Income-tax Act 1961 s.194C", "0.01", "0.02", 100000, 30000),
    _r("C-2025", "contractor", "2025", A26, None, "Income-tax Act 2025 s.393(1) Table Sl. No. 6(i)", "0.01", "0.02", 100000, 30000,
       note="One secondary source mixes 194C/194M thresholds in its table; verify against Act."),
    # --- Professional fees (old 194J(a) -> new 393(1) Sl. 6(iii)(a)) ---
    _r("P-1961-a", "professional", "1961", A24, E24, "Income-tax Act 1961 s.194J (professional services)", "0.10", "0.10", 30000),
    _r("P-1961-b", "professional", "1961", A25, E25, "Income-tax Act 1961 s.194J (professional services)", "0.10", "0.10", 50000),
    _r("P-2025", "professional", "2025", A26, None, "Income-tax Act 2025 s.393(1) Table Sl. No. 6(iii)(a)", "0.10", "0.10", 50000),
    # --- Technical services (old 194J(b) -> new 393(1) Sl. 6(iii)(b)) ---
    _r("T-1961-a", "technical", "1961", A24, date(2025, 3, 31), "Income-tax Act 1961 s.194J (technical services)", "0.02", "0.02", 30000),
    _r("T-1961-b", "technical", "1961", A25, E25, "Income-tax Act 1961 s.194J (technical services)", "0.02", "0.02", 50000),
    _r("T-2025", "technical", "2025", A26, None, "Income-tax Act 2025 s.393(1) Table Sl. No. 6(iii)(b)", "0.02", "0.02", 50000),
    # --- Commission / brokerage (old 194H -> new 393(1) Sl. 1(ii)); rate fell 5% -> 2% on 1 Oct 2024 ---
    _r("H-1961-a", "commission", "1961", A24, date(2024, 9, 30), "Income-tax Act 1961 s.194H", "0.05", "0.05", 15000),
    _r("H-1961-b", "commission", "1961", date(2024, 10, 1), E24, "Income-tax Act 1961 s.194H", "0.02", "0.02", 15000),
    _r("H-1961-c", "commission", "1961", A25, E25, "Income-tax Act 1961 s.194H", "0.02", "0.02", 20000),
    _r("H-2025", "commission", "2025", A26, None, "Income-tax Act 2025 s.393(1) Table Sl. No. 1(ii)", "0.02", "0.02", 20000),
    # --- Rent (old 194-I -> new 393(1) Sl. 2(ii)); annual threshold raised 2.4L -> 6L from 1 Apr 2025 ---
    _r("RB-1961-a", "rent_building", "1961", A24, E24, "Income-tax Act 1961 s.194-I (land/building/furniture)", "0.10", "0.10", 240000),
    _r("RB-1961-b", "rent_building", "1961", A25, E25, "Income-tax Act 1961 s.194-I (land/building/furniture)", "0.10", "0.10", 600000),
    _r("RB-2025", "rent_building", "2025", A26, None, "Income-tax Act 2025 s.393(1) Table Sl. No. 2(ii)", "0.10", "0.10", 600000,
       note="A secondary source lists Rs 50,000/month here (looks like the 194-IB figure). Verify."),
    _r("RM-1961-a", "rent_machinery", "1961", A24, E24, "Income-tax Act 1961 s.194-I (plant/machinery)", "0.02", "0.02", 240000),
    _r("RM-1961-b", "rent_machinery", "1961", A25, E25, "Income-tax Act 1961 s.194-I (plant/machinery)", "0.02", "0.02", 600000),
    _r("RM-2025", "rent_machinery", "2025", A26, None, "Income-tax Act 2025 s.393(1) Table Sl. No. 2(ii)", "0.02", "0.02", 600000),
]

CATEGORIES = sorted({r.category for r in RULES})
NO_PAN_RATE = D("0.20")  # old s.206AA -> new s.397(2): higher of rate / 20% (general case)


def find_rule(category: str, on: date) -> Optional[Rule]:
    for r in RULES:
        if r.category == category and r.valid_from <= on and (r.valid_to is None or on <= r.valid_to):
            return r
    return None
