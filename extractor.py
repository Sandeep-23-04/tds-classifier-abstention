"""Category extraction from a free-text payment narration.

Two interchangeable extractors, same output shape:
  keyword_extract(narration) -> (category | None, reason)      # non-AI baseline
  llm_extract(narration)     -> (category | None, reason)      # OpenRouter free model (see README)

The LLM is ONLY allowed to pick a category from a closed list (or say UNSURE).
It never outputs a rate, section or amount. Anything outside the list -> abstain.
"""
import json
import os
import re

from rules import CATEGORIES

KEYWORDS = {
    "contractor": ["contract", "labour", "manpower", "catering", "transport", "repair", "advertis",
                   "printing", "installation", "maintenance", "housekeeping", "security services"],
    "professional": ["legal", "consultan", "audit fee", "professional", "architect", "advocate",
                     "retainer", "chartered accountant", "ca fee"],
    "technical": ["technical", "support", "managed service", "engineering service", "call cent"],
    "commission": ["commission", "brokerage", "referral"],
    "rent_building": ["rent", "lease", "hire", "godown", "office space", "warehouse"],
    "rent_machinery": ["machinery", "equipment", "crane", "plant hire", "excavator"],
}


def keyword_extract(narration: str):
    t = narration.lower()
    hits = {c: [k for k in ks if k in t] for c, ks in KEYWORDS.items()}
    hits = {c: v for c, v in hits.items() if v}
    # machinery rent beats building rent when both words appear
    if "rent_machinery" in hits and "rent_building" in hits:
        del hits["rent_building"]
    if not hits:
        return None, "no keyword matched"
    if len(hits) > 1:
        return None, f"ambiguous: matched {sorted(hits)}"
    cat = next(iter(hits))
    return cat, f"keyword(s) {hits[cat]}"


SYSTEM_PROMPT = f"""You classify Indian vendor-payment narrations for TDS purposes.
Choose EXACTLY ONE category from: {CATEGORIES}.
If the narration could reasonably belong to two categories, is not a vendor payment
(e.g. a government levy, salary, reimbursement), or you are not sure, answer UNSURE.
Never give rates, sections or amounts. Reply as JSON: {{"category": "...", "evidence": "<quote from narration>"}}"""


def llm_extract(narration: str, model: str = None):
    """UNTESTED in the delivered run (no network to OpenRouter from the build sandbox)."""
    import requests  # imported lazily so the baseline runs with no dependencies

    key = os.environ["OPENROUTER_API_KEY"]
    model = model or os.environ.get("OPENROUTER_MODEL", "")  # pick a current free-tier model
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": model, "temperature": 0,
              "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                           {"role": "user", "content": narration}]},
        timeout=60,
    )
    text = r.json()["choices"][0]["message"]["content"]
    m = re.search(r"\{.*\}", text, re.S)
    try:
        obj = json.loads(m.group(0))
    except Exception:
        return None, "unparseable model output -> abstain"
    cat = obj.get("category")
    if cat not in CATEGORIES:                       # closed-list validation
        return None, f"model said {cat!r} -> abstain"
    ev = obj.get("evidence", "")
    if ev.lower() not in narration.lower():          # evidence must be a real quote
        return None, "evidence not found in narration -> abstain"
    return cat, f"llm; evidence={ev!r}"
