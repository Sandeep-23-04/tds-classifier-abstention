# TDS Classifier with Abstention (prototype)

Smallest thing that shows the idea: **an LLM may only pick a payment category; a dated rules table and a deterministic engine decide section, rate and amount; anything unclear goes to a human.**

Jurisdiction: India, resident non-salary payments, Income-tax Act 1961 (before 1 Apr 2026) and Income-tax Act 2025 s.393 (from 1 Apr 2026). Payments from 1 Apr 2024 only.

## Files
| File | Role |
|---|---|
| `rules.py` | Versioned rule table (rate, threshold, citation, effective dates). Every rule has `verified=False`. |
| `engine.py` | Deterministic decision: earlier of credit/payment date, Act selection, GST exclusion, thresholds, no-PAN rate, lower-deduction certificate, rupee rounding, abstention. |
| `extractor.py` | `keyword_extract` (non-AI baseline) and `llm_extract` (OpenRouter, closed-list output, evidence must be a quote from the narration). |
| `run_tests.py` | 21 synthetic cases, two runs (engine-only, end-to-end). |

## Run
```bash
python3 run_tests.py            # baseline extractor, no dependencies
export OPENROUTER_API_KEY=...   # optional, free account
export OPENROUTER_MODEL=<a free-tier model id from openrouter.ai/models>
pip install -r requirements.txt   # only needed for --llm
python3 run_tests.py --llm      # LLM extractor
```

## Data
All 21 narrations, vendors and amounts are **made up**. No real client or personal data.

## Results (keyword baseline, as run)
- **Engine only (gold category given): 21/21.** This checks that the code does what I intended. It does not prove the legal content is right, because I wrote the expected values myself from the same understanding as the rules.
- **End-to-end with the keyword baseline: 18 PASS, 1 SAFE_MISS, 2 WRONG_CONFIDENT.**

Where it fails:
- **Case 16** (SAFE_MISS): "Drafting of shareholder agreement" has no keyword, so it escalates. Safe but unhelpful. Paraphrase is the reason an LLM is needed.
- **Case 17** (WRONG_CONFIDENT): "Rent-a-cab ... vehicle hire" matches `rent`/`hire` and is auto-classified as building rent. Vehicle hire is a genuine gray area (contract vs rent); a human should see it.
- **Case 18** (WRONG_CONFIDENT): "Professional tax payment - municipal corporation" matches `professional` and would wrongly deduct 10% TDS from a government levy.

## Not tested / limits (read before trusting)
- **The LLM extractor was not run.** The build sandbox had no access to OpenRouter. Its safeguards (closed list, evidence-quote check, abstain on anything else) are implemented but unmeasured. Run `--llm` yourself and record which model you used.
- **Keywords and tests were written by the same author in one session**, so the baseline numbers are illustrative, not a benchmark.
- **Rules are unverified.** They come from secondary sources and general knowledge. Two known discrepancies are flagged in `rules.py` (contractor 194C/194M thresholds, and the new-Act rent threshold). Check against the Act on the Income Tax Department portal before any real use.
- **Simplifying assumption:** when a payment crosses the annual threshold, TDS is computed on the full aggregate. Practice varies; a CA must confirm.
- Out of scope: non-residents, salary, TCS, payer = unaudited individual/HUF, 15G/15H declarations, filing returns, tax-treaty rates.
- Amounts, dates and payee type are given as structured fields; only the *category* is extracted from text.
