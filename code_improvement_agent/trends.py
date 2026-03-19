"""Trend tracking — saves score history and reports changes across runs."""

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

HISTORY_FILENAME = ".code-improve-history.json"


def _history_path(repo_path: str) -> Path:
    return Path(repo_path) / HISTORY_FILENAME


def save_run(repo_path: str, scores: dict, metadata: dict) -> None:
    """Append the current run to the history file in the analyzed repo."""
    history = _load_raw(repo_path)

    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "scores": {
            "quality": scores.get("quality", 0.0),
            "structure": scores.get("structure", 0.0),
            "security": scores.get("security", 0.0),
            "usefulness": scores.get("usefulness", 0.0),
            "overall": scores.get("overall", 0.0),
        },
        "findings_count": metadata.get("total_findings", 0),
        "files_analyzed": metadata.get("files_analyzed", 0),
        "mode": metadata.get("mode", "static"),
    }

    history["runs"].append(entry)

    try:
        _history_path(repo_path).write_text(
            json.dumps(history, indent=2), encoding="utf-8"
        )
    except OSError as exc:
        logger.warning("Could not write trend history: %s", exc)


def load_history(repo_path: str) -> list[dict]:
    """Load history and return the list of runs (may be empty)."""
    return _load_raw(repo_path).get("runs", [])


def format_trend_section(repo_path: str, current_scores: dict) -> str:
    """Return a Markdown section comparing current scores to history.

    If no previous runs exist, returns a short first-run notice.
    """
    runs = load_history(repo_path)

    # No history at all (first run — history not saved yet)
    if not runs:
        return _first_run_section()

    # If there's only the run we just saved, there's no *previous* to compare
    if len(runs) < 2:
        return _first_run_section()

    previous = runs[-2]  # second-to-last is the previous run
    prev_scores = previous["scores"]

    lines = [
        "## Trend Tracking",
        "",
        f"**Runs tracked:** {len(runs)}",
        "",
        "### Current vs Previous",
        "",
        "| Category   | Previous | Current | Change |",
        "|------------|----------|---------|--------|",
    ]

    categories = ["quality", "structure", "security", "usefulness", "overall"]
    regressions = []

    for cat in categories:
        prev = prev_scores.get(cat, 0.0)
        curr = current_scores.get(cat, 0.0)
        delta = round(curr - prev, 1)

        if delta > 0:
            arrow = "\u2191"
            sign = f"+{delta}"
        elif delta < 0:
            arrow = "\u2193"
            sign = str(delta)
            regressions.append((cat, prev, curr, delta))
        else:
            arrow = "\u2192"
            sign = "0.0"

        label = cat.capitalize() if cat != "overall" else "**Overall**"
        lines.append(f"| {label} | {prev} | {curr} | {arrow} {sign} |")

    lines.append("")

    # Best / worst historical
    all_overalls = [r["scores"].get("overall", 0.0) for r in runs]
    best = max(all_overalls)
    worst = min(all_overalls)
    lines.append(f"**Best overall score:** {best}  ")
    lines.append(f"**Worst overall score:** {worst}")
    lines.append("")

    # Regression warnings
    if regressions:
        lines.append("### Regression Warnings")
        lines.append("")
        for cat, prev, curr, delta in regressions:
            lines.append(
                f"- **{cat.capitalize()}** dropped from {prev} to {curr} ({delta})"
            )
        lines.append("")

    return "\n".join(lines)


def _first_run_section() -> str:
    return (
        "## Trend Tracking\n\n"
        "First run — no trend data available yet. "
        "Scores from this run will be used as the baseline for future comparisons."
    )


def _load_raw(repo_path: str) -> dict:
    """Read the JSON history file, returning a default structure on failure."""
    path = _history_path(repo_path)
    if not path.exists():
        return {"runs": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if "runs" not in data:
            data["runs"] = []
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read trend history: %s", exc)
        return {"runs": []}
