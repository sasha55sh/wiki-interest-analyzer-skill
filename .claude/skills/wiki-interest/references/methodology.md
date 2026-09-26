# Methodology

How `wiki-interest run` turns a topic into the numbers in `analysis.json`.
Code: `scripts/wiki_interest/`.

## 1. Resolving the topic (`resolve.py`)

1. Search Wikidata (`wbsearchentities`) in English and in each requested language.
2. Drop Wikimedia internal items (disambiguation pages, categories, templates).
3. Rank candidates by how many Wikipedias have an article (sitelink count).
4. **Ambiguity**: if any of the next 3 candidates has ≥ 30% of the top candidate's
   sitelinks, stop with `ambiguous_topic` and return the candidates. The agent asks
   the user and re-runs with `--qids`.
5. For each language take the article linked from the Wikidata item (so "Astronomy",
   "Астрономія" and "Astronomie" are the same topic), plus its redirects.

## 2. Pageviews (`fetch.py`, `cache.py`)

- Source: Wikimedia REST API, `per-article/{lang}.wikipedia/all-access/user/…/daily`.
  `user` excludes crawlers and traffic flagged as automated.
- Views of the article and its first 5 redirects are **summed** per day (the API
  counts a redirect's views separately from the target article).
- The whole language edition (`aggregate/{lang}.wikipedia/all-access/user`) is
  fetched too, as the `baseline`.
- The period is the last `--months` **complete** calendar months (UTC), so no
  partial month distorts the series.
- Daily data are cached in SQLite forever (past days never change); a repeated run
  only downloads the missing days.

## 3. Trend metrics (`analyze.py`)

Daily views are summed into calendar months.

| Field | Method |
|---|---|
| `yoy_change_pct` | Sum of the last 12 months / sum of the 12 before − 1. Needs ≥ 24 months, else `null`. |
| `trend_pct_per_year` | OLS slope of log(monthly views) vs month index, annualized: (e^(12·slope) − 1)·100. Months with 0 views are skipped. |
| `ci95` | 95% percentile interval of the same slope from 1000 moving-block bootstrap resamples of the regression residuals (block = max(3, n/4) months). Blocks keep autocorrelation and seasonality, so the interval is honest about noisy series. |
| `mann_kendall_p` | ≥ 24 months: **seasonal** Mann-Kendall (period 12) compares each calendar month only with the same month in other years, so school-year or holiday cycles do not look like trends. 12–23 months: plain Mann-Kendall. < 12 months: not tested (`p = 1`). |
| `anomalies` | Daily spikes: views > 3× the 31-day rolling median, or robust z-score (rolling MAD) > 5. Reported by month, up to 10. |
| `baseline` | `yoy_change_pct` and `trend_pct_per_year` of the whole language edition. |

## 4. Caveats

| Caveat | Rule | Meaning |
|---|---|---|
| `short_history` | < 24 months | No YoY; trend may be one season. |
| `low_volume` | median < 300 views/month | Random noise dominates. |
| `high_seasonality` | coefficient of variation of monthly views > 0.5 | Strong swings (seasonal or spikes); the trend line is less reliable. |
| `bot_traffic_before_2020` | data before April 2020 | Older data has more undetected automated traffic. |

## 5. Confidence score

One point for each:

1. **Volume**: median ≥ 1000 views/month.
2. **History**: ≥ 24 months of data.
3. **Significance**: `mann_kendall_p` < 0.05 **and** `ci95` does not include 0.

| Points | Confidence |
|---|---|
| 3 | `high` |
| 2 | `medium` |
| 0–1 | `low` |

## Limits

- Pageviews measure attention on Wikipedia, not demand. Search engines' AI answers
  and changes in Google's layout move Wikipedia traffic independently of the topic;
  that is what `baseline` is for.
- One language ≠ one country (e.g. English, Russian, Spanish are read in many countries).
- Only the linked article and 5 redirects are counted; related articles are not.
