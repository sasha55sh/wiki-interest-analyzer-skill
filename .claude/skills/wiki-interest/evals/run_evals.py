#!/usr/bin/env python
"""End-to-end evals of the CLI against the live Wikimedia APIs.

Unit tests (tests/) are offline and check the logic; these check that real topics still
resolve and analyse as expected. Each case runs one CLI command in a temporary
WIKI_INTEREST_HOME and checks the JSON output.

    uv run python evals/run_evals.py
"""

import contextlib
import io
import json
import os
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from wiki_interest import cli

Check = Callable[[dict], bool]


def run(argv: list[str]) -> dict:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        cli.main(argv)
    return json.loads(out.getvalue())


def has_results(*langs: str) -> Check:
    return lambda r: all(
        lang in r.get("langs_found", []) and {"confidence", "caveats", "first_month"} <= set(r["results"][lang])
        for lang in langs
    )


# (name, argv, checks); "{session}" is replaced by the session_id of the first case.
CASES: list[tuple[str, list[str], dict[str, Check]]] = [
    ("astronomy_uk_pl", ["run", "Astronomy", "--langs", "uk,pl", "--months", "24"], {
        "session_id returned": lambda r: bool(r.get("session_id")),
        "uk and pl analysed": has_results("uk", "pl"),
    }),
    ("followup_step", ["run", "--session", "{session}", "--langs", "cs", "--question", "And in Czech?"], {
        "same session, step 2": lambda r: r.get("step") == 2,
        "cs analysed": has_results("cs"),
    }),
    ("report", ["report", "--session", "{session}", "--lang", "uk", "--conclusion", "ok",
                "--followup", "2", "ok"], {
        "PDF written": lambda r: Path(r.get("files", {}).get("report", "")).is_file(),
    }),
    ("missing_language", ["run", "Intermittent fasting", "--langs", "pl,cs", "--months", "24"], {
        "no pl article": lambda r: r.get("langs_missing") == ["pl"],
        "cs analysed": has_results("cs"),
    }),
    ("ambiguous_topic", ["resolve", "Mercury", "--langs", "uk,en"], {
        "ambiguous_topic": lambda r: r.get("error") == "ambiguous_topic",
        ">= 2 candidates": lambda r: len(r.get("candidates", [])) >= 2,
        "hint": lambda r: bool(r.get("hint")),
    }),
    ("unknown_topic", ["resolve", "xyz_nonexistent_xyz", "--langs", "uk"], {
        "unknown_topic": lambda r: r.get("error") == "unknown_topic",
        "hint": lambda r: bool(r.get("hint")),
    }),
    ("qid_direct", ["run", "--qids", "Q333", "--langs", "uk,pl", "--months", "24"], {
        "uk and pl analysed": has_results("uk", "pl"),
    }),
    ("short_period", ["run", "Astronomy", "--langs", "uk", "--months", "6"], {
        "low confidence": lambda r: r["results"]["uk"]["confidence"] == "low",
        "short_history": lambda r: "short_history" in r["results"]["uk"]["caveats"],
    }),
]


def main() -> int:
    os.environ["WIKI_INTEREST_HOME"] = tempfile.mkdtemp(prefix="wiki-interest-evals-")
    session, passed = "", 0
    for name, argv, checks in CASES:
        try:
            result = run([a.replace("{session}", session) for a in argv])
            session = session or result.get("session_id", "")
            failed = [label for label, check in checks.items() if not check(result)]
        except Exception as e:  # noqa: BLE001 - a crashing case is a failed case
            failed = [f"{type(e).__name__}: {e}"]
        print(f"[{'PASS' if not failed else 'FAIL'}] {name}" + (f": {', '.join(failed)}" if failed else ""))
        passed += not failed
    print(f"\n{passed}/{len(CASES)} evals passed")
    return 0 if passed == len(CASES) else 1


if __name__ == "__main__":
    sys.exit(main())
