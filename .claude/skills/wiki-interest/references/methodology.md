# Methodology

How `wiki-interest run` turns a topic into the numbers in `analysis.json`.
Code: `scripts/wiki_interest/`.

## 1. Resolving the topic (`resolve.py`)

1. Search Wikidata (`wbsearchentities`) in English and in each requested language.
2. Drop Wikimedia internal items (disambiguation pages, categories, templates) and items
   without any Wikipedia article.
3. Keep Wikidata's search order (English hits first, then each language's): the first
   candidate is the best text match. It is not re-ranked by popularity, so a popular but
   different topic never silently replaces the exact match.
4. **Ambiguity**: if any of the next 3 candidates is in ≥ 30% as many Wikipedias as the
   first one (sitelink count), stop with `ambiguous_topic` and return the candidates.
   The agent asks the user and re-runs with `--qids`.
5. For each language take the article linked from the Wikidata item (so "Astronomy",
   "Астрономія" and "Astronomie" are the same topic), plus its redirects.

## 2. Pageviews (`fetch.py`, `cache.py`)

- Source: Wikimedia REST API, `per-article/{lang}.wikipedia/all-access/user/…/daily`.
  `user` excludes crawlers and traffic flagged as automated.
- Views of the article and up to 5 of its redirects are **summed** per day (the API
  counts a redirect's views separately from the target article). The 5 are the first
  ones the Wikipedia API lists (roughly the oldest), not the most visited; the rest are
  not counted.
- The whole language edition (`aggregate/{lang}.wikipedia/all-access/user`) is
  fetched too, as the `baseline`.
- The period is the last `--months` **complete** calendar months (UTC), so no
  partial month distorts the series. The API publishes a day's views with a delay, so a
  month counts as complete only 3 days after it ends.
- If an article was created during the period, its data start with the first complete
  month after creation (date of the first revision); the partial first month would
  otherwise look like growth. `baseline` uses the same months. The result has
  `first_month`; fewer than 24 months → `short_history`.
- A language with an article but no views in the period is reported in
  `langs_no_views`, not in `langs_missing` (no article).
- Daily data are cached in SQLite forever (past days never change); a repeated run
  only downloads the missing days. The last 3 days are never marked as cached, so data
  the API has not published yet are fetched again instead of staying zero.

## 3. Trend metrics (`analyze.py`)

Daily views are summed into calendar months.

| Field | Method |
|---|---|
| `yoy_change_pct` | Sum of the last 12 months / sum of the 12 before − 1. Needs ≥ 24 months, else `null`. |
| `trend_pct_per_year` | OLS slope of log(monthly views) vs month index, annualized: (e^(12·slope) − 1)·100. Months with 0 views are skipped; the rest keep their real month positions. |
| `ci95` | 95% percentile interval of the same slope from 1000 moving-block bootstrap resamples of the regression residuals (block = max(3, n/4) months). Blocks keep autocorrelation and seasonality, so the interval is honest about noisy series. |
| `mann_kendall_p` | ≥ 24 months: **seasonal** Mann-Kendall (period 12) compares each calendar month only with the same month in other years, so school-year or holiday cycles do not look like trends. 12–23 months: plain Mann-Kendall. < 12 months: not tested (`p = 1`). |
| `anomalies` | Daily spikes: views > 3× the 31-day rolling median, or robust z-score (rolling MAD, at least 1) > 5, **and** at least 20 views above the median (so 2 views vs a median of 1 is not a spike). Days without views count as 0. The 10 largest (by factor) are kept; reported by month. |
| `baseline` | `yoy_change_pct` and `trend_pct_per_year` of the whole language edition. |
| `seasonality` | Needs ≥ 24 months. The series is cut into complete 12-month **seasons counted back from the last month** (36 months ending in August → three Sep–Aug seasons; an incomplete leading remainder is dropped). Each season is compared with **its own mean**, so a long-term decline does not hide the yearly shape: `peak_vs_mean_pct = (peak / season mean − 1) × 100`, same for the low. `peak_repeats` = the peak falls in the same calendar month in every season. `peak_above_neighbours` = the peak month is higher than both adjacent months of the full series; if not, the "peak" is only the first month of a falling (or last of a rising) season, i.e. trend, not seasonality. `by_month` is the raw month × year table. |

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
- Only the linked article and up to 5 redirects (not chosen by views) are counted;
  related articles are not.
