"""Command-line interface for wiki-interest.

Entry point: wiki-interest <command> [options]
Commands: run, resolve, report
All output is JSON on stdout (errors too), so an agent can parse it directly.

One conversation = one session folder runs/<session_id>/. Step 1 is the main question;
each follow-up that needs new data adds a step (analysis-N.json, chart-N.png).
`report` turns the whole session into a single PDF.
"""

import argparse
import json
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from .analyze import analyze, baseline
from .cache import Cache, home
from .fetch import TOTAL, Client, daily_views
from .plot import plot_trends
from .resolve import TopicError, resolve

MAX_REDIRECTS = 5
DEFAULT_MONTHS = 24


def _session_dir(session_id: str) -> Path:
    return home() / "runs" / session_id


def _load_session(session_id: str) -> dict | None:
    f = _session_dir(session_id) / "session.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def _save_session(session_id: str, session: dict) -> None:
    (_session_dir(session_id) / "session.json").write_text(
        json.dumps(session, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _session_not_found(session_id: str) -> dict:
    return {
        "error": "session_not_found",
        "hint": f"Session {session_id} not found in {_session_dir(session_id).parent}. "
                "Start a new one with `run` without --session.",
    }


def _period(months: int, today: date | None = None) -> tuple[date, date]:
    """Last `months` complete calendar months: first day of the first month .. last day of the last."""
    today = today or datetime.now(UTC).date()  # Wikimedia days are UTC
    end = today.replace(day=1) - timedelta(days=1)
    y, m = end.year, end.month - (months - 1)
    while m < 1:
        y, m = y - 1, m + 12
    return date(y, m, 1), end


def _topic_error(e: TopicError) -> dict:
    return {
        "error": e.code,
        "message": str(e),
        "hint": e.hint,
        "candidates": [
            {"qid": c["qid"], "label": c["label"], "description": c.get("description", "")}
            for c in e.candidates
        ],
    }


def cmd_run(args):
    """Resolve → Fetch → Analyze → Plot in one call; a new session or a follow-up step."""
    session = {"steps": []}
    if args.session:
        session = _load_session(args.session)
        if session is None:
            return _session_not_found(args.session)
        prev = session["steps"][-1]
        if not args.topic and not args.qids:
            args.qids = prev["qids"]
        args.langs = args.langs or prev["langs"]
        args.months = args.months or prev["months"]
    args.months = args.months or DEFAULT_MONTHS

    client = Client()
    cache = Cache()

    try:
        resolution = resolve(client, cache, args.langs, topic=args.topic, qids=args.qids)
    except TopicError as e:
        return _topic_error(e)

    start, end = _period(args.months)

    targets = []
    for lang in args.langs:
        for article in resolution.articles.get(lang, []):
            targets.append((article.project, article.title))
            for redirect in article.redirects[:MAX_REDIRECTS]:
                targets.append((article.project, redirect))
        targets.append((f"{lang}.wikipedia", TOTAL))

    views_data = daily_views(client, cache, targets, start, end, workers=4)

    results = {}
    for lang in args.langs:
        project = f"{lang}.wikipedia"
        lang_views: dict[date, int] = {}
        for (proj, title), views in views_data.items():
            if proj != project or title == TOTAL:
                continue
            for d, v in views.items():
                lang_views[d] = lang_views.get(d, 0) + v  # article + its redirects

        if lang_views and any(lang_views.values()):
            analysis = analyze(lang_views)
            analysis["baseline"] = baseline(views_data.get((project, TOTAL), {}))
            results[lang] = analysis

    topic_label = args.topic or ", ".join(i["label"] for i in resolution.items)
    langs_missing = [lang for lang in args.langs if lang not in results]

    session_id = args.session or f"session-{int(time.time())}"
    run_dir = _session_dir(session_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    step = len(session["steps"]) + 1
    analysis_file = run_dir / f"analysis-{step}.json"
    analysis_file.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    plot_file = run_dir / f"chart-{step}.png"
    plot_trends(results, output=str(plot_file), lang=args.lang)

    session["steps"].append({
        "step": step,
        "question": args.question,
        "topic": topic_label,
        "qids": [i["qid"] for i in resolution.items],
        "langs": args.langs,
        "months": args.months,
        "period": [start.isoformat(), end.isoformat()],
        "articles": {
            lang: [
                {"title": a.title, "redirects_counted": len(a.redirects[:MAX_REDIRECTS])}
                for a in arts
            ]
            for lang, arts in resolution.articles.items()
        },
        "langs_missing": langs_missing,
    })
    _save_session(session_id, session)

    return {
        "session_id": session_id,
        "step": step,
        "topic": topic_label,
        "period": [start.isoformat(), end.isoformat()],
        "langs_found": list(results.keys()),
        "langs_missing": langs_missing,
        "results": {
            lang: {k: v for k, v in r.items() if k not in ("monthly", "anomalies")}
            | {"anomaly_months": sorted({a["month"] for a in r["anomalies"]})}
            for lang, r in results.items()
        },
        "files": {"analysis": str(analysis_file), "chart": str(plot_file)},
        "next_steps": [
            "Answer the user in chat first.",
            (
                "Follow-up that needs new data (other languages, period or topic): "
                f'wiki-interest run --session {session_id} --question "<follow-up>" '
                "[--langs ...] [--months ...] [--qids ...]  (omitted options are inherited)"
            ),
            (
                "Ask the user whether to generate a PDF report; only if they agree run: "
                f'wiki-interest report --session {session_id} --lang <user language> '
                '--title "<main request>" --conclusion "..." --recommendation "..." '
                '--followup <step> "<short answer>" --followup "<question>" "<short answer>"'
            ),
        ] if results else ["No data found"],
    }


def cmd_resolve(args):
    """Resolve topic → QID → article titles."""
    client = Client()
    cache = Cache()

    try:
        resolution = resolve(client, cache, args.langs, topic=args.topic, qids=args.qids)
    except TopicError as e:
        return _topic_error(e)
    return {
        "qids": [{"qid": item["qid"], "label": item["label"]} for item in resolution.items],
        "articles": {
            lang: [{"title": a.title, "redirects": a.redirects} for a in articles]
            for lang, articles in resolution.articles.items()
        },
        "missing": resolution.missing,
    }


def cmd_report(args):
    """One PDF for the whole session: the main answer, then each follow-up.

    --followup N "answer"          → follow-up data step N (its question and chart come from the session)
    --followup "question" "answer" → follow-up answered from existing data (text only)
    Data steps not mentioned in --followup are still included (question + chart).
    """
    from .report import generate_report  # reportlab is only needed here

    session = _load_session(args.session)
    if session is None:
        return _session_not_found(args.session)
    steps = session["steps"]
    run_dir = _session_dir(args.session)

    def load(step: dict) -> tuple[dict, Path]:
        n = step["step"]
        analysis = json.loads((run_dir / f"analysis-{n}.json").read_text(encoding="utf-8"))
        chart = run_dir / f"chart-{n}.png"
        plot_trends(analysis, output=str(chart), lang=args.lang)  # labels in the report language
        return analysis, chart

    def question(step: dict) -> str:
        return step.get("question") or step["topic"]

    followups, used = [], set()
    for first, answer in args.followup or []:
        if first.strip().isdigit():
            n = int(first)
            if not 2 <= n <= len(steps):
                return {
                    "error": "unknown_step",
                    "hint": f"Follow-up steps in this session: {list(range(2, len(steps) + 1)) or 'none'} "
                            "(step 1 is the main question). For a text-only follow-up pass "
                            '--followup "<question>" "<answer>".',
                }
            _, chart = load(steps[n - 1])
            used.add(n)
            followups.append({"question": question(steps[n - 1]), "answer": answer, "chart_file": str(chart)})
        else:
            followups.append({"question": first, "answer": answer, "chart_file": None})
    for step in steps[1:]:
        if step["step"] not in used:
            _, chart = load(step)
            followups.append({"question": question(step), "answer": "", "chart_file": str(chart)})

    main = steps[0]
    analysis, chart = load(main)
    pdf_file = run_dir / "report.pdf"
    generate_report(
        topic=args.title or question(main),
        analysis=analysis,
        chart_file=str(chart),
        conclusion=args.conclusion or "",
        output_file=str(pdf_file),
        meta=main,
        recommendations=args.recommendation,
        problems=args.problem,
        lang=args.lang,
        followups=followups,
    )
    return {
        "session_id": args.session,
        "files": {
            "report": str(pdf_file),
            "charts": [str(run_dir / f"chart-{s['step']}.png") for s in steps],
        },
        "summary": {
            lang: {
                "confidence": data["confidence"],
                "yoy_change_pct": data["yoy_change_pct"],
                "trend_pct_per_year": data["trend_pct_per_year"],
                "caveats": data["caveats"],
            }
            for lang, data in analysis.items()
        },
    }


def main(argv: list[str] | None = None) -> int:
    # Windows consoles default to cp1252; topic names are often Cyrillic.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        prog="wiki-interest", description="Analyze Wikipedia pageview trends across languages."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Analyze a topic across languages (full pipeline)")
    p_run.add_argument("topic", nargs="?", default="", help="Topic text (e.g., 'Astronomy')")
    p_run.add_argument("--langs", help="Comma-separated languages (e.g., uk,pl,cs)")
    p_run.add_argument("--months", type=int,
                       help=f"Complete months of data (default: {DEFAULT_MONTHS}, or the previous step's)")
    p_run.add_argument("--qids", help="Comma-separated QIDs (skips topic search)")
    p_run.add_argument("--lang", default="en", help="Language of chart labels: uk or en (default: en)")
    p_run.add_argument("--session", help="Add this run as a follow-up step to an existing session; "
                                         "omitted topic/--langs/--months are taken from the previous step")
    p_run.add_argument("--question", help="The user's question for this step, in their words")
    p_run.set_defaults(func=cmd_run)

    p_resolve = sub.add_parser("resolve", help="Find articles for a topic in given languages")
    p_resolve.add_argument("topic", nargs="?", default="", help="Topic text (e.g., 'Astronomy')")
    p_resolve.add_argument("--langs", required=True, help="Comma-separated languages")
    p_resolve.add_argument("--qids", help="Skip search, use these QIDs directly")
    p_resolve.set_defaults(func=cmd_resolve)

    p_report = sub.add_parser("report", help="Build one PDF report for a whole session")
    p_report.add_argument("--session", required=True, help="Session ID from `run`")
    p_report.add_argument("--lang", default="en", help="Report language: uk or en (default: en)")
    p_report.add_argument("--title", help="The user's main request, shown as the report topic")
    p_report.add_argument("--conclusion", help="Answer to the main question, in the user's language")
    p_report.add_argument("--recommendation", action="append",
                          help="One recommendation; repeat the flag for more")
    p_report.add_argument("--problem", action="append",
                          help="Extra critical issue (data problems are added automatically)")
    p_report.add_argument("--followup", nargs=2, action="append", metavar=("STEP_OR_QUESTION", "ANSWER"),
                          help='Short answer to a follow-up: --followup 2 "answer" for data step 2, or '
                               '--followup "question" "answer" for one answered without new data; repeat')
    p_report.set_defaults(func=cmd_report)

    args = parser.parse_args(argv)

    if getattr(args, "langs", None):
        args.langs = [lang.strip() for lang in args.langs.split(",") if lang.strip()]
    if getattr(args, "qids", None):
        args.qids = [q.strip() for q in args.qids.split(",") if q.strip()]
    else:
        args.qids = None
    if (getattr(args, "months", None) or 1) < 1:
        parser.error("--months must be >= 1")
    has_session = bool(getattr(args, "session", None)) and args.command == "run"
    if args.command in ("run", "resolve") and not args.topic and not args.qids and not has_session:
        parser.error("give a topic or --qids")
    if args.command in ("run", "resolve") and not args.langs and not has_session:
        parser.error("--langs is required")

    try:
        result = args.func(args)
    except Exception as e:  # noqa: BLE001 - surface any failure as JSON for the agent
        print(json.dumps({"error": "internal_error", "message": str(e)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if "error" in result else 0


if __name__ == "__main__":
    sys.exit(main())
