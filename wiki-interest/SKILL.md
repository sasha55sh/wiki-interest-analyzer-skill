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

## Workflow

1. **Resolve articles** — find the article for the topic in each requested language:

   ```bash
   uv run wiki-interest resolve "<topic>" --langs uk,pl,cs
   ```

2. **Fetch pageviews** — download daily pageviews for the resolved articles.
3. **Analyze** — detect trends, peaks and differences between languages.
   See [references/methodology.md](references/methodology.md) for the statistical methods.
4. **Plot** — build charts of the time series.
5. **Report** — summarize the findings for the user.
   See [references/interpretation.md](references/interpretation.md) for how to read the results
   and which caveats to mention.

## Scripts

| Module | Purpose |
| --- | --- |
| `scripts/wiki_interest/cli.py` | Command-line entry point |
| `scripts/wiki_interest/resolve.py` | Topic → article title per language |
| `scripts/wiki_interest/fetch.py` | Wikimedia pageviews API client |
| `scripts/wiki_interest/analyze.py` | Trend and peak analysis |
| `scripts/wiki_interest/plot.py` | Charts |
| `scripts/wiki_interest/report.py` | Report generation |
