"""Reusability analyzer — detect repeated code, suggest shared utilities."""

import re
from collections import Counter
from .base import BaseAnalyzer, AnalyzerResult


class ReusabilityAnalyzer(BaseAnalyzer):

    name = "Reusability"
    category = "reusability"

    def analyze(self) -> AnalyzerResult:
        result = AnalyzerResult(analyzer_name=self.name)

        self._check_duplicate_blocks(result)
        self._check_repeated_imports(result)
        self._check_inline_logic(result)
        self._calculate_score(result)

        return result

    def _check_duplicate_blocks(self, result: AnalyzerResult):
        """Find code blocks (3+ lines) that appear in multiple files."""
        # Build a map of 3-line sliding windows across all files
        block_locations: dict[str, list[tuple[str, int]]] = {}

        for filepath, content in self.file_contents.items():
            lines = [l.strip() for l in content.split("\n") if l.strip() and not l.strip().startswith("#")]
            for i in range(len(lines) - 2):
                block = "\n".join(lines[i:i+3])
                if len(block) < 30:  # skip trivial blocks
                    continue
                if block not in block_locations:
                    block_locations[block] = []
                block_locations[block].append((filepath, i + 1))

        # Find blocks that appear in multiple files
        for block, locations in block_locations.items():
            unique_files = set(loc[0] for loc in locations)
            if len(unique_files) >= 2:
                files_str = ", ".join(sorted(unique_files))
                result.findings.append(self._make_finding(
                    file=files_str,
                    severity="medium",
                    title="Duplicated code block",
                    description=f"A 3-line block appears in {len(unique_files)} files.",
                    suggestion="Extract into a shared utility function.",
                    code_before=block,
                ))

    def _check_repeated_imports(self, result: AnalyzerResult):
        """Find the same import pattern across many files — candidate for a shared base."""
        import_sets: dict[str, list[str]] = {}

        for filepath, content in self.file_contents.items():
            imports = []
            for line in content.split("\n"):
                stripped = line.strip()
                if stripped.startswith("import ") or stripped.startswith("from "):
                    imports.append(stripped)
            if imports:
                key = "\n".join(sorted(imports))
                if key not in import_sets:
                    import_sets[key] = []
                import_sets[key].append(filepath)

        # Check for common import patterns (same set in 3+ files)
        for import_block, files in import_sets.items():
            if len(files) >= 3:
                result.findings.append(self._make_finding(
                    file=", ".join(files),
                    severity="low",
                    title="Repeated import pattern",
                    description=f"Same imports appear in {len(files)} files.",
                    suggestion="Consider a shared module that re-exports common dependencies.",
                ))

    def _check_inline_logic(self, result: AnalyzerResult):
        """Detect long inline expressions that should be extracted."""
        for filepath, content in self.file_contents.items():
            for i, line in enumerate(content.split("\n"), 1):
                # Very long lines with nested function calls
                if len(line.strip()) > 120 and line.count("(") >= 3:
                    result.findings.append(self._make_finding(
                        file=filepath,
                        severity="low",
                        title="Complex inline expression",
                        description=f"Line {i}: {len(line.strip())} chars with nested calls.",
                        suggestion="Extract intermediate steps into named variables for readability.",
                        line=i,
                    ))

    def _calculate_score(self, result: AnalyzerResult):
        deductions = {"critical": 3.0, "high": 2.0, "medium": 1.0, "low": 0.5}
        for f in result.findings:
            result.score -= deductions.get(f.severity, 0.5)
        result.score = max(1.0, result.score)
