import pytest
from unittest.mock import Mock, patch
from code_improvement_agent.analyzers.clarity import ClarityAnalyzer
from code_improvement_agent.analyzers.base import AnalyzerResult
from code_improvement_agent.config import Config


@pytest.fixture
def clarity_analyzer():
    file_contents = {
        'test_file.py': '''
def calculate_total(items):
    """Calculate total price of items."""
    total = 0
    for item in items:
        total += item.price
    return total

def x():
    return 42

def very_long_function():
    line1 = 1
    line2 = 2
    line3 = 3
    line4 = 4
    line5 = 5
    line6 = 6
    line7 = 7
    line8 = 8
    line9 = 9
    line10 = 10
    line11 = 11
    line12 = 12
    line13 = 13
    line14 = 14
    line15 = 15
    line16 = 16
    line17 = 17
    line18 = 18
    line19 = 19
    line20 = 20
    line21 = 21
    return line21
        '''
    }
    return ClarityAnalyzer("/fake", file_contents, config=Config())


@pytest.fixture
def empty_analyzer():
    return ClarityAnalyzer("/fake", {}, config=Config())


@pytest.fixture
def multi_file_analyzer():
    file_contents = {
        'file1.py': 'def good_function():\n    """Good docstring."""\n    return True',
        'file2.py': 'def bad_function():\n    return 42',
        'file3.py': 'class TestClass:\n    pass'
    }
    return ClarityAnalyzer("/fake", file_contents, config=Config())


def test_analyze_returns_analyzer_result(clarity_analyzer):
    result = clarity_analyzer.analyze()
    
    assert isinstance(result, AnalyzerResult)
    assert result.analyzer_name == clarity_analyzer.name


def test_analyze_calls_all_check_methods(clarity_analyzer):
    with patch.object(clarity_analyzer, '_check_naming') as mock_naming, \
         patch.object(clarity_analyzer, '_check_function_length') as mock_length, \
         patch.object(clarity_analyzer, '_check_missing_docstrings') as mock_docstrings, \
         patch.object(clarity_analyzer, '_check_magic_numbers') as mock_magic, \
         patch.object(clarity_analyzer, '_check_deep_nesting') as mock_nesting, \
         patch.object(clarity_analyzer, '_calculate_score') as mock_score:
        
        result = clarity_analyzer.analyze()
        
        mock_naming.assert_called_once()
        mock_length.assert_called_once()
        mock_docstrings.assert_called_once()
        mock_magic.assert_called_once()
        mock_nesting.assert_called_once()
        mock_score.assert_called_once_with(result)


def test_analyze_processes_all_files(multi_file_analyzer):
    with patch.object(multi_file_analyzer, '_check_naming') as mock_check:
        multi_file_analyzer.analyze()
        
        assert mock_check.call_count == 3
        called_files = [call[0][0] for call in mock_check.call_args_list]
        assert 'file1.py' in called_files
        assert 'file2.py' in called_files
        assert 'file3.py' in called_files


def test_analyze_passes_correct_parameters_to_checks(clarity_analyzer):
    with patch.object(clarity_analyzer, '_check_naming') as mock_check:
        result = clarity_analyzer.analyze()
        
        mock_check.assert_called_once()
        args = mock_check.call_args[0]
        assert args[0] == 'test_file.py'
        assert 'def calculate_total' in args[1]
        assert isinstance(args[2], AnalyzerResult)


def test_analyze_with_empty_file_contents(empty_analyzer):
    with patch.object(empty_analyzer, '_calculate_score') as mock_score:
        result = empty_analyzer.analyze()
        
        assert isinstance(result, AnalyzerResult)
        mock_score.assert_called_once_with(result)


def test_analyze_score_calculation_called_last(clarity_analyzer):
    call_order = []
    
    def track_calls(method_name):
        def wrapper(*args, **kwargs):
            call_order.append(method_name)
        return wrapper
    
    with patch.object(clarity_analyzer, '_check_naming', side_effect=track_calls('naming')), \
         patch.object(clarity_analyzer, '_check_function_length', side_effect=track_calls('length')), \
         patch.object(clarity_analyzer, '_check_missing_docstrings', side_effect=track_calls('docstrings')), \
         patch.object(clarity_analyzer, '_check_magic_numbers', side_effect=track_calls('magic')), \
         patch.object(clarity_analyzer, '_check_deep_nesting', side_effect=track_calls('nesting')), \
         patch.object(clarity_analyzer, '_calculate_score', side_effect=track_calls('score')):
        
        clarity_analyzer.analyze()
        
        assert call_order[-1] == 'score'
        assert len([call for call in call_order if call != 'score']) == 5


def test_analyze_maintains_result_consistency(clarity_analyzer):
    result1 = clarity_analyzer.analyze()
    result2 = clarity_analyzer.analyze()
    
    assert result1.analyzer_name == result2.analyzer_name
    assert type(result1) == type(result2)


def test_analyze_handles_single_file(clarity_analyzer):
    single_file_analyzer = ClarityAnalyzer("/fake", {'single.py': 'def test(): pass'}, config=Config())
    
    with patch.object(single_file_analyzer, '_check_naming') as mock_check:
        result = single_file_analyzer.analyze()
        
        assert isinstance(result, AnalyzerResult)
        mock_check.assert_called_once()
        assert mock_check.call_args[0][0] == 'single.py'
