"""Command-line interface for wiki-interest.

Entry point: wiki-interest <command> [options]
Commands: run, resolve
"""

import argparse
import json
import sys
from datetime import date, timedelta

from .analyze import analyze
from .cache import Cache, home
from .fetch import Client, daily_views
from .plot import plot_trends
from .resolve import TopicError, resolve


def _run_id() -> str:
    """Generate a unique run ID based on timestamp."""
    import time

    return f"run-{int(time.time())}"


def cmd_run(args):
    """Resolve → Fetch → Analyze → Plot in one call."""
    client = Client()
    cache = Cache()

    try:
        resolution = resolve(client, cache, args.langs, topic=args.topic, qids=args.qids)
    except TopicError as e:
        return {
            "error": e.code,
            "message": str(e),
            "hint": e.hint,
            "candidates": [
                {"qid": c["qid"], "label": c["label"], "description": c.get("description", "")}
                for c in e.candidates
            ],
        }

    run_id = _run_id()
    run_dir = home() / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    end = date.today().replace(day=1) - timedelta(days=1)  # Last full month
    start = end.replace(day=1) - timedelta(days=30 * (args.months - 1))

    targets = []
    for lang in args.langs:
        for article in resolution.articles[lang]:
            targets.append((article.project, article.title))
            for redirect in article.redirects[:5]:  # Limit redirects
                targets.append((article.project, redirect))

    views_data = daily_views(client, cache, targets, start, end, workers=4)

    results = {}
    for lang in args.langs:
        lang_views = {}
        for (proj, title), views in views_data.items():
            if proj == f"{lang}.wikipedia":
                lang_views.update(views)

        if lang_views:
            analysis = analyze(lang_views)
            results[lang] = analysis

    (run_dir / "analysis.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    plot_file = run_dir / "chart.png"
    plot_trends(results, output=str(plot_file))

    return {
        "run_id": run_id,
        "topic": args.topic,
        "langs_found": list(results.keys()),
        "langs_missing": [l for l in args.langs if l not in results],
        "results": {
            lang: {"confidence": r["confidence"], "caveats": r["caveats"]} for lang, r in results.items()
        },
        "files": {"analysis": str(run_dir / "analysis.json"), "chart": str(plot_file)},
        "next_steps": (
            [f"uv run wiki-interest report --run {run_id}"] if results else ["No data found"]
        ),
    }


def cmd_resolve(args):
    """Resolve topic → QID → article titles."""
    client = Client()
    cache = Cache()

    try:
        resolution = resolve(client, cache, args.langs, topic=args.topic, qids=args.qids)
        return {
            "qids": [{"qid": item["qid"], "label": item["label"]} for item in resolution.items],
            "articles": {
                lang: [{"title": a.title, "redirects": a.redirects} for a in articles]
                for lang, articles in resolution.articles.items()
            },
            "missing": resolution.missing,
        }
    except TopicError as e:
        return {"error": e.code, "hint": e.hint, "candidates": e.candidates}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="wiki-interest", description="Analyze Wikipedia pageview trends across languages."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Analyze a topic across languages (full pipeline)")
    p_run.add_argument("topic", nargs="?", default="", help="Topic text (e.g., 'Astronomy')")
    p_run.add_argument("--langs", required=True, help="Comma-separated languages (e.g., uk,pl,cs)")
    p_run.add_argument("--months", type=int, default=24, help="Months of data (default: 24)")
    p_run.add_argument("--qids", help="Comma-separated QIDs (skips topic search)")
    p_run.set_defaults(func=cmd_run)

    p_resolve = sub.add_parser("resolve", help="Find articles for a topic in given languages")
    p_resolve.add_argument("topic", help="Topic text (e.g., 'Astronomy')")
    p_resolve.add_argument("--langs", required=True, help="Comma-separated languages")
    p_resolve.add_argument("--qids", help="Skip search, use these QIDs directly")
    p_resolve.set_defaults(func=cmd_resolve)

    args = parser.parse_args(argv)

    if hasattr(args, "langs") and args.langs:
        args.langs = [l.strip() for l in args.langs.split(",")]
    if hasattr(args, "qids") and args.qids:
        args.qids = [q.strip() for q in args.qids.split(",")]
    else:
        args.qids = None

    try:
        result = args.func(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(
            json.dumps({"error": "internal_error", "message": str(e)}, ensure_ascii=False),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())


def cmd_report(args):
    """Generate report from a previous run."""
    run_dir = home() / "runs" / args.run_id
    if not run_dir.exists():
        return {"error": "run_not_found", "hint": f"Run {args.run_id} not found"}
    
    analysis_file = run_dir / "analysis.json"
    if not analysis_file.exists():
        return {"error": "missing_analysis", "hint": "analysis.json not found in run"}
    
    analysis = json.loads(analysis_file.read_text(encoding="utf-8"))
    return {
        "run_id": args.run_id,
        "analysis": analysis,
        "summary": {
            lang: {
                "confidence": data["confidence"],
                "yoy_change_pct": data["yoy_change_pct"],
                "caveats": data["caveats"],
            }
            for lang, data in analysis.items()
        },
    }
