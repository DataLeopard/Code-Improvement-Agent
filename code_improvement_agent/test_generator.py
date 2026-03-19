"""Test generator — creates pytest tests for Python functions using Claude."""

import ast
import json
import logging
from pathlib import Path

from .llm import call_claude

logger = logging.getLogger(__name__)


def _collect_functions(filepath: str, content: str) -> list[dict]:
    """Extract public function/method signatures and bodies from a Python file."""
    try:
        tree = ast.parse(content, filename=filepath)
    except SyntaxError:
        return []

    lines = content.split("\n")
    functions = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_"):
            continue

        end = getattr(node, "end_lineno", None)
        if end is None:
            continue

        source = "\n".join(lines[node.lineno - 1:end])

        # Get the class name if this is a method
        class_name = None
        for parent in ast.walk(tree):
            if isinstance(parent, ast.ClassDef):
                for child in ast.iter_child_nodes(parent):
                    if child is node:
                        class_name = parent.name
                        break

        functions.append({
            "name": node.name,
            "class": class_name,
            "line": node.lineno,
            "source": source,
            "is_async": isinstance(node, ast.AsyncFunctionDef),
        })

    return functions


def generate_tests(file_contents: dict[str, str], repo_path: str,
                   write: bool = False) -> dict:
    """Generate pytest tests for all public functions in Python files.

    Args:
        file_contents: {relative_path: content} of files to analyze
        repo_path: Root path of the repository
        write: If True, write test files to disk

    Returns:
        dict with "tests_generated", "files_created", and "test_code" entries
    """
    all_functions = {}
    for filepath, content in file_contents.items():
        if not filepath.endswith(".py"):
            continue
        funcs = _collect_functions(filepath, content)
        if funcs:
            all_functions[filepath] = funcs

    if not all_functions:
        logger.info("No public Python functions found to test")
        return {"tests_generated": 0, "files_created": [], "test_code": {}}

    test_code = {}
    files_created = []
    total_tests = 0

    for filepath, funcs in all_functions.items():
        func_summaries = "\n\n".join(
            f"### {f['class'] + '.' if f['class'] else ''}{f['name']}() "
            f"(line {f['line']})\n```python\n{f['source']}\n```"
            for f in funcs
        )

        module_path = filepath.replace("/", ".").replace("\\", ".").removesuffix(".py")

        prompt = f"""Write pytest tests for these Python functions from `{filepath}`.

{func_summaries}

Requirements:
- Import from `{module_path}` (adjust as needed for the project structure)
- Write clear, focused tests — one test function per behavior
- Test normal cases, edge cases, and error cases where applicable
- Use pytest fixtures where helpful
- Use descriptive test names: test_<function>_<scenario>
- For functions that need complex setup (file I/O, network, etc.), mock dependencies
- Do NOT test private methods
- Do NOT over-test trivial getters/setters
- Keep tests practical — skip functions that are too tightly coupled to test in isolation

Respond with ONLY valid Python code for a complete test file. No explanations outside the code.
Start with the necessary imports."""

        try:
            response = call_claude(prompt, max_tokens=4000,
                                   system="You are an expert Python test engineer. "
                                          "Write clean, thorough pytest tests.")

            code = response.strip()
            if code.startswith("```"):
                code = code.split("\n", 1)[1].rsplit("```", 1)[0]

            # Determine test file path
            test_filename = _test_path_for(filepath)
            test_code[test_filename] = code

            # Count test functions
            num_tests = code.count("\ndef test_") + code.count("\nasync def test_")
            total_tests += num_tests

            logger.info(f"Generated {num_tests} tests for {filepath} -> {test_filename}")

            if write:
                test_file = Path(repo_path) / test_filename
                test_file.parent.mkdir(parents=True, exist_ok=True)
                test_file.write_text(code, encoding="utf-8")
                files_created.append(test_filename)
                logger.info(f"Wrote {test_filename}")

        except Exception as e:
            logger.warning(f"Test generation failed for {filepath}: {e}")

    return {
        "tests_generated": total_tests,
        "files_created": files_created,
        "test_code": test_code,
    }


def _test_path_for(filepath: str) -> str:
    """Convert a source file path to a test file path.

    e.g. 'src/utils.py' -> 'tests/test_utils.py'
         'analyzers/clarity.py' -> 'tests/test_clarity.py'
    """
    p = Path(filepath)
    return f"tests/test_{p.stem}.py"


def format_test_report(result: dict) -> str:
    """Format test generation results into a Markdown section."""
    if not result["test_code"]:
        return "## Generated Tests\n\nNo tests generated."

    lines = [
        "## Generated Tests\n",
        f"**{result['tests_generated']} tests** generated "
        f"across **{len(result['test_code'])} files**\n",
    ]

    if result["files_created"]:
        lines.append("### Files Written")
        for f in result["files_created"]:
            lines.append(f"- `{f}`")
        lines.append("")

    for test_file, code in result["test_code"].items():
        lines.append(f"### `{test_file}`")
        lines.append(f"```python\n{code}\n```\n")

    return "\n".join(lines)
