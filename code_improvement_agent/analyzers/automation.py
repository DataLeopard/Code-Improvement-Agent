"""Automation analyzer — identify where agents/hooks/CI could plug in."""

import re
from .base import BaseAnalyzer, AnalyzerResult


class AutomationAnalyzer(BaseAnalyzer):

    name = "Automation"
    category = "automation"

    def analyze(self) -> AnalyzerResult:
        result = AnalyzerResult(analyzer_name=self.name)

        self._check_ci_cd(result)
        self._check_testing(result)
        self._check_linting(result)
        self._check_hook_points(result)
        self._calculate_score(result)

        return result

    def _check_ci_cd(self, result: AnalyzerResult):
        """Check for CI/CD configuration."""
        ci_files = [".github/workflows", ".gitlab-ci.yml", "Jenkinsfile",
                    ".circleci", "azure-pipelines.yml", "Makefile"]

        has_ci = any(any(ci in f for ci in ci_files)
                     for f in self.file_contents.keys())

        if not has_ci:
            result.findings.append(self._make_finding(
                file="(repo root)",
                severity="medium",
                title="No CI/CD pipeline detected",
                description="No GitHub Actions, GitLab CI, or other CI config found.",
                suggestion="Add .github/workflows/ci.yml for automated testing and linting on push.",
            ))

    def _check_testing(self, result: AnalyzerResult):
        """Assess test coverage and infrastructure."""
        test_files = [f for f in self.file_contents.keys()
                      if "test" in f.lower() and f.endswith(".py")]
        code_files = [f for f in self.file_contents.keys()
                      if f.endswith(".py") and "test" not in f.lower()
                      and "__pycache__" not in f]

        if not test_files and code_files:
            result.findings.append(self._make_finding(
                file="(repo root)",
                severity="high",
                title="No tests found",
                description=f"{len(code_files)} code files but no test files.",
                suggestion="Add tests for core logic. Start with the most critical/complex functions.",
            ))
        elif test_files and code_files:
            ratio = len(test_files) / len(code_files)
            if ratio < 0.3:
                result.findings.append(self._make_finding(
                    file="(repo root)",
                    severity="medium",
                    title=f"Low test coverage: {len(test_files)} tests for {len(code_files)} modules",
                    description="Test-to-code ratio is below 30%.",
                    suggestion="Prioritize testing core business logic and edge cases.",
                ))

    def _check_linting(self, result: AnalyzerResult):
        """Check for linter/formatter configuration."""
        lint_indicators = ["pyproject.toml", "setup.cfg", ".flake8", ".pylintrc",
                           ".pre-commit-config.yaml", "ruff.toml", ".prettierrc",
                           "eslint", "tox.ini"]

        has_linting = False
        for filepath, content in self.file_contents.items():
            for indicator in lint_indicators:
                if indicator in filepath:
                    has_linting = True
                    break
            if has_linting:
                break

        if not has_linting:
            result.findings.append(self._make_finding(
                file="(repo root)",
                severity="low",
                title="No linter/formatter configuration",
                description="No ruff, flake8, black, or pre-commit config found.",
                suggestion="Add ruff (or flake8 + black) config for consistent code style.",
            ))

    def _check_hook_points(self, result: AnalyzerResult):
        """Identify places where automation hooks could be added."""
        opportunities = []

        # Check for main entry points that could expose CLI interfaces
        for filepath, content in self.file_contents.items():
            if '__name__ == "__main__"' in content or "__name__ == '__main__'" in content:
                if "argparse" not in content and "click" not in content and "typer" not in content:
                    opportunities.append(f"{filepath}: add CLI argument parsing (argparse/click/typer)")

            # Check for functions that could be wrapped as API endpoints
            func_count = len(re.findall(r'^def \w+', content, re.MULTILINE))
            if func_count > 5 and "flask" not in content.lower() and "fastapi" not in content.lower():
                opportunities.append(f"{filepath}: {func_count} functions — consider exposing key ones via API")

        if opportunities:
            result.notes.extend(opportunities)
            result.findings.append(self._make_finding(
                file="(repo root)",
                severity="low",
                title="Automation hook opportunities identified",
                description=f"{len(opportunities)} places where agents/APIs could plug in.",
                suggestion="See notes for specific hook point suggestions.",
            ))

    def _calculate_score(self, result: AnalyzerResult):
        deductions = {"critical": 3.0, "high": 2.0, "medium": 1.0, "low": 0.3}
        for f in result.findings:
            result.score -= deductions.get(f.severity, 0.3)
        result.score = max(1.0, min(10.0, result.score))
