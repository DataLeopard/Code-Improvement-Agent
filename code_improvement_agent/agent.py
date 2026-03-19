"""Core orchestrator — traverses repo, runs analyzers, produces report."""

import os
import logging
from pathlib import Path

from .analyzers import ALL_ANALYZERS
from .analyzers.base import AnalyzerResult
from .config import load_config
from .scoring import compute_repo_score, classify_tag, recommend_action
from .report import generate_report
from .trends import save_run, format_trend_section

logger = logging.getLogger(__name__)

# File extensions to analyze
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".rb",
    ".c", ".cpp", ".h", ".hpp", ".cs", ".swift", ".kt",
    ".html", ".css", ".scss", ".json", ".yaml", ".yml", ".toml",
    ".sh", ".bash", ".bat", ".cmd", ".ps1",
    ".md", ".txt", ".cfg", ".ini", ".env",
}

# Directories to skip
SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", "env",
    ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "dist", "build", ".egg-info", ".eggs",
    ".idea", ".vscode", ".vs",
}

# Max file size to read (500KB)
MAX_FILE_SIZE = 500_000


def collect_files(repo_path: str) -> dict[str, str]:
    """Recursively collect all analyzable files and their contents."""
    file_contents = {}
    repo = Path(repo_path).resolve()

    for root, dirs, files in os.walk(repo):
        # Skip ignored directories (modify dirs in-place to prevent descent)
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for filename in files:
            filepath = Path(root) / filename
            ext = filepath.suffix.lower()

            # Also include dotfiles like .gitignore
            if ext not in CODE_EXTENSIONS and not filename.startswith("."):
                continue

            try:
                size = filepath.stat().st_size
                if size > MAX_FILE_SIZE:
                    continue

                relative = str(filepath.relative_to(repo)).replace("\\", "/")
                content = filepath.read_text(encoding="utf-8", errors="replace")
                file_contents[relative] = content
            except (OSError, UnicodeDecodeError):
                continue

    return file_contents


def infer_app_description(file_contents: dict[str, str]) -> str:
    """Try to figure out what the app does from README, docstrings, etc."""
    # Check README first
    for key in ("README.md", "readme.md", "README.rst", "README.txt"):
        if key in file_contents:
            readme = file_contents[key]
            # Take first non-empty paragraph
            for para in readme.split("\n\n"):
                text = para.strip().lstrip("# ").strip()
                if text and not text.startswith(("![", "<!--", "```", "---")):
                    return text[:300]

    # Fall back to main module docstrings
    for key in sorted(file_contents.keys()):
        content = file_contents[key]
        if content.startswith('"""'):
            end = content.find('"""', 3)
            if end > 0:
                return content[3:end].strip()[:300]

    return "(Could not determine — no README or module docstrings found)"


def _run_smart_analysis(results, file_contents):
    """Validate findings with Claude and add deep AI review."""
    logger.info("Running smart analysis (Claude API)...")
    from .smart_analyzer import validate_findings, deep_review

    all_findings = []
    for r in results:
        all_findings.extend(r.findings)

    validated = validate_findings(all_findings, file_contents)

    dismissed = len(all_findings) - len(validated)
    for r in results:
        cat = r.findings[0].category if r.findings else r.analyzer_name.lower()
        r.findings = [f for f in validated if f.category == cat]

    ai_result = deep_review(file_contents)
    if ai_result.findings:
        results.append(ai_result)

    logger.info(f"Smart analysis: {dismissed} false positives removed, "
                 f"{len(ai_result.findings)} AI findings added")


def _run_auto_fix(results, file_contents, repo_path, apply_fixes):
    """Generate and optionally apply auto-fix patches."""
    logger.info("Generating auto-fix patches...")
    from .auto_fix import generate_fixes, apply_patches, format_patches_report

    all_findings = []
    for r in results:
        all_findings.extend(r.findings)

    patches = generate_fixes(all_findings, file_contents, repo_path)

    if apply_fixes and patches:
        patches = apply_patches(patches, repo_path, dry_run=False)
    elif patches:
        patches = apply_patches(patches, repo_path, dry_run=True)

    return format_patches_report(patches)


