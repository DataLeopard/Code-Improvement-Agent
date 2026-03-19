import pytest
from unittest.mock import Mock, patch
from code_improvement_agent.analyzers.functionality import FunctionalityAnalyzer
from code_improvement_agent.analyzers.base import AnalyzerResult
from code_improvement_agent.config import Config


@pytest.fixture
def analyzer():
    file_contents = {
        'test_file.py': '''
def test_function():
    # TODO: implement this
    pass

def working_function():
    return "hello"

try:
    risky_code()
except:
    pass

import unused_module
import os

def empty_func():
    pass
'''
    }
    return FunctionalityAnalyzer("/fake", file_contents, config=Config())


@pytest.fixture
def empty_analyzer():
    return FunctionalityAnalyzer("/fake", {}, config=Config())


def test_analyze_returns_analyzer_result(analyzer):
    result = analyzer.analyze()
    
    assert isinstance(result, AnalyzerResult)
    assert result.analyzer_name == analyzer.name


def test_analyze_with_empty_files(empty_analyzer):
    result = empty_analyzer.analyze()
    
    assert isinstance(result, AnalyzerResult)
    assert result.analyzer_name == empty_analyzer.name


@patch.object(FunctionalityAnalyzer, '_check_todos_fixmes')
@patch.object(FunctionalityAnalyzer, '_check_empty_functions')
@patch.object(FunctionalityAnalyzer, '_check_bare_excepts')
@patch.object(FunctionalityAnalyzer, '_check_unused_imports')
@patch.object(FunctionalityAnalyzer, '_check_dead_code')
@patch.object(FunctionalityAnalyzer, '_calculate_score')
def test_analyze_calls_all_check_methods(
    mock_calc_score, mock_dead_code, mock_unused_imports, 
    mock_bare_excepts, mock_empty_functions, mock_todos_fixmes, analyzer
):
    result = analyzer.analyze()
    
    # Each check method should be called once per file
    assert mock_todos_fixmes.call_count == 1
    assert mock_empty_functions.call_count == 1
    assert mock_bare_excepts.call_count == 1
    assert mock_unused_imports.call_count == 1
    assert mock_dead_code.call_count == 1
    
    # Calculate score should be called once
    mock_calc_score.assert_called_once()


def test_analyze_with_multiple_files():
    file_contents = {
        'file1.py': 'def func1(): pass',
        'file2.py': 'def func2(): pass',
        'file3.py': 'def func3(): pass'
    }
    analyzer = FunctionalityAnalyzer("/fake", file_contents, config=Config())

    with patch.object(FunctionalityAnalyzer, '_check_todos_fixmes') as mock_check:
        result = analyzer.analyze()
        
        # Should be called once for each file
        assert mock_check.call_count == 3


@patch.object(FunctionalityAnalyzer, '_check_todos_fixmes', side_effect=Exception("Test error"))
def test_analyze_handles_check_method_exception(mock_check, analyzer):
    # Should not raise exception even if check methods fail
    result = analyzer.analyze()
    
    assert isinstance(result, AnalyzerResult)


def test_analyze_preserves_result_between_checks(analyzer):
    with patch.object(FunctionalityAnalyzer, '_check_todos_fixmes') as mock_todos, \
         patch.object(FunctionalityAnalyzer, '_check_empty_functions') as mock_empty:
        
        def check_same_result(*args):
            # Verify the same result object is passed to all methods
            assert args[2] is not None  # result parameter
            
        mock_todos.side_effect = check_same_result
        mock_empty.side_effect = check_same_result
        
        result = analyzer.analyze()
        
        # Verify methods were called with the same result object
        todos_result = mock_todos.call_args[0][2]
        empty_result = mock_empty.call_args[0][2]
        assert todos_result is empty_result
