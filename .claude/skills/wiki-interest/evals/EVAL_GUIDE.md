# Evals

Two levels of checks:

| What | Command | Network | Checks |
|---|---|---|---|
| Unit tests | `uv run pytest` | no (API is mocked) | formulas, confidence, caveats, cache, sessions, PDF |
| Live evals | `uv run python evals/run_evals.py` | yes (Wikimedia) | real topics still resolve and analyse as expected |

Run both from the skill folder after `uv sync --locked`.

## Live evals

`evals/run_evals.py` runs CLI commands against the real APIs in a temporary
`WIKI_INTEREST_HOME` (nothing is written to the skill's `runs/` or cache) and checks the JSON:

| Case | Command | Expect |
|---|---|---|
| `astronomy_uk_pl` | `run "Astronomy" --langs uk,pl --months 24` | session started, both languages analysed |
| `followup_step` | `run --session <id> --langs cs` | step 2 of the same session, `cs` analysed |
| `report` | `report --session <id> --followup 2 "ok"` | one PDF for the session |
| `missing_language` | `run "Intermittent fasting" --langs pl,cs` | `pl` in `langs_missing`, `cs` analysed |
| `ambiguous_topic` | `resolve "Mercury" --langs uk,en` | `ambiguous_topic`, ≥ 2 candidates, a hint |
| `unknown_topic` | `resolve "xyz_nonexistent_xyz" --langs uk` | `unknown_topic`, a hint |
| `qid_direct` | `run --qids Q333 --langs uk,pl` | both languages analysed |
| `short_period` | `run "Astronomy" --langs uk --months 6` | `low` confidence, `short_history` |

Output: one `[PASS]`/`[FAIL] <case>: <failed checks>` line per case and a total; the exit
code is 0 only if all pass. Wikipedia changes over time (a Polish article on intermittent
fasting may appear), so a failing live case can mean the data changed, not the code.

To add a case, append `(name, argv, {label: check})` to `CASES`; a check gets the parsed
JSON and returns a bool. `{session}` in argv is the session of the first case.

## Skill behaviour in a conversation

The evals check the CLI, not how an agent uses it. To check the agent side, ask Claude
Code the example conversation from `SKILL.md` and verify the rules there: numbers only
from the JSON, confidence stated, missing language reported as missing, no QIDs or
session IDs in the answer, PDF only after the user agrees.
