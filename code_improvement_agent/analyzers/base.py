"""Base analyzer interface — all analyzers inherit from this."""

from dataclasses import dataclass, field


@dataclass
class Finding:
    """A single improvement finding."""
    file: str
    category: str       # structure, reusability, clarity, functionality, security, automation
    severity: str       # critical, high, medium, low
    title: str
    description: str
    suggestion: str
    line: int | None = None
    code_before: str | None = None
    code_after: str | None = None


@dataclass
class AnalyzerResult:
    """Result from a single analyzer."""
    analyzer_name: str
    findings: list[Finding] = field(default_factory=list)
    score: float = 10.0  # 1-10, starts perfect, deductions applied
    notes: list[str] = field(default_factory=list)


class BaseAnalyzer:
    """Base class for all code analyzers."""

    name: str = "base"
    category: str = "general"

    def __init__(self, repo_path: str, file_contents: dict[str, str], config=None):
        self.repo_path = repo_path
        self.file_contents = file_contents  # {relative_path: content}
        if config is None:
            from ..config import load_config
            config = load_config(repo_path)
        self.config = config

    def analyze(self) -> AnalyzerResult:
        raise NotImplementedError

    def _make_finding(self, file: str, severity: str, title: str,
                      description: str, suggestion: str, **kwargs) -> Finding:
        return Finding(
            file=file,
            category=self.category,
            severity=severity,
            title=title,
            description=description,
            suggestion=suggestion,
            **kwargs,
        )
