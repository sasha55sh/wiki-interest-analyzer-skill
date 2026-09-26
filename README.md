# wiki-interest-analyzer-skill

A Claude Code [Agent Skill](https://docs.claude.com/en/docs/claude-code/skills) that measures
how public interest in a topic changes over time and across languages, using Wikipedia
pageviews as a proxy.

Everything (code, docs, tests, evals) lives in the skill directory:
[`.claude/skills/wiki-interest/`](.claude/skills/wiki-interest/SKILL.md).

## Requirements

- [uv](https://docs.astral.sh/uv/) (installs Python 3.12 and the locked dependencies itself)
- Internet access to `wikimedia.org` / `wikidata.org`

## Use it in Claude Code

Open this repository in Claude Code. The skill is picked up automatically from
`.claude/skills/`. Ask e.g. "How has interest in astronomy changed in Ukrainian, Polish
and Czech Wikipedia?" or call it explicitly with `/wiki-interest`.

To use it in other projects, copy the folder to `~/.claude/skills/wiki-interest/`.

## Run it manually

```bash
uv run --directory .claude/skills/wiki-interest wiki-interest run "Astronomy" --langs uk,pl,cs --months 24
uv run --directory .claude/skills/wiki-interest wiki-interest report --run <run_id> --summary "..."
```

Results are written to `.claude/skills/wiki-interest/runs/<run_id>/`.

## Tests

```bash
cd .claude/skills/wiki-interest
uv sync --locked
uv run pytest
```
