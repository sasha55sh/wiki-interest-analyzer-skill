---
name: wiki-interest
description: Analyzes public interest in a topic over time by comparing Wikipedia pageview trends across language editions. Resolves the matching article in each language, fetches daily pageviews from the Wikimedia API, tests for trends (Mann-Kendall), and produces charts and a written report. Use when the user asks how interest in a topic, person, event or product changed over time, wants to compare attention across countries or languages, or mentions Wikipedia pageviews.
compatibility: Requires Python 3.12+, uv, and internet access to the Wikimedia REST API.
metadata:
  author: sasha55sh
  version: "0.1.0"
---

# Wiki Interest

Measure how public interest in a topic changes over time and across languages,
using Wikipedia pageviews as a proxy.

## Setup

All commands run from the skill directory. `uv` installs dependencies on first run:

```bash
uv run wiki-interest --help
```

## Quick Start

**Full analysis in one command:**

```bash
cd wiki-interest
uv run wiki-interest run "Astronomy" --langs uk,pl,cs --months 24
```

This resolves the topic, fetches pageviews, analyzes trends, and produces a JSON summary + PNG chart.

**Output:** A `run-<timestamp>/` directory with `analysis.json` and `chart.png`.

## Decision Tree

| User's intent | Command(s) |
|---|---|
| Compare topic interest across languages | `run "<topic>" --langs uk,pl,cs` |
| Check if a specific language has the article | `resolve "<topic>" --langs uk` |
| Use a Wikidata QID directly (skip search) | `run "" --langs uk,pl --qids Q333` |
| Change the analysis period | `run "..." --months 6` or `--months 36` |

## Key Rules for Responses

1. **Cite the confidence level**: Always mention whether the result is `high`, `medium`, or `low` confidence.
2. **Explain caveats**: Include warnings like "short_history", "low_volume", "high_seasonality" from the analysis.
3. **Compare with normalization**: If the topic trend differs sharply from the whole-Wikipedia trend, mention this.
4. **Don't overstate**: Interest in Wikipedia ≠ readiness to pay for a product. Frame as "a signal to investigate further."
5. **Show numbers from JSON**: Extract YoY change, trend slope, confidence, and caveats directly from `analysis.json`.

## Examples

### Example 1: Single language, recent trend
```
User: "Is astronomy growing in interest in Ukrainian Wikipedia?"
→ run "Astronomy" --langs uk --months 24
→ Check JSON for: confidence, yoy_change_pct, caveats
→ Reply: "Based on the last 24 months, interest in astronomy [increased/decreased] by X%. 
   Confidence is [high/medium/low] because [reason from caveats]."
```

### Example 2: Comparison and ambiguity
```
User: "Compare interest in Mercury across Wikipedia versions"
→ resolve "Mercury" --langs uk,en,de
→ Error: ambiguous_topic (planet vs. element vs. Roman god)
→ Show candidates, ask user to clarify
→ run "" --langs uk,en,de --qids Q308  (planet)
```

### Example 3: Language not covered
```
User: "Check intermittent fasting interest in Polish"
→ run "Intermittent fasting" --langs pl,cs
→ Result: "pl" in langs_missing (no Wikipedia article in Polish)
→ Reply: "No Wikipedia article exists in Polish. Czech shows [data]."
```

## References

- **Methodology**: See `references/methodology.md` for trend tests (Mann-Kendall), confidence scoring rules, anomaly detection.
- **Interpretation**: See `references/interpretation.md` for how to phrase conclusions and which caveats to mention.
