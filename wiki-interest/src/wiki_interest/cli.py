import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="wiki-interest",
        description="Analyze Wikipedia pageview trends across languages.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_resolve = sub.add_parser("resolve", help="Find articles for a topic in given languages")
    p_resolve.add_argument("topic")
    p_resolve.add_argument("--langs", required=True, help="Comma-separated, e.g. uk,pl,cs")

    args = parser.parse_args(argv)

    if args.command == "resolve":
        print(f"TODO: resolve '{args.topic}' for {args.langs}")

    return 0


if __name__ == "__main__":
    sys.exit(main())