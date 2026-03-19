"""Auto-fix module — generates and optionally applies code patches using Claude."""

import os
import json
import logging
from pathlib import Path
from .analyzers.base import Finding
from .llm import call_claude

logger = logging.getLogger(__name__)


def generate_fixes(findings: list[Finding], file_contents: dict[str, str],
                   repo_path: str) -> list[dict]:
    """Generate concrete code fixes for confirmed findings.

    Returns a list of patches:
    [
        {
            "file": "path/to/file.py",
            "finding": "Title of finding",
            "original": "original code block",
            "fixed": "fixed code block",
            "explanation": "what was changed and why",
        }
    ]
    """
    # Only fix confirmed, non-trivial findings
    fixable = [f for f in findings
               if f.severity in ("critical", "high", "medium")
               and f.file in file_contents
               and "," not in f.file]  # skip multi-file findings

    if not fixable:
        logger.info("No fixable findings to generate patches for")
        return []

    patches = []

    # Group by file to batch API calls
    by_file: dict[str, list[Finding]] = {}
    for f in fixable:
        if f.file not in by_file:
            by_file[f.file] = []
        by_file[f.file].append(f)

    for filepath, file_findings in by_file.items():
        content = file_contents.get(filepath, "")
        if not content:
            continue

        findings_desc = "\n".join(
            f"  {i+1}. [{f.severity.upper()}] {f.title} (line {f.line}): {f.description}\n"
            f"     Suggestion: {f.suggestion}"
            for i, f in enumerate(file_findings)
        )

        prompt = f"""Fix the issues in this file. Generate minimal, targeted patches.

FILE: {filepath}
```
{content}
```

ISSUES TO FIX:
{findings_desc}

For each fix, respond with a JSON array. Each element:
{{
  "finding_index": 1,
  "original": "exact original code to replace (copy verbatim from the file, include enough context to be unique)",
  "fixed": "the replacement code",
  "explanation": "brief explanation of the change"
}}

RULES:
- Keep changes minimal — fix the issue, nothing else
- The "original" string MUST appear exactly in the file (it will be used for find-and-replace)
- Do NOT add comments explaining the fix in the code
- Do NOT reformat or restructure surrounding code
- Do NOT add type hints, docstrings, or imports unless the fix requires them
- If a finding cannot be safely fixed without more context, skip it

Respond with ONLY the JSON array."""

        try:
            response = call_claude(prompt, max_tokens=4000)

            json_str = response.strip()
            if json_str.startswith("```"):
                json_str = json_str.split("\n", 1)[1].rsplit("```", 1)[0]
            fix_data = json.loads(json_str)

            for fix in fix_data:
                original = fix.get("original", "")
                fixed = fix.get("fixed", "")

                # Validate the original text actually exists in the file
                if original and original in content:
                    idx = fix.get("finding_index", 1) - 1
                    title = file_findings[idx].title if 0 <= idx < len(file_findings) else "Fix"

                    patches.append({
                        "file": filepath,
                        "finding": title,
                        "original": original,
                        "fixed": fixed,
                        "explanation": fix.get("explanation", ""),
                    })
                else:
                    logger.debug(f"Skipping patch for {filepath}: original text not found in file")

        except json.JSONDecodeError as e:
            logger.warning(f"Could not parse fix response for {filepath}: {e}")
        except Exception as e:
            logger.warning(f"Fix generation failed for {filepath}: {e}")

    logger.info(f"Generated {len(patches)} patches across {len(by_file)} files")
    return patches


def apply_patches(patches: list[dict], repo_path: str, dry_run: bool = True) -> list[dict]:
    """Apply patches to files. Returns list of applied patches.

    If dry_run=True (default), only reports what would change without modifying files.
    """
    applied = []
    repo = Path(repo_path).resolve()

    for patch in patches:
        filepath = repo / patch["file"]
        if not filepath.exists():
            logger.warning(f"File not found: {filepath}")
            continue

        content = filepath.read_text(encoding="utf-8", errors="replace")

        if patch["original"] not in content:
            logger.warning(f"Original text not found in {patch['file']} — skipping")
            continue

        # Check for uniqueness (original should appear exactly once)
        count = content.count(patch["original"])
        if count > 1:
            logger.warning(f"Original text appears {count} times in {patch['file']} — skipping for safety")
            continue

        new_content = content.replace(patch["original"], patch["fixed"], 1)

        if dry_run:
            patch["status"] = "would_apply"
            logger.info(f"[DRY RUN] Would fix '{patch['finding']}' in {patch['file']}")
        else:
            filepath.write_text(new_content, encoding="utf-8")
            patch["status"] = "applied"
            logger.info(f"Applied fix: '{patch['finding']}' in {patch['file']}")

        applied.append(patch)

    return applied


def format_patches_report(patches: list[dict]) -> str:
    """Format patches into a readable Markdown section for the report."""
    if not patches:
        return "## Auto-Fix Patches\n\nNo patches generated."

    lines = [
        "## Auto-Fix Patches\n",
        f"**{len(patches)} patches generated**\n",
    ]

    for i, patch in enumerate(patches, 1):
        status = patch.get("status", "generated")
        status_icon = {"applied": "done", "would_apply": "ready", "generated": "pending"}.get(status, "?")

        lines.append(f"### Patch {i}: {patch['finding']}")
        lines.append(f"**File:** `{patch['file']}` | **Status:** {status_icon}\n")
        lines.append(f"{patch.get('explanation', '')}\n")
        lines.append("```diff")
        for line in patch["original"].split("\n"):
            lines.append(f"- {line}")
        for line in patch["fixed"].split("\n"):
            lines.append(f"+ {line}")
        lines.append("```\n")

    return "\n".join(lines)