def _build_metadata(repo_path, file_contents, results, score,
                    smart, auto_fix, apply_fixes):
    """Build the metadata dict for programmatic use."""
    return {
        "repo_path": repo_path,
        "files_analyzed": len(file_contents),
        "total_findings": sum(len(r.findings) for r in results),
        "scores": {
            "quality": score.quality,
            "structure": score.structure,
            "security": score.security,
            "usefulness": score.usefulness,
            "overall": score.overall,
        },
        "tag": score.tag,
        "recommendation": score.recommendation,
        "analyzer_scores": {r.analyzer_name: r.score for r in results},
        "mode": "smart" if smart else "static",
        "auto_fix": auto_fix,
        "fixes_applied": apply_fixes,
    }


def _insert_trend_section(report, repo_path, metadata):
    """Save run to trend history and insert the trend section into the report."""
    save_run(repo_path, metadata["scores"], metadata)
    trend_section = format_trend_section(repo_path, metadata["scores"])
    return report.replace(
        "\n---\n\n*Generated by",
        f"\n\n{trend_section}\n\n---\n\n*Generated by"
    )


def run_analysis(repo_path: str, smart: bool = False, auto_fix: bool = False,
                 apply_fixes: bool = False, config_path: str | None = None,
                 gen_tests: bool = False, write_tests: bool = False) -> tuple[str, dict]:
    """Main entry point: analyze a repo and return (report_text, metadata).

    Args:
        repo_path: Path to the repository
        smart: Use Claude API to validate findings and eliminate false positives
        auto_fix: Generate code patches for confirmed findings
        apply_fixes: Actually apply the patches to files (requires auto_fix=True)
        config_path: Optional path to a .code-improve.yaml config file
        gen_tests: Generate pytest tests for public functions
        write_tests: Write generated tests to disk (requires gen_tests=True)
    """
    repo_path = str(Path(repo_path).resolve())

    # Step 1: Load configuration
    config = load_config(repo_path, config_path=config_path)

    # Step 2: Collect files
    file_contents = collect_files(repo_path)
    if not file_contents:
        return "ERROR: No analyzable files found in the repository.", {}

    # Step 3: Infer what the app does
    description = infer_app_description(file_contents)

    # Step 4: Run all static analyzers
    results: list[AnalyzerResult] = []
    for analyzer_cls in ALL_ANALYZERS:
        analyzer = analyzer_cls(repo_path, file_contents, config=config)
        result = analyzer.analyze()
        results.append(result)

    # Step 5: Smart mode — validate findings with Claude + deep review
    patches_report = ""
    if smart:
        _run_smart_analysis(results, file_contents)

    # Step 6: Auto-fix mode — generate patches
    if auto_fix:
        patches_report = _run_auto_fix(results, file_contents, repo_path, apply_fixes)

    # Step 7: Compute scores
    score = compute_repo_score(results, config=config)
    score.tag = classify_tag(file_contents, repo_path)
    score.recommendation = recommend_action(score, len(file_contents))

    # Step 8: Generate report
    file_list = sorted(file_contents.keys())
    report = generate_report(repo_path, description, results, score, file_list)

    # Append patches report if generated
    if patches_report:
        report = report.replace(
            "\n---\n\n*Generated by",
            f"\n\n{patches_report}\n\n---\n\n*Generated by"
        )

    # Update version tag for smart mode
    if smart:
        report = report.replace("Agent Version:** 1.0.0", "Agent Version:** 2.0.0 (Smart)")

    # Step 9: Generate tests
    if gen_tests:
        from .test_generator import generate_tests, format_test_report
        logger.info("Generating tests...")
        test_result = generate_tests(file_contents, repo_path, write=write_tests)
        test_report = format_test_report(test_result)
        report = report.replace(
            "\n---\n\n*Generated by",
            f"\n\n{test_report}\n\n---\n\n*Generated by"
        )

    # Build metadata and save trends
    metadata = _build_metadata(repo_path, file_contents, results, score,
                               smart, auto_fix, apply_fixes)
    report = _insert_trend_section(report, repo_path, metadata)

    return report, metadata
