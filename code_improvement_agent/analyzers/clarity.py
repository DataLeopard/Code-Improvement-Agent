"""Clarity analyzer — naming, comments, complexity."""

import re
from .base import BaseAnalyzer, AnalyzerResult


class ClarityAnalyzer(BaseAnalyzer):

    name = "Clarity"
    category = "clarity"

    def analyze(self) -> AnalyzerResult:
        result = AnalyzerResult(analyzer_name=self.name)

        for filepath, content in self.file_contents.items():
            self._check_naming(filepath, content, result)
            self._check_function_length(filepath, content, result)
            self._check_missing_docstrings(filepath, content, result)
            self._check_magic_numbers(filepath, content, result)
            self._check_deep_nesting(filepath, content, result)

        self._calculate_score(result)
        return result

    def _check_naming(self, filepath: str, content: str, result: AnalyzerResult):
        """Check for poor variable/function names."""
        # Single-letter variables (except loop vars i, j, k, x, y)
        pattern = r'\b([a-z])\s*='
        allowed = set("ijkxynmfe_")

        for i, line in enumerate(content.split("\n"), 1):
            if line.strip().startswith("#") or line.strip().startswith("def "):
                continue
            matches = re.findall(pattern, line)
            bad_names = [m for m in matches if m not in allowed]
            if bad_names:
                result.findings.append(self._make_finding(
                    file=filepath,
                    severity="low",
                    title=f"Single-letter variable: '{', '.join(bad_names)}'",
                    description=f"Line {i}: unclear variable name(s).",
                    suggestion="Use descriptive names that explain the variable's purpose.",
                    line=i,
                ))

    def _check_function_length(self, filepath: str, content: str, result: AnalyzerResult):
        """Flag functions longer than 50 lines."""
        lines = content.split("\n")
        func_start = None
        func_name = None
        indent_level = 0

        for i, line in enumerate(lines):
            match = re.match(r'^(\s*)def (\w+)', line)
            if match:
                # Check if previous function was too long
                if func_start is not None:
                    length = i - func_start
                    if length > 50:
                        result.findings.append(self._make_finding(
                            file=filepath,
                            severity="medium",
                            title=f"Long function: {func_name}() ({length} lines)",
                            description=f"Functions over 50 lines are harder to understand and test.",
                            suggestion="Break into smaller, focused helper functions.",
                            line=func_start + 1,
                        ))
                func_start = i
                func_name = match.group(2)
                indent_level = len(match.group(1))

        # Check last function
        if func_start is not None:
            length = len(lines) - func_start
            if length > 50:
                result.findings.append(self._make_finding(
                    file=filepath,
                    severity="medium",
                    title=f"Long function: {func_name}() ({length} lines)",
                    description=f"Functions over 50 lines are harder to understand and test.",
                    suggestion="Break into smaller, focused helper functions.",
                    line=func_start + 1,
                ))

    def _check_missing_docstrings(self, filepath: str, content: str, result: AnalyzerResult):
        """Check for functions/classes missing docstrings."""
        lines = content.split("\n")
        missing = []

        for i, line in enumerate(lines):
            match = re.match(r'\s*(def|class) (\w+)', line)
            if match:
                kind, name = match.groups()
                if name.startswith("_") and kind == "def":
                    continue  # skip private methods
                # Check next non-empty line for docstring
                for j in range(i + 1, min(i + 3, len(lines))):
                    next_line = lines[j].strip()
                    if next_line:
                        if not (next_line.startswith('"""') or next_line.startswith("'''")):
                            missing.append((name, i + 1))
                        break

        if len(missing) > 3:
            names = ", ".join(m[0] for m in missing[:5])
            result.findings.append(self._make_finding(
                file=filepath,
                severity="low",
                title=f"{len(missing)} functions/classes missing docstrings",
                description=f"Including: {names}",
                suggestion="Add brief docstrings to public functions describing what they do and return.",
            ))

    def _check_magic_numbers(self, filepath: str, content: str, result: AnalyzerResult):
        """Detect magic numbers in code (not in config files)."""
        if "config" in filepath.lower():
            return

        magic_count = 0
        for i, line in enumerate(content.split("\n"), 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("def ") or stripped.startswith("class "):
                continue
            # Numbers that aren't 0, 1, 2, or common defaults
            numbers = re.findall(r'(?<!["\w])(\d+\.?\d*)(?!["\w])', stripped)
            for n in numbers:
                val = float(n)
                if val not in (0, 1, 2, 100, 255) and not stripped.startswith(("import", "from", "#")):
                    magic_count += 1

        if magic_count > 10:
            result.findings.append(self._make_finding(
                file=filepath,
                severity="low",
                title=f"{magic_count} magic numbers detected",
                description="Hardcoded numeric values without explanation.",
                suggestion="Extract to named constants in config or at module top.",
            ))

    def _check_deep_nesting(self, filepath: str, content: str, result: AnalyzerResult):
        """Flag deeply nested code (4+ levels)."""
        max_depth = 0
        deepest_line = 0

        for i, line in enumerate(content.split("\n"), 1):
            if not line.strip():
                continue
            # Count indentation (assuming 4-space or 1-tab)
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            depth = indent // 4  # assume 4-space indent
            if depth > max_depth:
                max_depth = depth
                deepest_line = i

        if max_depth >= 5:
            result.findings.append(self._make_finding(
                file=filepath,
                severity="medium",
                title=f"Deep nesting ({max_depth} levels)",
                description=f"Deepest nesting at line {deepest_line}.",
                suggestion="Use early returns, guard clauses, or extract nested logic into functions.",
                line=deepest_line,
            ))

    def _calculate_score(self, result: AnalyzerResult):
        deductions = {"critical": 3.0, "high": 2.0, "medium": 1.0, "low": 0.3}
        for f in result.findings:
            result.score -= deductions.get(f.severity, 0.3)
        result.score = max(1.0, min(10.0, result.score))
