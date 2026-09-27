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

## How to run commands

`<skill-dir>` below is this skill's base directory (the folder containing this
SKILL.md; in this repo it is `.claude/skills/wiki-interest`). Always pass it with
`--directory`, so commands work from any working directory:

```bash
uv run --directory <skill-dir> wiki-interest --help
```

On the first call `uv` creates `.venv` from `uv.lock` (can take a minute). Every command
prints one JSON object to stdout; a non-zero exit code means the JSON has an
`"error"` key with a `"hint"` on what to do next.

## Workflow

1. **Resolve the topic** in the user's language first:
   ```bash
   uv run --directory <skill-dir> wiki-interest resolve "Витинанка" --langs uk
   ```
   - `ambiguous_topic` → show the `candidates` (label + description) to the user and
     ask which one they mean. Do not guess.
   - `unknown_topic` → retry with the English name or a broader term.
   - Success → note the Wikidata QID from `qids` (internal only, never show it).

2. **Run the analysis** by QID (skips the search, so no second ambiguity). Pass
   `--lang` = the user's language (`uk` or `en`) so the chart labels match, and
   `--question` = the user's question in their words:
   ```bash
   uv run --directory <skill-dir> wiki-interest run --qids Q3220036 --langs uk,pl,cs --months 24 --lang uk \
     --question "<the user's question>"
   ```
   If the topic is unambiguous you can skip step 1: `run "Astronomy" --langs uk,pl,cs`.
   This starts a **session**. Keep `session_id` for the whole conversation (don't show it).

3. **Answer the user in chat** from the `results` in the JSON (see rules below) and
   offer the chart at `files.chart`.

4. **Handle follow-up questions in the same session.**
   - Answerable from data you already have (why confidence is low, what a spike means):
     just answer in chat, no command. Remember the question and your short answer.
   - Needs new data (another language, period or topic): add a step to the session.
     Omitted topic/`--langs`/`--months` are taken from the previous step:
     ```bash
     uv run --directory <skill-dir> wiki-interest run --session <session_id> --langs pl,en --lang uk \
       --question "<the follow-up question>"
     ```
     The JSON has `step` (2, 3, …) and its own `files.chart`. Never start a new session
     for a follow-up.

5. **Ask before making a PDF.** When the discussion settles, ask the user whether to
   generate a PDF report (e.g. "Згенерувати PDF-звіт?"). **Never generate it without a
   yes.** If they agree, make **one** PDF for the whole session:
   ```bash
   uv run --directory <skill-dir> wiki-interest report --session <session_id> --lang uk \
     --title "<the user's main request, in their words>" \
     --conclusion "<2-4 sentences: the answer to the main question>" \
     --recommendation "<action 1>" --recommendation "<action 2>" \
     --followup "<follow-up answered in chat>" "<1-2 sentence answer>" \
     --followup 2 "<1-2 sentence answer to follow-up step 2>"
   ```
   `--followup <step> "<answer>"` is for a follow-up that ran a new step (its question and
   chart are taken from the session); `--followup "<question>" "<answer>"` is for one you
   answered without new data. Pass them in the order they were asked.
   The PDF (`files.report`) contains: title = the main request, a small results table
   per language, critical issues (missing languages, low volume, short history are
   added automatically; add others with `--problem "..."`), your conclusion, your
   recommendations, the main chart, then each follow-up: question, short answer and its
   chart if it has one. A short report fits one page; long text continues on the next
   page. Write all text in the user's language, in plain words, without QIDs, session
   IDs or statistical jargon.

## Commands

| User's intent | Command |
|---|---|
| Compare interest across languages | `run "<topic>" --langs uk,pl,cs` |
| Check which languages have an article | `resolve "<topic>" --langs uk,pl,cs` |
| Use a known Wikidata QID | `run --qids Q333 --langs uk,pl` |
| Change the period | `--months 12` … `--months 60` (complete calendar months) |
| Follow-up needing new data | `run --session <session_id> --question "..." [--langs ...] [--months ...] [--qids ...]` |
| Another topic in the same conversation (e.g. Python, then JavaScript) | `run --session <session_id> --qids <QID> --question "..."` — one step **per topic** (several QIDs in one run would be summed) |
| PDF report (only after the user agrees) | `report --session <session_id> --lang uk --title "..." --conclusion "..." --recommendation "..." --followup ...` |

Outputs go to `<skill-dir>/runs/<session_id>/`: `session.json` (the steps),
`analysis-<step>.json` and `chart-<step>.png` for every step, and one `report.pdf`
after `report`. Downloads are cached in `<skill-dir>/.cache/`, so repeated runs are fast.

## Result fields (per language)

- `yoy_change_pct`: last 12 months vs the 12 before, in %. `null` if < 24 months of data.
- `trend_pct_per_year`: annualized log-linear trend, in %.
- `ci95`: 95% interval for `trend_pct_per_year` (block bootstrap). If it spans 0, the direction is not established.
- `mann_kendall_p`: p-value of the (seasonal) Mann-Kendall test; < 0.05 = significant.
- `confidence`: `high` | `medium` | `low` (rules in `references/methodology.md`).
- `caveats`: `short_history`, `low_volume`, `high_seasonality`, `bot_traffic_before_2020`.
- `baseline`: the same YoY/trend for the **whole** language edition of Wikipedia.
- `anomaly_months`: months with daily spikes (news, TV, viral links).
- `langs_missing` (top level): no article in that language, so no data.

## Rules for the answer

1. **State the confidence** for every language and why it is not higher.
2. **Mention the caveats** in plain words (see `references/interpretation.md`).
3. **Compare with `baseline`**: Wikipedia traffic overall is falling in many languages.
   A topic at −20% while its baseline is −25% is holding up, not declining.
4. **Don't overstate**: pageviews ≠ demand or willingness to pay. Frame results as
   "a signal to investigate further".
5. **Use numbers from the JSON only**; never invent or extrapolate.
6. **Hide technical IDs**: no QIDs or session IDs in the user-facing answer.
7. **Answer in the user's language.**

## Examples

```
User: "Чи зростає інтерес до астрономії в українській Вікіпедії?"
→ run "Astronomy" --langs uk --months 24
→ "За рік перегляди впали на 60% (вся українська Вікіпедія: −25%), тобто падіння
   сильніше за загальне. Впевненість середня: сильна сезонність (навчальний рік)."
```

```
User: "Чи зростає інтерес до писанки перед Великоднем?"
→ resolve "писанка" --langs uk → ambiguous → user picks "pysanka"
→ run --qids Q3233785 --langs uk,de --months 48 --lang uk --question "Чи зростає інтерес до писанки перед Великоднем?"
User: "Чому надійність для німецької низька?" → answer in chat (low_volume), no command
User: "А як у Польщі та англомовній аудиторії?"
→ run --session <session_id> --langs pl,en --lang uk --question "А як у Польщі та англомовній аудиторії?"   (step 2)
User: "Так, зроби PDF"
→ report --session <session_id> --lang uk --title "..." --conclusion "..." --recommendation "..." \
    --followup "Чому надійність для німецької низька?" "Мало переглядів…" --followup 2 "Польської статті немає…"
```

```
User: "Compare Mercury interest across languages"
→ resolve "Mercury" --langs uk,en,de → ambiguous_topic (planet, element, god)
→ ask the user → run --qids Q308 --langs uk,en,de
```

```
User: "Check Polish interest in <topic>"
→ run "<topic>" --langs pl → "pl" in langs_missing
→ "There is no Polish article, so no Polish data. Other languages show …"
```

## References

- `references/methodology.md`: data source, trend tests, confidence scoring, anomaly detection.
- `references/interpretation.md`: how to phrase conclusions and explain each caveat.
