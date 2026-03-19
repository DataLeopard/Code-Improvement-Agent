"""Functionality analyzer — detect incomplete features, broken flows, TODOs."""

import re
from .base import BaseAnalyzer, AnalyzerResult


class FunctionalityAnalyzer(BaseAnalyzer):

    name = "Functionality"
    category = "functionality"

    def analyze(self) -> AnalyzerResult:
        result = AnalyzerResult(analyzer_name=self.name)

        for filepath, content in self.file_contents.items():
            self._check_todos_fixmes(filepath, content, result)
            self._check_empty_functions(filepath, content, result)
            self._check_bare_excepts(filepath, content, result)
            self._check_unused_imports(filepath, content, result)
            self._check_dead_code(filepath, content, result)

        self._calculate_score(result)
        return result

    def _check_todos_fixmes(self, filepath: str, content: str, result: AnalyzerResult):
        """Find TODO, FIXME, HACK, XXX comments — indicators of incomplete work."""
        markers = []
        for i, line in enumerate(content.split("\n"), 1):
            for marker in ("TODO", "FIXME", "HACK", "XXX", "BUG"):
                if marker in line.upper() and "#" in line:
                    markers.append((marker, i, line.strip()))

        if markers:
            for marker, line_num, text in markers:
                result.findings.append(self._make_finding(
                    file=filepath,
                    severity="medium" if marker in ("FIXME", "BUG") else "low",
                    title=f"{marker} at line {line_num}",
                    description=text,
                    suggestion="Address the TODO or create a tracked issue for it.",
                    line=line_num,
                ))

    def _check_empty_functions(self, filepath: str, content: str, result: AnalyzerResult):
        """Find functions with only pass or ... as body."""
        lines = content.split("\n")
        for i, line in enumerate(lines):
            match = re.match(r'\s*def (\w+)', line)
            if match:
                func_name = match.group(1)
                # Look at next non-empty, non-docstring lines
                body_lines = []
                in_docstring = False
                for j in range(i + 1, min(i + 10, len(lines))):
                    stripped = lines[j].strip()
                    if stripped.startswith('"""') or stripped.startswith("'''"):
                        if in_docstring:
                            in_docstring = False
                            continue
                        if stripped.count('"""') == 2 or stripped.count("'''") == 2:
                            continue  # single-line docstring
                        in_docstring = True
                        continue
                    if in_docstring:
                        continue
                    if stripped and not stripped.startswith("#"):
                        body_lines.append(stripped)
                    if len(body_lines) >= 2:
                        break

                if body_lines and body_lines[0] in ("pass", "...", "raise NotImplementedError"):
                    if len(body_lines) == 1 or (len(body_lines) > 1 and
                            not body_lines[1].startswith(("def ", "class "))):
                        continue  # might have more body
                    result.findings.append(self._make_finding(
                        file=filepath,
                        severity="medium",
                        title=f"Stub function: {func_name}()",
                        description=f"Line {i+1}: function body is just '{body_lines[0]}'.",
                        suggestion="Implement the function or remove it if unnecessary.",
                        line=i + 1,
                    ))

    def _check_bare_excepts(self, filepath: str, content: str, result: AnalyzerResult):
        """Find bare except clauses that swallow all errors."""
        for i, line in enumerate(content.split("\n"), 1):
            stripped = line.strip()
            if stripped == "except:" or stripped == "except Exception:":
                # Check if the next line is just pass
                lines = content.split("\n")
                if i < len(lines):
                    next_line = lines[i].strip() if i < len(lines) else ""
                    if next_line == "pass":
                        result.findings.append(self._make_finding(
                            file=filepath,
                            severity="high",
                            title="Silent exception swallowing",
                            description=f"Line {i}: bare except with pass — errors will be invisible.",
                            suggestion="Log the exception or handle specific exception types.",
                            line=i,
                        ))

    def _check_unused_imports(self, filepath: str, content: str, result: AnalyzerResult):
        """Basic check for imports that aren't referenced in the file."""
        lines = content.split("\n")
        imports = []

        for line in lines:
            stripped = line.strip()
            # "import foo" -> check for "foo"
            match = re.match(r'^import (\w+)', stripped)
            if match:
                imports.append(match.group(1))
            # "from foo import bar, baz" -> check for "bar", "baz"
            match = re.match(r'^from \S+ import (.+)', stripped)
            if match:
                names = [n.strip().split(" as ")[-1].strip()
                         for n in match.group(1).split(",")]
                imports.extend(n for n in names if n and n != "*")

        # Check if each imported name appears elsewhere in the file
        rest_of_code = "\n".join(l for l in lines
                                  if not l.strip().startswith(("import ", "from ")))
        unused = [name for name in imports
                  if name not in rest_of_code and name != "__"]

        if unused:
            result.findings.append(self._make_finding(
                file=filepath,
                severity="low",
                title=f"Potentially unused imports: {', '.join(unused[:5])}",
                description=f"{len(unused)} imported names not found in file body.",
                suggestion="Remove unused imports to reduce clutter.",
            ))

    def _check_dead_code(self, filepath: str, content: str, result: AnalyzerResult):
        """Detect obviously unreachable code after return/break/continue."""
        lines = content.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped in ("return", "break", "continue") or stripped.startswith("return "):
                # Check next non-empty line at same or deeper indent
                current_indent = len(line) - len(line.lstrip())
                for j in range(i + 1, min(i + 5, len(lines))):
                    next_line = lines[j]
                    if not next_line.strip():
                        continue
                    next_indent = len(next_line) - len(next_line.lstrip())
                    if next_indent > current_indent:
                        # Deeper indent after return = dead code
                        if not next_line.strip().startswith(("def ", "class ", "except", "elif", "else")):
                            result.findings.append(self._make_finding(
                                file=filepath,
                                severity="medium",
                                title="Unreachable code after return/break",
                                description=f"Line {j+1}: code after '{stripped}' at line {i+1}.",
                                suggestion="Remove dead code or restructure control flow.",
                                line=j + 1,
                            ))
                    break

    def _calculate_score(self, result: AnalyzerResult):
        deductions = {"critical": 3.0, "high": 2.0, "medium": 1.0, "low": 0.3}
        for f in result.findings:
            result.score -= deductions.get(f.severity, 0.3)
        result.score = max(1.0, min(10.0, result.score))
