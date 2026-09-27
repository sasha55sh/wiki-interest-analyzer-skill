---
name: wiki-interest
description: Measures public interest in a topic over time from Wikipedia pageviews and compares it across language editions (countries). Finds the article in each language, fetches the views, computes trend, year-over-year change, seasonality and reliability, draws charts and writes a PDF report. Use when the user asks whether interest in a topic, product, person or event is growing, when it peaks, or which countries/languages to launch in or research next, or mentions Wikipedia pageviews.
compatibility: Requires Python 3.12+, uv, and internet access to the Wikimedia REST API.
metadata:
  author: sasha55sh
  version: "0.1.0"
---

# Wiki Interest

All commands run as `uv run --directory <skill-dir> wiki-interest ...`, where `<skill-dir>` is
the folder containing this file. The first call creates `.venv` from `uv.lock` (up to a minute).
Every command prints one JSON object; on failure it has `"error"` and a `"hint"` on what to do.

## Workflow

1. **Pick the languages.** Countries → their Wikipedia language codes (Ukraine `uk`,
   Poland `pl`, Germany `de`, Czechia `cs`, …; "English-speaking audience" = `en`). If the
   user gives no languages or countries, ask.

2. **Find the topic in the language of the user's request**, not by translating it:
   ```bash
   uv run --directory <skill-dir> wiki-interest resolve "писанка" --langs uk
   ```
   - `ambiguous_topic` → show the candidates (label + description), ask which one. Don't guess.
   - `unknown_topic` → try the English name or a broader term.
   - Success → take the QID from `qids`. It links the same article in every language.

3. **Run the analysis by QID.** `--lang` = the user's language for chart labels (`uk` or
   `en`; others fall back to English), `--question` = the user's question in their words:
   ```bash
   uv run --directory <skill-dir> wiki-interest run --qids Q3233785 --langs uk,de --months 48 --lang uk \
     --question "<the user's question>"
   ```
   Default period is 24 complete months; use 36+ for seasonality questions. This starts a
   **session**: keep `session_id` for the whole conversation. Answer in chat (rules below)
   and offer the chart at `files.chart`.

4. **Follow-up questions stay in the same session.**
   - Answerable from the data you have (why reliability is low, when the peak is): answer
     in chat, no command. Remember the question and your short answer for the PDF.
   - Needs new data (other languages, period or topic): add a step. Omitted topic,
     `--langs` and `--months` are taken from the previous step:
     ```bash
     uv run --directory <skill-dir> wiki-interest run --session <session_id> --langs pl,en --lang uk \
       --question "<the follow-up question>"
     ```
     For another topic pass its `--qids` (one topic per step; several QIDs in one run are summed).
     Never start a new session for a follow-up.

5. **PDF only after the user says yes.** When the discussion settles, ask
   ("Згенерувати PDF-звіт?"). Then make **one** PDF for the whole session:
   ```bash
   uv run --directory <skill-dir> wiki-interest report --session <session_id> --lang uk \
     --title "<the main request, in the user's words>" \
     --conclusion "<2-4 sentences answering the main question>" \
     --recommendation "<action 1>" --recommendation "<action 2>" \
     --followup "<question answered in chat>" "<1-2 sentence answer>" \
     --followup 2 "<1-2 sentence answer to step 2>"
   ```
   `--followup <step> "<answer>"` = a follow-up that ran a new step (question and chart
   come from the session); `--followup "<question>" "<answer>"` = one answered without new
   data. Keep the order in which they were asked. Tables, the chart, the seasonality section
   and data problems (missing languages, low volume, short history) are added automatically;
   add other issues with `--problem "..."`. Give the user the path from `files.report`.

## Result fields (per language, in `results`)

- `yoy_change_pct`: last 12 months vs the 12 before, %. `null` with < 24 months.
- `trend_pct_per_year`, `ci95`, `mann_kendall_p`: trend per year, its 95% interval, and
  significance (< 0.05). Growing/declining only if the interval excludes 0 and p < 0.05.
- `confidence`: `high` | `medium` | `low`; `caveats`: `short_history`, `low_volume`,
  `high_seasonality`, `bot_traffic_before_2020`.
- `baseline`: the same YoY/trend for the **whole** Wikipedia in that language.
- `anomaly_months`: months with one-day spikes (news, TV, viral links).
- `seasonality` (`null` with < 24 months):
  - `by_month`: month × year table, e.g. `{"11": {"2023": 2088, "2024": 973}}`;
  - `seasons`: 12-month seasons counted back from the last month, each with `mean`,
    `peak_month`/`peak_views`/`peak_vs_mean_pct`, `low_month`/`low_views`/`low_vs_mean_pct`,
    `months_above_mean`, `peak_above_neighbours` (`false` = the "peak" is just the trend);
  - `peak_calendar_month` + `peak_repeats` (same peak month every season?); same for `low_`.
- `langs_missing` (top level): no article in that language.

## Rules for the answer

1. **Numbers only from the JSON.** Never invent, extrapolate, or write your own code to
   recompute them; seasonality and "same month in different years" come from `seasonality`.
2. **State the confidence** for each language and why it is not higher; explain caveats in
   plain words and compare with `baseline` (see `references/interpretation.md`).
3. **Missing language = a fact, not a gap to fill.** Say there is no article in that
   language, so there is no data (not zero interest), and suggest a close alternative
   (a neighbouring country's language, or `en`). Don't substitute other data.
4. **Don't overstate**: pageviews show attention, not demand or willingness to pay.
   Frame results as a signal to check further.
5. **No QIDs or session IDs** in anything the user sees. Answer in the user's language.

## Example conversation

```
User: "Чи зростає інтерес до писанки перед Великоднем?"
→ resolve "писанка" --langs uk → ambiguous → user picks "pysanka" (egg-decorating tradition)
→ run --qids Q3233785 --langs uk,de --months 48 --lang uk --question "Чи зростає інтерес до писанки перед Великоднем?"
→ answer: trend and YoY vs baseline, peak month from seasonality, confidence and caveats
User: "Чому надійність для німецької низька?"  → answer from caveats (low_volume), no command
User: "А як у Польщі та англомовній аудиторії?"
→ run --session <session_id> --langs pl,en --lang uk --question "А як у Польщі та англомовній аудиторії?"   (step 2)
→ "pl" in langs_missing → say there is no Polish article; report English
User: "Так, зроби PDF"
→ report --session <session_id> --lang uk --title "..." --conclusion "..." --recommendation "..." \
    --followup "Чому надійність для німецької низька?" "..." --followup 2 "..."
```

## References

- `references/methodology.md`: data source, formulas, seasonality, confidence rules.
- `references/interpretation.md`: how to phrase each result and caveat.
