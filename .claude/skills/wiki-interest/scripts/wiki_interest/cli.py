"""Command-line interface for wiki-interest.

Entry point: wiki-interest <command> [options]
Commands: run, resolve, report
All output is JSON on stdout (errors too), so an agent can parse it directly.
"""

import argparse
import json
import sys
import time
from datetime import UTC, date, datetime, timedelta

from .analyze import analyze, baseline
from .cache import Cache, home
from .fetch import TOTAL, Client, daily_views
from .plot import plot_trends
from .resolve import TopicError, resolve

MAX_REDIRECTS = 5


def _run_id() -> str:
    """Generate a unique run ID based on timestamp."""
    return f"run-{int(time.time())}"


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
    """Resolve → Fetch → Analyze → Plot in one call."""
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

    run_id = _run_id()
    run_dir = home() / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "analysis.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (run_dir / "meta.json").write_text(
        json.dumps(
            {
                "topic": topic_label,
                "langs": args.langs,
                "period": [start.isoformat(), end.isoformat()],
                "qids": [i["qid"] for i in resolution.items],
                "articles": {
                    lang: [
                        {"title": a.title, "redirects_counted": len(a.redirects[:MAX_REDIRECTS])}
                        for a in arts
                    ]
                    for lang, arts in resolution.articles.items()
                },
                "langs_missing": [lang for lang in args.langs if lang not in results],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    plot_file = run_dir / "chart.png"
    plot_trends(results, output=str(plot_file), lang=args.lang)

    return {
        "run_id": run_id,
        "topic": topic_label,
        "period": [start.isoformat(), end.isoformat()],
        "langs_found": list(results.keys()),
        "langs_missing": [lang for lang in args.langs if lang not in results],
        "results": {
            lang: {k: v for k, v in r.items() if k not in ("monthly", "anomalies")}
            | {"anomaly_months": sorted({a["month"] for a in r["anomalies"]})}
            for lang, r in results.items()
        },
        "files": {"analysis": str(run_dir / "analysis.json"), "chart": str(plot_file)},
        "next_steps": (
            [
                "Answer the user in chat first and handle follow-up questions.",
                (
                    "Ask the user whether to generate a PDF report; only if they agree run: "
                    f'wiki-interest report --run {run_id} --lang <user language> --title "<user request>" '
                    '--conclusion "..." --recommendation "..." --recommendation "..."'
                ),
            ]
            if results
            else ["No data found"]
        ),
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
    """Build the short PDF report from one run, or compare topics from several runs.

    One run → table rows are languages. Several runs (one topic each) → rows are topics,
    labelled "<topic>" or "<topic> (<lang>)" when a run has several languages.
    """
    from .report import generate_report  # reportlab is only needed here

    loaded = []
    for run_id in args.run:
        run_dir = home() / "runs" / run_id
        if not run_dir.exists():
            return {"error": "run_not_found", "hint": f"Run {run_id} not found in {run_dir.parent}"}
        analysis_file = run_dir / "analysis.json"
        if not analysis_file.exists():
            return {"error": "missing_analysis", "hint": f"analysis.json not found in {run_id}"}
        meta_file = run_dir / "meta.json"
        loaded.append((
            run_dir,
            json.loads(analysis_file.read_text(encoding="utf-8")),
            json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else {},
        ))

    if len(loaded) == 1:
        out_dir, analysis, meta = loaded[0]
        rows = "languages"
    else:
        out_dir = home() / "runs" / f"compare-{int(time.time())}"
        out_dir.mkdir(parents=True, exist_ok=True)
        analysis, missing = {}, []
        for _, run_analysis, run_meta in loaded:
            topic = run_meta.get("topic") or "?"
            for lang, data in run_analysis.items():
                analysis[topic if len(run_analysis) == 1 else f"{topic} ({lang})"] = data
            missing += [f"{topic}: {lang}" for lang in run_meta.get("langs_missing") or []]
        periods = [m["period"] for _, _, m in loaded if m.get("period")]
        meta = {
            "topic": ", ".join(m.get("topic", "?") for _, _, m in loaded),
            "period": [min(p[0] for p in periods), max(p[1] for p in periods)] if periods else None,
            "langs_missing": missing,
        }
        rows = "topics"

    # Re-plot so the chart labels match the report language.
    chart_file = out_dir / f"chart_{args.lang}.png"
    plot_trends(analysis, output=str(chart_file), lang=args.lang)

    pdf_file = out_dir / "report.pdf"
    generate_report(
        topic=args.title or meta.get("topic", ""),
        analysis=analysis,
        chart_file=str(chart_file),
        conclusion=args.conclusion or "",
        output_file=str(pdf_file),
        meta=meta,
        recommendations=args.recommendation,
        problems=args.problem,
        lang=args.lang,
        rows=rows,
    )
    return {
        "run_id": args.run[0] if len(args.run) == 1 else args.run,
        "files": {"report": str(pdf_file), "chart": str(chart_file)},
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
    p_run.add_argument("--langs", required=True, help="Comma-separated languages (e.g., uk,pl,cs)")
    p_run.add_argument("--months", type=int, default=24, help="Complete months of data (default: 24)")
    p_run.add_argument("--qids", help="Comma-separated QIDs (skips topic search)")
    p_run.add_argument("--lang", default="en", help="Language of chart labels: uk or en (default: en)")
    p_run.set_defaults(func=cmd_run)

    p_resolve = sub.add_parser("resolve", help="Find articles for a topic in given languages")
    p_resolve.add_argument("topic", nargs="?", default="", help="Topic text (e.g., 'Astronomy')")
    p_resolve.add_argument("--langs", required=True, help="Comma-separated languages")
    p_resolve.add_argument("--qids", help="Skip search, use these QIDs directly")
    p_resolve.set_defaults(func=cmd_resolve)

    p_report = sub.add_parser("report", help="Build a short PDF report from a previous run")
    p_report.add_argument("--run", required=True, action="append",
                          help="Run ID; repeat to compare topics from several runs in one report")
    p_report.add_argument("--lang", default="en", help="Report language: uk or en (default: en)")
    p_report.add_argument("--title", help="The user's request, shown as the report topic")
    p_report.add_argument("--conclusion", help="Conclusion in the user's language")
    p_report.add_argument("--recommendation", action="append",
                          help="One recommendation; repeat the flag for more")
    p_report.add_argument("--problem", action="append",
                          help="Extra critical issue (data problems are added automatically)")
    p_report.set_defaults(func=cmd_report)

    args = parser.parse_args(argv)

    if getattr(args, "langs", None):
        args.langs = [lang.strip() for lang in args.langs.split(",") if lang.strip()]
    if getattr(args, "qids", None):
        args.qids = [q.strip() for q in args.qids.split(",") if q.strip()]
    else:
        args.qids = None
    if getattr(args, "months", 1) < 1:
        parser.error("--months must be >= 1")
    if args.command in ("run", "resolve") and not args.topic and not args.qids:
        parser.error("give a topic or --qids")

    try:
        result = args.func(args)
    except Exception as e:  # noqa: BLE001 - surface any failure as JSON for the agent
        print(json.dumps({"error": "internal_error", "message": str(e)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if "error" in result else 0


if __name__ == "__main__":
    sys.exit(main())
