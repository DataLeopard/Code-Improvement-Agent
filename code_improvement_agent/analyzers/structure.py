"""Structure analyzer — folder organization, separation of concerns, modularity."""

import os
from collections import Counter
from .base import BaseAnalyzer, AnalyzerResult


class StructureAnalyzer(BaseAnalyzer):

    name = "Structure"
    category = "structure"

    def analyze(self) -> AnalyzerResult:
        result = AnalyzerResult(analyzer_name=self.name)
        files = list(self.file_contents.keys())

        self._check_flat_structure(files, result)
        self._check_mixed_concerns(files, result)
        self._check_missing_packaging(files, result)
        self._check_config_separation(files, result)
        self._calculate_score(result)

        return result

    def _check_flat_structure(self, files: list[str], result: AnalyzerResult):
        """Flag repos where too many files sit at the root with no subdirectories."""
        root_files = [f for f in files if os.sep not in f and "/" not in f]
        code_files = [f for f in root_files if f.endswith((".py", ".js", ".ts", ".go", ".rs", ".java"))]

        if len(code_files) > 5:
            result.findings.append(self._make_finding(
                file="(repo root)",
                severity="high",
                title="Flat project structure",
                description=f"{len(code_files)} code files at root level with no subdirectory organization.",
                suggestion="Group related files into packages/directories: e.g., src/, core/, utils/, tests/.",
            ))

    def _check_mixed_concerns(self, files: list[str], result: AnalyzerResult):
        """Detect when logic, UI, config, and tests are all mixed together."""
        categories = {"config": [], "test": [], "ui": [], "logic": [], "script": []}

        for f in files:
            name = os.path.basename(f).lower()
            content = self.file_contents.get(f, "")

            if "config" in name or name in ("settings.py", ".env", "constants.py"):
                categories["config"].append(f)
            elif name.startswith("test_") or name.endswith("_test.py"):
                categories["test"].append(f)
            elif "tkinter" in content or "tk." in content or "gui" in name or "overlay" in name:
                categories["ui"].append(f)
            elif name.endswith((".bat", ".sh", ".cmd")):
                categories["script"].append(f)
            else:
                categories["logic"].append(f)

        # Check if different concerns share the same directory
        root_mix = set()
        for cat, cat_files in categories.items():
            for f in cat_files:
                dirname = os.path.dirname(f) or "(root)"
                if dirname == "(root)":
                    root_mix.add(cat)

        if len(root_mix) >= 3:
            result.findings.append(self._make_finding(
                file="(repo root)",
                severity="medium",
                title="Mixed concerns at root level",
                description=f"Found {', '.join(root_mix)} files all at root level.",
                suggestion="Separate into directories: src/ (logic), ui/ (GUI), tests/, scripts/, etc.",
            ))

    def _check_missing_packaging(self, files: list[str], result: AnalyzerResult):
        """Check for missing setup.py/pyproject.toml in Python projects."""
        py_files = [f for f in files if f.endswith(".py")]
        if not py_files:
            return

        has_setup = any(os.path.basename(f) in ("setup.py", "pyproject.toml", "setup.cfg")
                        for f in files)
        if not has_setup and len(py_files) > 2:
            result.findings.append(self._make_finding(
                file="(repo root)",
                severity="low",
                title="No Python packaging config",
                description="No setup.py or pyproject.toml found.",
                suggestion="Add pyproject.toml for installable packaging, dependency management, and tool config.",
            ))

    def _check_config_separation(self, files: list[str], result: AnalyzerResult):
        """Check if config values are hardcoded in logic files."""
        for filepath, content in self.file_contents.items():
            if "config" in filepath.lower():
                continue

            lines = content.split("\n")
            hardcoded_count = 0
            for line in lines:
                stripped = line.strip()
                # Look for patterns like SOME_CONSTANT = 123 or magic numbers in logic
                if ("= 0." in stripped or "= \"" in stripped) and stripped.isupper():
                    hardcoded_count += 1

            if hardcoded_count > 3:
                result.findings.append(self._make_finding(
                    file=filepath,
                    severity="medium",
                    title="Hardcoded constants in logic file",
                    description=f"Found {hardcoded_count} potential hardcoded constants.",
                    suggestion="Move constants to a config file or environment variables.",
                ))

    def _calculate_score(self, result: AnalyzerResult):
        deductions = {"critical": 3.0, "high": 2.0, "medium": 1.0, "low": 0.5}
        for f in result.findings:
            result.score -= deductions.get(f.severity, 0.5)
        result.score = max(1.0, result.score)
