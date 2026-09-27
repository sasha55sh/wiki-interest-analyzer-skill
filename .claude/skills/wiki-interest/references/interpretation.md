# Interpreting results

How to turn `analysis.json` into an answer for the user.

## Order of an answer

1. One-sentence verdict per language: direction + size ("down 16% over the year").
2. Context from `baseline` (is the topic moving with Wikipedia as a whole or not?).
3. Confidence and the reason it is not higher.
4. Caveats that matter, in plain words.
5. What this means / what to check next. No overclaiming.

## Direction

Use `ci95` and `mann_kendall_p` together:

| Situation | Say |
|---|---|
| `ci95` entirely > 0 and p < 0.05 | "Interest is growing" |
| `ci95` entirely < 0 and p < 0.05 | "Interest is declining" |
| `ci95` spans 0, or p ≥ 0.05 | "No clear trend; changes are within normal fluctuation" |

Do not call a +5% YoY "growth" if the interval spans zero.

## Relative to the baseline

Compute topic − baseline for `yoy_change_pct` (or `trend_pct_per_year`):

| Topic vs baseline | Say |
|---|---|
| Both negative, topic ≈ baseline (±5 pp) | "Falls in line with Wikipedia overall; no topic-specific decline" |
| Topic much lower | "Declines faster than Wikipedia overall: interest is really fading" |
| Topic higher | "Holds up better than Wikipedia overall / gains share" |

## Confidence

| Level | Phrase |
|---|---|
| `high` | "reliable signal" |
| `medium` | "likely, but check" + name the missing point (volume, history, or significance) |
| `low` | "exploratory only; too little data / no significant trend" |

## Caveats in plain words

| Caveat | Explain as |
|---|---|
| `short_history` | "Less than two years of data, so we can't compare year over year." |
| `low_volume` | "The article gets few views (median < 300/month); small random changes look big." |
| `high_seasonality` | "Views swing a lot from month to month (e.g. school year, holidays), so the trend is less certain." |
| `bot_traffic_before_2020` | "Early data may include some undetected bot traffic." |
| language in `langs_missing` | "There is no article in that language, so there is no data, which is not the same as zero interest." |
| language in `langs_no_views` | "There is an article in that language, but it had no views in this period (or is too new for a full month)." |
| `first_month` later than the period start | "The article only appeared in <month>, so the numbers cover a shorter period." |
| `anomaly_months` | "Spikes in <months>, likely news or media coverage; they can inflate a single year." |

## Business framing

- Wikipedia interest is a **proxy for attention**, not purchase intent.
- `high` + growing (and above baseline): worth prioritizing for further research.
- `high` + declining (below baseline): lower priority, or find out why.
- `medium`/`low`: an exploratory signal only; validate with search data, surveys or sales.

## Don'ts

- Don't show QIDs or run IDs.
- Don't invent numbers or forecast beyond the data.
- Don't compare absolute view counts across languages as "market size" without
  noting that language editions differ hugely in total traffic.
