"""Security analyzer — exposed secrets, unsafe patterns, .env usage."""

import re
from .base import BaseAnalyzer, AnalyzerResult


class SecurityAnalyzer(BaseAnalyzer):

    name = "Security"
    category = "security"

    # Patterns that likely indicate hardcoded secrets
    SECRET_PATTERNS = [
        (r'(?i)(api[_-]?key|secret[_-]?key|password|token|auth)\s*=\s*["\'][^"\']{8,}["\']',
         "Hardcoded secret/credential"),
        (r'(?i)(aws_access_key_id|aws_secret_access_key)\s*=\s*["\'][^"\']+["\']',
         "AWS credential"),
        (r'sk-[a-zA-Z0-9]{20,}',
         "OpenAI-style API key"),
        (r'ghp_[a-zA-Z0-9]{36}',
         "GitHub personal access token"),
        (r'(?i)mongodb(\+srv)?://\w+:\w+@',
         "Database connection string with credentials"),
        (r'(?i)(mysql|postgres|postgresql)://\w+:\w+@',
         "Database connection string with credentials"),
    ]

    # Dangerous function calls
    UNSAFE_PATTERNS = [
        (r'\beval\s*\(', "eval() usage — code injection risk"),
        (r'\bexec\s*\(', "exec() usage — code injection risk"),
        (r'subprocess\..*shell\s*=\s*True', "Shell=True in subprocess — command injection risk"),
        (r'os\.system\s*\(', "os.system() — prefer subprocess with shell=False"),
        (r'pickle\.loads?\s*\(', "pickle.load — deserialization attack risk"),
        (r'yaml\.load\s*\([^)]*\)(?!.*Loader)', "yaml.load without safe Loader"),
    ]

    def analyze(self) -> AnalyzerResult:
        result = AnalyzerResult(analyzer_name=self.name)

        for filepath, content in self.file_contents.items():
            self._check_secrets(filepath, content, result)
            self._check_unsafe_calls(filepath, content, result)

        self._check_env_file(result)
        self._check_gitignore(result)
        self._calculate_score(result)

        return result

    def _check_secrets(self, filepath: str, content: str, result: AnalyzerResult):
        """Scan for hardcoded secrets and credentials."""
        if filepath.endswith((".pyc", ".pyo", ".so", ".dll")):
            return

        for pattern, description in self.SECRET_PATTERNS:
            for match in re.finditer(pattern, content):
                line_num = content[:match.start()].count("\n") + 1
                result.findings.append(self._make_finding(
                    file=filepath,
                    severity="critical",
                    title=description,
                    description=f"Line {line_num}: potential secret detected.",
                    suggestion="Move to environment variable (.env) and load with os.environ or python-dotenv.",
                    line=line_num,
                ))

    def _check_unsafe_calls(self, filepath: str, content: str, result: AnalyzerResult):
        """Detect dangerous function calls."""
        for pattern, description in self.UNSAFE_PATTERNS:
            for match in re.finditer(pattern, content):
                line_num = content[:match.start()].count("\n") + 1
                result.findings.append(self._make_finding(
                    file=filepath,
                    severity="high",
                    title=description,
                    description=f"Line {line_num}",
                    suggestion="Use safer alternatives or validate/sanitize all inputs.",
                    line=line_num,
                ))

    def _check_env_file(self, result: AnalyzerResult):
        """Check if .env file is being tracked (it shouldn't be)."""
        if ".env" in self.file_contents:
            result.findings.append(self._make_finding(
                file=".env",
                severity="critical",
                title=".env file is tracked in repository",
                description="Environment file with potential secrets is part of the repo.",
                suggestion="Add .env to .gitignore and remove from tracking with git rm --cached .env",
            ))

    def _check_gitignore(self, result: AnalyzerResult):
        """Check if .gitignore exists and covers common sensitive files."""
        gitignore = self.file_contents.get(".gitignore", "")
        if not gitignore:
            result.findings.append(self._make_finding(
                file=".gitignore",
                severity="high",
                title="No .gitignore file",
                description="Repository has no .gitignore — sensitive files could be committed.",
                suggestion="Add a .gitignore covering .env, __pycache__, *.pyc, venv/, etc.",
            ))
            return

        recommended = [".env", "__pycache__", "*.pyc", "venv/", "node_modules/"]
        missing = [r for r in recommended if r not in gitignore]
        if missing:
            result.notes.append(f".gitignore could also cover: {', '.join(missing)}")

    def _calculate_score(self, result: AnalyzerResult):
        deductions = {"critical": 4.0, "high": 2.5, "medium": 1.0, "low": 0.5}
        for f in result.findings:
            result.score -= deductions.get(f.severity, 0.5)
        result.score = max(1.0, min(10.0, result.score))
