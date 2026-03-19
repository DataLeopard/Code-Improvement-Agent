"""Report generator — produces structured Markdown reports."""

import os
from datetime import datetime
from .analyzers.base import AnalyzerResult, Finding
from .scoring import RepoScore


def generate_report(
    repo_path: str,
    app_description: str,
    analyzer_results: list[AnalyzerResult],
    score: RepoScore,
    file_list: list[str],
) -> str:
    """Generate a full Markdown improvement report."""
    sections = [
        _header(repo_path),
        _summary(app_description, score, analyzer_results, file_list),
        _top_improvements(analyzer_results),
        _file_analysis(analyzer_results),
        _next_iteration(analyzer_results, score),
        _footer(),
    ]
    return "\n\n".join(sections)


def _header(repo_path: str) -> str:
    name = os.path.basename(repo_path)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""# Code Improvement Report: {name}

**Generated:** {timestamp}
**Agent Version:** 1.0.0"""


def _summary(description: str, score: RepoScore,
             results: list[AnalyzerResult], files: list[str]) -> str:
    total_findings = sum(len(r.findings) for r in results)
    critical = sum(1 for r in results for f in r.findings if f.severity == "critical")
    high = sum(1 for r in results for f in r.findings if f.severity == "high")

    recommendation_labels = {
        "promote": "PROMOTE to core system",
        "maintain": "MAINTAIN — keep improving",
        "archive": "Consider ARCHIVING",
    }

    return f"""## Summary

**What this app does:** {description}

**Files analyzed:** {len(files)}
**Total findings:** {total_findings} ({critical} critical, {high} high)

### Scores (1-10)

| Category   | Score |
|------------|-------|
| Quality    | {score.quality} |
| Structure  | {score.structure} |
| Security   | {score.security} |
| Usefulness | {score.usefulness} |
| **Overall**| **{score.overall}** |

**Tag:** `{score.tag}`
**Recommendation:** {recommendation_labels.get(score.recommendation, score.recommendation)}"""


def _top_improvements(results: list[AnalyzerResult]) -> str:
    # Collect all findings, sort by severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    all_findings = []
    for r in results:
        all_findings.extend(r.findings)

    all_findings.sort(key=lambda f: severity_order.get(f.severity, 99))
    top = all_findings[:5]

    if not top:
        return "## Top 5 Improvements\n\nNo significant issues found."

    lines = ["## Top 5 Highest-Impact Improvements\n"]
    for i, f in enumerate(top, 1):
        icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}.get(f.severity, "⚪")
        lines.append(f"### {i}. {icon} [{f.severity.upper()}] {f.title}")
        lines.append(f"**File:** `{f.file}`")
        if f.line:
            lines.append(f"**Line:** {f.line}")
        lines.append(f"\n{f.description}\n")
        lines.append(f"**Suggestion:** {f.suggestion}")
        if f.code_before:
            lines.append(f"\n```\n# Before:\n{f.code_before}\n```")
        if f.code_after:
            lines.append(f"\n```\n# After:\n{f.code_after}\n```")
        lines.append("")

    return "\n".join(lines)


def _file_analysis(results: list[AnalyzerResult]) -> str:
    """Group findings by file for file-by-file view."""
    by_file: dict[str, list[Finding]] = {}

    for r in results:
        for f in r.findings:
            files_key = f.file
            if files_key not in by_file:
                by_file[files_key] = []
            by_file[files_key].append(f)

    if not by_file:
        return "## File-by-File Analysis\n\nAll files look clean."

    lines = ["## File-by-File Analysis\n"]

    for filepath in sorted(by_file.keys()):
        findings = by_file[filepath]
        lines.append(f"### `{filepath}`")
        lines.append(f"*{len(findings)} finding(s)*\n")

        for f in findings:
            icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}.get(f.severity, "⚪")
            line_info = f" (line {f.line})" if f.line else ""
            lines.append(f"- {icon} **{f.title}**{line_info}: {f.suggestion}")

        lines.append("")

    # Analyzer notes
    all_notes = []
    for r in results:
        for note in r.notes:
            all_notes.append(f"- [{r.analyzer_name}] {note}")

    if all_notes:
        lines.append("### Additional Notes\n")
        lines.extend(all_notes)
        lines.append("")

    return "\n".join(lines)


def _next_iteration(results: list[AnalyzerResult], score: RepoScore) -> str:
    """Generate a prioritized next-iteration plan."""
    lines = ["## Next Iteration Plan\n"]

    # Priority 1: Critical/high findings
    critical_high = []
    for r in results:
        for f in r.findings:
            if f.severity in ("critical", "high"):
                critical_high.append(f)

    if critical_high:
        lines.append("### Priority 1: Fix Critical Issues")
        for f in critical_high:
            lines.append(f"- [ ] **{f.title}** in `{f.file}` — {f.suggestion}")
        lines.append("")

    # Priority 2: Structure improvements
    structure_items = [f for r in results for f in r.findings
                       if f.category == "structure"]
    if structure_items:
        lines.append("### Priority 2: Improve Structure")
        for f in structure_items:
            lines.append(f"- [ ] {f.suggestion}")
        lines.append("")

    # Priority 3: Automation
    lines.append("### Priority 3: Add Automation")
    auto_items = [f for r in results for f in r.findings
                  if f.category == "automation"]
    if auto_items:
        for f in auto_items:
            lines.append(f"- [ ] {f.suggestion}")
    else:
        lines.append("- [ ] Add CI/CD pipeline")
        lines.append("- [ ] Add pre-commit hooks")
    lines.append("")

    # What can be automated
    lines.append("### Automatable Improvements")
    lines.append("- Linting and formatting (ruff/black) — fully automatable")
    lines.append("- Import sorting (isort/ruff) — fully automatable")
    lines.append("- Type checking (mypy/pyright) — can be added incrementally")
    lines.append("- Test generation — partially automatable with AI agents")
    lines.append("- Dependency updates — automatable with dependabot/renovate")

    return "\n".join(lines)


def _footer() -> str:
    return """---

*Generated by Code Improvement Agent v1.0.0*
*This report is version 1 of a system designed to evolve into a self-improving code ecosystem.*"""
