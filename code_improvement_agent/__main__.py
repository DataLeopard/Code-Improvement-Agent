"""CLI entry point — run with: python -m code_improvement_agent <repo_path>"""

import argparse
import json
import logging
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

    # Level 2: Smart mode
    parser.add_argument(
        "--smart",
        action="store_true",
        help="Use Claude API to validate findings and add AI-powered deep review",
    )
    parser.add_argument(
        "--auto-fix",
        action="store_true",
        help="Generate code patches for confirmed findings (requires --smart)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually apply generated patches to files (use with --auto-fix)",
    )
    parser.add_argument(
        "--cost",
        action="store_true",
        help="Estimate API cost before running smart mode (does not run analysis)",
    )

    args = parser.parse_args()

    repo = Path(args.repo_path).resolve()
    if not repo.is_dir():
        print(f"Error: '{args.repo_path}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    # Set up logging for smart mode
    if args.smart or args.auto_fix:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            stream=sys.stderr,
        )

    # Cost estimation mode
    if args.cost:
        from .agent import collect_files
        from .llm import estimate_cost
        file_contents = collect_files(str(repo))
        mode = "auto-fix" if args.auto_fix else "smart"
        est = estimate_cost(file_contents, mode)
        print(f"Estimated cost for --{mode} mode:", file=sys.stderr)
        print(f"  Files:         {est['file_count']}", file=sys.stderr)
        print(f"  Input tokens:  ~{est['input_tokens']:,}", file=sys.stderr)
        print(f"  Output tokens: ~{est['output_tokens']:,}", file=sys.stderr)
        print(f"  Est. cost:     ${est['estimated_cost_usd']:.4f}", file=sys.stderr)
        sys.exit(0)

    if not args.quiet:
        mode_str = "smart + auto-fix" if args.auto_fix else "smart" if args.smart else "static"
        print(f"Analyzing: {repo} (mode: {mode_str})", file=sys.stderr)

    report, metadata = run_analysis(
        str(repo),
        smart=args.smart,
        auto_fix=args.auto_fix,
        apply_fixes=args.apply,
    )

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
        mode = metadata.get("mode", "static")
        print(f"\nScore: {overall}/10 | Tag: {tag} | Recommendation: {rec} | "
              f"Findings: {findings} | Mode: {mode}",
              file=sys.stderr)


if __name__ == "__main__":
    main()
