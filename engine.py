"""Deterministic TDS engine. No LLM here. Every number comes from rules.py + arithmetic.

Input  : structured facts (category may come from an LLM/human, everything else is data)
Output : Decision(status in DEDUCT | NO_TDS | ESCALATE, amount, rate, citation, reasons)
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal as D, ROUND_HALF_UP
from typing import List, Optional

from rules import NO_PAN_RATE, find_rule


@dataclass
class Facts:
    category: Optional[str]            # one of rules.CATEGORIES, or None if unknown
    amount: D                          # invoice amount
    payee_type: str = "other"          # "individual_huf" | "other"
    payer_type: str = "company"        # "company" | "individual_huf_unaudited" | ...
    aggregate_before: D = D(0)         # earlier payments/credits to this payee this tax year
    credit_date: Optional[date] = None
    payment_date: Optional[date] = None
    gst_amount: D = D(0)
    gst_shown_separately: bool = False
    has_pan: bool = True
    lower_cert_rate: Optional[D] = None            # s.197 (1961) / s.395 (2025) certificate
    lower_cert_valid: Optional[tuple] = None       # (from, to)


@dataclass
class Decision:
    status: str
    amount: D = D(0)
    rate: D = D(0)
    base: D = D(0)
    cite: str = ""
    rule_id: str = ""
    reasons: List[str] = field(default_factory=list)
    needs_review: List[str] = field(default_factory=list)


def _rupee(x: D) -> D:
    return x.quantize(D(1), rounding=ROUND_HALF_UP)


def decide(f: Facts) -> Decision:
    d = Decision(status="ESCALATE")

    if f.category is None:
        d.reasons.append("Payment category unclear -> human must classify.")
        return d
    if f.payer_type != "company":
        d.reasons.append(f"Payer type '{f.payer_type}' is out of scope (individual/HUF payers follow a different rule).")
        return d

    dates = [x for x in (f.credit_date, f.payment_date) if x]
    if not dates:
        d.reasons.append("No credit/payment date -> cannot pick the applicable Act.")
        return d
    event = min(dates)  # TDS is triggered by the EARLIER of credit or payment

    rule = find_rule(f.category, event)
    if rule is None:
        d.reasons.append(f"No rule loaded for '{f.category}' on {event} (outside covered period).")
        return d
    d.rule_id, d.cite = rule.id, rule.cite
    if not rule.verified:
        d.needs_review.append(f"Rule {rule.id} not verified against primary text.")
    if rule.note:
        d.needs_review.append(rule.note)

    base = f.amount - f.gst_amount if f.gst_shown_separately else f.amount  # CBDT Circ. 23/2017 (verify)
    agg = f.aggregate_before + base

    if rule.single_threshold is not None and base > rule.single_threshold:
        applies, tds_base = True, base
        d.reasons.append(f"Single payment {base} > {rule.single_threshold}.")
    elif agg > rule.threshold:
        applies = True
        crossing = f.aggregate_before <= rule.threshold
        tds_base = agg if crossing else base
        d.reasons.append(
            f"Annual aggregate {agg} > {rule.threshold}"
            + (" (threshold crossed by this payment: deducting on the full aggregate - SIMPLIFYING ASSUMPTION, CA to confirm)." if crossing else ".")
        )
    else:
        d.status = "NO_TDS"
        d.cite, d.base = rule.cite, base
        d.reasons.append(f"Below threshold: aggregate {agg} <= {rule.threshold}.")
        return d

    rate = rule.rate_individual if f.payee_type == "individual_huf" else rule.rate_other
    if not f.has_pan:
        rate = max(rate, NO_PAN_RATE)
        d.reasons.append("Payee PAN missing -> higher rate (old s.206AA / new s.397(2)).")
        d.cite += " + no-PAN higher rate"
    if f.lower_cert_rate is not None and f.lower_cert_valid and f.lower_cert_valid[0] <= event <= f.lower_cert_valid[1]:
        rate = f.lower_cert_rate
        d.reasons.append("Valid lower-deduction certificate applied (old s.197 / new s.395).")
        d.cite += " + lower-deduction certificate"

    d.status, d.rate, d.base = "DEDUCT", rate, tds_base
    d.amount = _rupee(tds_base * rate)
    return d
