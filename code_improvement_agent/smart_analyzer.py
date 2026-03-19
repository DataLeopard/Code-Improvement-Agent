"""Smart analyzer — uses Claude to validate findings, eliminate false positives,
and provide deeper insights that static analysis can't catch."""

import json
import logging
from .analyzers.base import Finding, AnalyzerResult
from .llm import call_claude

logger = logging.getLogger(__name__)


def validate_findings(findings: list[Finding], file_contents: dict[str, str]) -> list[Finding]:
    """Send findings to Claude for validation. Returns filtered + enriched findings.

    Groups findings by file, sends context, and asks Claude to:
    1. Confirm or dismiss each finding
    2. Explain why it matters (or doesn't)
    3. Provide a concrete fix suggestion
    """
    if not findings:
        return []

    # Group findings by file
    by_file: dict[str, list[Finding]] = {}
    for f in findings:
        key = f.file.split(",")[0].strip()  # handle multi-file findings
        if key not in by_file:
            by_file[key] = []
        by_file[key].append(f)

    validated = []
    dismissed_count = 0

    for filepath, file_findings in by_file.items():
        content = file_contents.get(filepath, "")
        if not content:
            # Keep findings for files we can't read (repo-level findings)
            validated.extend(file_findings)
            continue

        # Build context: file content (truncated) + findings list
        truncated = content[:8000] if len(content) > 8000 else content
        findings_desc = "\n".join(
            f"  {i+1}. [{f.severity.upper()}] {f.title} (line {f.line}): {f.description}"
            for i, f in enumerate(file_findings)
        )

        prompt = f"""Analyze this code file and validate each finding below.

FILE: {filepath}
```
{truncated}
```

FINDINGS TO VALIDATE:
{findings_desc}

For each finding, respond with a JSON array. Each element should have:
- "index": the finding number (1-based)
- "valid": true if the finding is a real issue, false if it's a false positive
- "reason": brief explanation of why it is or isn't a real issue
- "improved_suggestion": a better fix suggestion (if valid), or null

Common false positives to watch for:
- JavaScript RegExp.exec() is NOT a security risk (it's not eval/exec)
- JSX return statements are NOT unreachable code
- package-lock.json "duplicates" with package.json are normal
- CSS pixel values are NOT "magic numbers"
- Single-letter vars in arrow functions/callbacks are fine in JS/TS

Respond with ONLY the JSON array, no other text."""

        try:
            response = call_claude(prompt, max_tokens=2000)
            # Parse JSON from response (handle markdown code blocks)
            json_str = response.strip()
            if json_str.startswith("```"):
                json_str = json_str.split("\n", 1)[1].rsplit("```", 1)[0]
            results = json.loads(json_str)

            for r in results:
                idx = r["index"] - 1
                if 0 <= idx < len(file_findings):
                    finding = file_findings[idx]
                    if r.get("valid", True):
                        # Update suggestion if LLM provided a better one
                        if r.get("improved_suggestion"):
                            finding.suggestion = r["improved_suggestion"]
                        finding.description += f" [AI: {r.get('reason', '')}]"
                        validated.append(finding)
                    else:
                        dismissed_count += 1
                        logger.debug(f"Dismissed: {finding.title} in {filepath} — {r.get('reason', '')}")

        except json.JSONDecodeError as e:
            logger.warning(f"Could not parse LLM response for {filepath}: {e}")
            validated.extend(file_findings)  # keep originals on parse failure
        except Exception as e:
            logger.warning(f"LLM validation failed for {filepath}: {e}")
            validated.extend(file_findings)

    logger.info(f"Smart validation: {len(validated)} confirmed, {dismissed_count} dismissed")
    return validated


def deep_review(file_contents: dict[str, str]) -> AnalyzerResult:
    """Run a deep AI-powered review on the entire codebase.

    This catches things static analysis can't:
    - Architectural issues
    - Business logic bugs
    - Missing error handling patterns
    - API design problems
    - Performance anti-patterns
    """
    result = AnalyzerResult(analyzer_name="AI Deep Review")

    # Build a codebase summary (fit within context window)
    file_summaries = []
    total_chars = 0
    for filepath, content in sorted(file_contents.items()):
        if filepath.endswith((".json", ".lock", ".css", ".md", ".txt", ".log")):
            continue
        # Send full file up to 6000 chars, then truncate with note
        if len(content) > 6000:
            snippet = content[:6000] + f"\n# ... [{len(content) - 6000} more chars, file continues] ..."
        else:
            snippet = content
        total_chars += len(snippet)
        if total_chars > 80000:  # stay within reasonable token limits
            file_summaries.append(f"\n--- {filepath} (skipped, {len(content)} chars) ---")
            break
        file_summaries.append(f"\n--- {filepath} ---\n{snippet}")

    if not file_summaries:
        return result

    codebase = "\n".join(file_summaries)

    prompt = f"""You are reviewing a codebase. Analyze it for issues that static analysis tools miss.

{codebase}

Identify up to 10 high-impact findings. Focus on:
1. Architectural problems (tight coupling, missing abstractions)
2. Business logic issues (race conditions, edge cases, incomplete flows)
3. Missing error handling that matters
4. Performance anti-patterns
5. API/interface design issues
6. Things that will cause bugs in production

Respond with a JSON array. Each element:
{{
  "file": "filename",
  "severity": "critical|high|medium|low",
  "title": "short title",
  "description": "what's wrong and why it matters",
  "suggestion": "concrete fix with code if possible",
  "line": null or line number
}}

Only report REAL issues. No style nits. No suggestions to add comments.
Do NOT report "incomplete" or "truncated" code — files may be snippets for context, the full code exists.
Respond with ONLY the JSON array."""

    try:
        response = call_claude(
            prompt,
            system="You are a senior software architect doing a production readiness review. Be direct and practical.",
            max_tokens=4000,
        )

        json_str = response.strip()
        if json_str.startswith("```"):
            json_str = json_str.split("\n", 1)[1].rsplit("```", 1)[0]
        findings_data = json.loads(json_str)

        for f in findings_data:
            result.findings.append(Finding(
                file=f.get("file", "(unknown)"),
                category="ai_review",
                severity=f.get("severity", "medium"),
                title=f.get("title", "AI Finding"),
                description=f.get("description", ""),
                suggestion=f.get("suggestion", ""),
                line=f.get("line"),
            ))

    except json.JSONDecodeError as e:
        logger.warning(f"Could not parse deep review response: {e}")
    except Exception as e:
        logger.warning(f"Deep review failed: {e}")

    # Score based on findings
    deductions = {"critical": 3.0, "high": 2.0, "medium": 1.0, "low": 0.3}
    for f in result.findings:
        result.score -= deductions.get(f.severity, 0.5)
    result.score = max(1.0, min(10.0, result.score))

    return result
