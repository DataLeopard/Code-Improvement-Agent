"""CLI entry point — run with: python -m code_improvement_agent <repo_path>"""

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from .agent import run_analysis


def main():
    parser = argparse.ArgumentParser(
        prog="code-improvement-agent",
        description="Analyze a repository and produce a structured improvement report.",
    )
    parser.add_argument(
        "repo_path",
        nargs="?",
        default=".",
        help="Path to the repository to analyze (default: current directory)",
    )
    parser.add_argument(
        "-o", "--output",
        help="Write report to file instead of stdout",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Also output metadata as JSON (to <output>.json)",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Only output the report, no progress messages",
    )

    args = parser.parse_args()

    repo = Path(args.repo_path).resolve()
    if not repo.is_dir():
        print(f"Error: '{args.repo_path}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    if not args.quiet:
        print(f"Analyzing: {repo}", file=sys.stderr)

    report, metadata = run_analysis(str(repo))

    if isinstance(report, str) and report.startswith("ERROR"):
        print(report, file=sys.stderr)
        sys.exit(1)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(report, encoding="utf-8")
        if not args.quiet:
            print(f"Report written to: {output_path}", file=sys.stderr)

        if args.json_output:
            json_path = output_path.with_suffix(".json")
            json_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
            if not args.quiet:
                print(f"Metadata written to: {json_path}", file=sys.stderr)
    else:
        print(report)

        if args.json_output:
            print("\n---\n## Metadata (JSON)\n")
            print(json.dumps(metadata, indent=2))

    if not args.quiet:
        overall = metadata.get("scores", {}).get("overall", "?")
        tag = metadata.get("tag", "?")
        rec = metadata.get("recommendation", "?")
        findings = metadata.get("total_findings", 0)
        print(f"\nScore: {overall}/10 | Tag: {tag} | Recommendation: {rec} | Findings: {findings}",
              file=sys.stderr)


if __name__ == "__main__":
    main()
