"""AST-based Python analyzer — accurate analysis using the ast module."""

import ast
from .base import BaseAnalyzer, AnalyzerResult


class ASTAnalyzer(BaseAnalyzer):

    name = "AST Analysis"
    category = "ast_analysis"

    def analyze(self) -> AnalyzerResult:
        result = AnalyzerResult(analyzer_name=self.name)

        for filepath, content in self.file_contents.items():
            if not filepath.endswith(".py"):
                continue
            try:
                tree = ast.parse(content, filename=filepath)
            except SyntaxError:
                result.notes.append(f"Skipped {filepath}: syntax error")
                continue

            self._check_unused_imports(filepath, content, tree, result)
            self._check_cyclomatic_complexity(filepath, tree, result)
            self._check_function_length(filepath, content, tree, result)
            self._check_missing_return_type(filepath, tree, result)
            self._check_mutable_defaults(filepath, tree, result)

        self._calculate_score(result)
        return result

    # ------------------------------------------------------------------
    # 1. Unused imports
    # ------------------------------------------------------------------
    def _check_unused_imports(self, filepath: str, content: str,
                              tree: ast.Module, result: AnalyzerResult):
        """Find imported names that are never referenced in the rest of the AST."""
        # Collect all imported names: {local_name: line_number}
        imported: dict[str, int] = {}
        type_checking_ranges: list[tuple[int, int]] = []

        # Find TYPE_CHECKING blocks to skip
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                test = node.test
                is_tc = False
                if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
                    is_tc = True
                elif isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING":
                    is_tc = True
                if is_tc:
                    end = max(
                        getattr(n, "lineno", node.lineno)
                        for n in ast.walk(node)
                    )
                    type_checking_ranges.append((node.lineno, end))

        def _in_type_checking(lineno: int) -> bool:
            return any(lo <= lineno <= hi for lo, hi in type_checking_ranges)

        # Collect names from __all__ so we can exclude them
        all_names: set[str] = set()
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        if isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                            for elt in node.value.elts:
                                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                    all_names.add(elt.value)

        # Gather imports (skip those inside TYPE_CHECKING blocks)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if _in_type_checking(node.lineno):
                    continue
                for alias in node.names:
                    local = alias.asname if alias.asname else alias.name
                    imported[local] = node.lineno
            elif isinstance(node, ast.ImportFrom):
                if _in_type_checking(node.lineno):
                    continue
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    local = alias.asname if alias.asname else alias.name
                    imported[local] = node.lineno

        if not imported:
            return

        # Walk tree to find all Name references (excluding import nodes themselves)
        used_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if isinstance(node, ast.Name):
                used_names.add(node.id)
            elif isinstance(node, ast.Attribute):
                # For chained attrs like foo.bar, the root is a Name node
                # which ast.walk will visit separately
                pass

        unused = [
            (name, line)
            for name, line in imported.items()
            if name not in used_names and name not in all_names
        ]

        for name, line in unused:
            result.findings.append(self._make_finding(
                file=filepath,
                severity="low",
                title=f"Unused import: {name}",
                description=f"Line {line}: '{name}' is imported but never used.",
                suggestion=f"Remove the unused import of '{name}'.",
                line=line,
            ))

    # ------------------------------------------------------------------
    # 2. Cyclomatic complexity
    # ------------------------------------------------------------------
    def _check_cyclomatic_complexity(self, filepath: str, tree: ast.Module,
                                     result: AnalyzerResult):
        """Count decision points per function; flag complexity > 10."""
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            complexity = 1  # base path
            for child in ast.walk(node):
                if isinstance(child, (ast.If, ast.IfExp)):
                    complexity += 1
                elif isinstance(child, (ast.For, ast.AsyncFor, ast.While)):
                    complexity += 1
                elif isinstance(child, ast.ExceptHandler):
                    complexity += 1
                elif isinstance(child, (ast.With, ast.AsyncWith)):
                    complexity += 1
                elif isinstance(child, ast.BoolOp):
                    # Each and/or adds a branch
                    complexity += len(child.values) - 1
                elif isinstance(child, ast.Assert):
                    complexity += 1

            if complexity > 10:
                severity = "high" if complexity > 20 else "medium"
                result.findings.append(self._make_finding(
                    file=filepath,
                    severity=severity,
                    title=f"High cyclomatic complexity: {node.name}() = {complexity}",
                    description=(
                        f"Line {node.lineno}: function '{node.name}' has a "
                        f"cyclomatic complexity of {complexity} (threshold: 10)."
                    ),
                    suggestion="Break this function into smaller, focused helper functions.",
                    line=node.lineno,
                ))

    # ------------------------------------------------------------------
    # 3. Function length (AST-based exact boundaries)
    # ------------------------------------------------------------------
    def _check_function_length(self, filepath: str, content: str,
                               tree: ast.Module, result: AnalyzerResult,
                               max_lines: int = 50):
        """Flag functions whose body spans more than max_lines."""
        total_lines = content.count("\n") + 1

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            start = node.lineno
            # end_lineno is available in Python 3.8+
            end = getattr(node, "end_lineno", None)
            if end is None:
                continue  # can't determine without end_lineno

            length = end - start + 1
            if length > max_lines:
                severity = "high" if length > 100 else "medium"
                result.findings.append(self._make_finding(
                    file=filepath,
                    severity=severity,
                    title=f"Long function: {node.name}() is {length} lines",
                    description=(
                        f"Lines {start}-{end}: function '{node.name}' spans "
                        f"{length} lines (threshold: {max_lines})."
                    ),
                    suggestion="Extract logical sections into smaller helper functions.",
                    line=start,
                ))

    # ------------------------------------------------------------------
    # 4. Missing return type hints on public functions
    # ------------------------------------------------------------------
    def _check_missing_return_type(self, filepath: str, tree: ast.Module,
                                   result: AnalyzerResult):
        """Flag public functions/methods without a return type annotation."""
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            # Skip private/protected functions
            if node.name.startswith("_"):
                continue

            if node.returns is None:
                result.findings.append(self._make_finding(
                    file=filepath,
                    severity="low",
                    title=f"Missing return type hint: {node.name}()",
                    description=(
                        f"Line {node.lineno}: public function '{node.name}' "
                        f"has no return type annotation."
                    ),
                    suggestion=f"Add a return type: def {node.name}(...) -> ReturnType:",
                    line=node.lineno,
                ))

    # ------------------------------------------------------------------
    # 5. Mutable default arguments
    # ------------------------------------------------------------------
    def _check_mutable_defaults(self, filepath: str, tree: ast.Module,
                                result: AnalyzerResult):
        """Flag mutable default arguments (list, dict, set literals)."""
        mutable_types = (ast.List, ast.Dict, ast.Set)

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            for default in node.args.defaults + node.args.kw_defaults:
                if default is None:
                    continue
                if isinstance(default, mutable_types):
                    # Determine the type name for the message
                    type_name = type(default).__name__.lower()
                    result.findings.append(self._make_finding(
                        file=filepath,
                        severity="high",
                        title=f"Mutable default argument in {node.name}()",
                        description=(
                            f"Line {node.lineno}: function '{node.name}' uses a "
                            f"mutable {type_name} as a default argument. This default "
                            f"is shared across all calls and mutations persist."
                        ),
                        suggestion=(
                            f"Use None as the default and create the {type_name} "
                            f"inside the function body: "
                            f"def {node.name}(..., arg=None): arg = arg or {type_name}()"
                        ),
                        line=node.lineno,
                    ))

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------
    def _calculate_score(self, result: AnalyzerResult):
        deductions = {"critical": 3.0, "high": 2.0, "medium": 1.0, "low": 0.3}
        for f in result.findings:
            result.score -= deductions.get(f.severity, 0.3)
        result.score = max(1.0, min(10.0, result.score))
