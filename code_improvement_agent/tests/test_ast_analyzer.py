import ast
import pytest
from unittest.mock import Mock, patch

from code_improvement_agent.analyzers.ast_analyzer import ASTAnalyzer
from code_improvement_agent.analyzers.base import AnalyzerResult
from code_improvement_agent.config import Config


@pytest.fixture
def valid_python_code():
    return """
def add(a, b):
    return a + b

def subtract(x, y):
    result = x - y
    return result
"""


@pytest.fixture
def invalid_python_code():
    return """
def broken_function(
    # missing closing parenthesis and colon
"""


@pytest.fixture
def mixed_file_contents():
    return {
        "test.py": """
def hello():
    return "world"
""",
        "config.json": """
{
    "name": "test"
}
""",
        "main.py": """
import os
import sys

def main():
    pass
"""
    }


@pytest.fixture
def ast_analyzer(mixed_file_contents):
    return ASTAnalyzer("/fake", file_contents=mixed_file_contents, config=Config())


def test_analyze_returns_analyzer_result(ast_analyzer):
    result = ast_analyzer.analyze()
    
    assert isinstance(result, AnalyzerResult)
    assert result.analyzer_name == ast_analyzer.name


def test_analyze_processes_only_python_files(ast_analyzer):
    with patch.object(ast_analyzer, '_check_unused_imports') as mock_check:
        ast_analyzer.analyze()
        
        # Should only be called for .py files (test.py and main.py)
        assert mock_check.call_count == 2
        called_files = [call[0][0] for call in mock_check.call_args_list]
        assert "test.py" in called_files
        assert "main.py" in called_files
        assert "config.json" not in called_files


def test_analyze_skips_files_with_syntax_errors():
    file_contents = {
        "valid.py": "def hello(): return 'world'",
        "invalid.py": "def broken_function(\n    # missing parts"
    }
    analyzer = ASTAnalyzer("/fake", file_contents=file_contents, config=Config())

    result = analyzer.analyze()

    assert any("Skipped invalid.py: syntax error" in note for note in result.notes)


def test_analyze_continues_after_syntax_error():
    file_contents = {
        "invalid.py": "def broken_function(\n    # syntax error",
        "valid.py": "def hello(): return 'world'"
    }
    analyzer = ASTAnalyzer("/fake", file_contents=file_contents, config=Config())
    
    with patch.object(analyzer, '_check_unused_imports') as mock_check:
        result = analyzer.analyze()
        
        # Should still process the valid file
        mock_check.assert_called_once()
        assert "valid.py" in mock_check.call_args[0][0]
        assert any("Skipped invalid.py: syntax error" in note for note in result.notes)


def test_analyze_calls_all_check_methods(ast_analyzer):
    with patch.object(ast_analyzer, '_check_unused_imports') as mock_unused, \
         patch.object(ast_analyzer, '_check_cyclomatic_complexity') as mock_complexity, \
         patch.object(ast_analyzer, '_check_function_length') as mock_length, \
         patch.object(ast_analyzer, '_check_missing_return_type') as mock_return_type, \
         patch.object(ast_analyzer, '_check_mutable_defaults') as mock_mutable:
        
        ast_analyzer.analyze()
        
        # Each check method should be called for each .py file
        assert mock_unused.call_count == 2
        assert mock_complexity.call_count == 2
        assert mock_length.call_count == 2
        assert mock_return_type.call_count == 2
        assert mock_mutable.call_count == 2


def test_analyze_calls_calculate_score(ast_analyzer):
    with patch.object(ast_analyzer, '_calculate_score') as mock_calculate:
        result = ast_analyzer.analyze()
        
        mock_calculate.assert_called_once_with(result)


def test_analyze_with_empty_file_contents():
    analyzer = ASTAnalyzer("/fake", file_contents={}, config=Config())

    result = analyzer.analyze()
    
    assert isinstance(result, AnalyzerResult)
    assert result.analyzer_name == analyzer.name


def test_analyze_passes_correct_arguments_to_check_methods(ast_analyzer):
    with patch.object(ast_analyzer, '_check_unused_imports') as mock_check:
        result = ast_analyzer.analyze()
        
        # Verify the method is called with correct argument types
        call_args = mock_check.call_args_list[0][0]  # First call's positional args
        filepath, content, tree, result_obj = call_args
        
        assert isinstance(filepath, str)
        assert filepath.endswith('.py')
        assert isinstance(content, str)
        assert isinstance(tree, ast.AST)
        assert isinstance(result_obj, AnalyzerResult)


def test_analyze_handles_ast_parse_with_filename():
    file_contents = {"test.py": "def hello(): pass"}
    analyzer = ASTAnalyzer("/fake", file_contents=file_contents, config=Config())
    
    with patch('ast.parse') as mock_parse:
        mock_parse.return_value = ast.Module(body=[], type_ignores=[])
        
        analyzer.analyze()
        
        mock_parse.assert_called_once_with("def hello(): pass", filename="test.py")
