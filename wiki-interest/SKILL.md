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

## How to Find Topics (Internal Process)

When a user asks about a topic in their language, always:

1. **Resolve in source language first:**
   ```bash
   uv run wiki-interest resolve "<user_topic>" --langs <user_language>
   ```
   Example: User asks in Ukrainian → `resolve "Витинанка" --langs uk`

2. **Extract the Wikidata QID** from the response (e.g., `Q3220036`)

3. **If ambiguous**, show candidates to user and ask for clarification

4. **If not found**, try English translation or broader terms

5. **Run analysis with QID** (hide the QID from final report):
   ```bash
   uv run wiki-interest run "" --langs uk,pl,cs --qids Q3220036
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
6. **Hide technical IDs**: Never show Wikidata QIDs (Q123456) or run IDs in user-facing reports. Internal use only.

## How to Interpret Results

The skill returns JSON with these fields for each language:

- **yoy_change_pct**: Year-over-year % change (e.g., +15% = growing)
- **trend_pct_per_year**: Annualized trend from regression (e.g., −10% per year = declining)
- **confidence**: `high` | `medium` | `low` — reliability of the trend
- **caveats**: List of data quality issues (e.g., `low_volume`, `high_seasonality`)
- **ci95**: 95% confidence interval for the trend estimate
- **anomalies**: Detected spikes in pageviews (e.g., news-driven surges)

When translating results into business recommendations:

- **High confidence + positive trend**: High-priority opportunity; strong signal
- **High confidence + negative trend**: Lower priority; declining interest
- **Low/medium confidence**: Treat as exploratory signal; validate with user research
- **Missing language**: No Wikipedia article in that language; no data available
- **low_volume caveat**: Too few pageviews; statistical noise dominates; increase sample
- **high_seasonality caveat**: Strong seasonal patterns obscure the underlying trend; needs longer observation
- **short_history caveat**: Less than 24 months of data; insufficient for reliable annual trends

## Examples

These show the skill's flexible patterns, not exhaustive coverage. Users may ask any question about pageview trends.

### Example 1: Single language trend
```
User: "Is astronomy growing in Ukrainian Wikipedia?"
→ run "Astronomy" --langs uk --months 24
→ Extract: yoy_change_pct, confidence, caveats
→ Reply: "Interest [grew/declined] X% YoY. Confidence is [level] because [reason]."
```

### Example 2: Handling ambiguity
```
User: "Compare Mercury interest across languages"
→ resolve "Mercury" --langs uk,en,de
→ Result: ambiguous_topic with candidates (planet, element, god)
→ Ask user to clarify intent
→ run "" --langs uk,en,de --qids Q308 (after user picks)
```

### Example 3: Missing data
```
User: "Check Polish interest in [topic]"
→ run "[topic]" --langs pl
→ Result: "pl" in langs_missing (no Wikipedia article)
→ Reply: "No article in Polish. [Other languages show...]"
```

## References

- **Methodology**: See `references/methodology.md` for trend tests (Mann-Kendall), confidence scoring rules, anomaly detection.
- **Interpretation**: See `references/interpretation.md` for how to phrase conclusions and which caveats to mention.
