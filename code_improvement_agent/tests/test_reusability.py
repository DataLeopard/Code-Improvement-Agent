import pytest
from unittest.mock import Mock, patch
from code_improvement_agent.analyzers.reusability import ReusabilityAnalyzer
from code_improvement_agent.analyzers.base import AnalyzerResult
from code_improvement_agent.config import Config


@pytest.fixture
def mock_analyzer():
    """Create a ReusabilityAnalyzer instance with mocked dependencies."""
    analyzer = ReusabilityAnalyzer("/fake", {}, config=Config())
    analyzer.name = "reusability"
    return analyzer


@pytest.fixture
def mock_result():
    """Create a mock AnalyzerResult instance."""
    return AnalyzerResult(analyzer_name="reusability")


def test_analyze_returns_analyzer_result(mock_analyzer):
    """Test that analyze returns an AnalyzerResult instance."""
    with patch.object(mock_analyzer, '_check_duplicate_blocks'), \
         patch.object(mock_analyzer, '_check_repeated_imports'), \
         patch.object(mock_analyzer, '_check_inline_logic'), \
         patch.object(mock_analyzer, '_calculate_score'):
        
        result = mock_analyzer.analyze()
        
        assert isinstance(result, AnalyzerResult)
        assert result.analyzer_name == "reusability"


def test_analyze_calls_all_check_methods_in_correct_order(mock_analyzer):
    """Test that analyze calls all check methods in the expected order."""
    with patch.object(mock_analyzer, '_check_duplicate_blocks') as mock_dup, \
         patch.object(mock_analyzer, '_check_repeated_imports') as mock_imp, \
         patch.object(mock_analyzer, '_check_inline_logic') as mock_inline, \
         patch.object(mock_analyzer, '_calculate_score') as mock_calc:
        
        mock_analyzer.analyze()
        
        mock_dup.assert_called_once()
        mock_imp.assert_called_once()
        mock_inline.assert_called_once()
        mock_calc.assert_called_once()


def test_analyze_passes_result_to_all_methods(mock_analyzer):
    """Test that analyze passes the same result instance to all methods."""
    with patch.object(mock_analyzer, '_check_duplicate_blocks') as mock_dup, \
         patch.object(mock_analyzer, '_check_repeated_imports') as mock_imp, \
         patch.object(mock_analyzer, '_check_inline_logic') as mock_inline, \
         patch.object(mock_analyzer, '_calculate_score') as mock_calc:
        
        result = mock_analyzer.analyze()
        
        # Verify all methods were called with the same result instance
        mock_dup.assert_called_once_with(result)
        mock_imp.assert_called_once_with(result)
        mock_inline.assert_called_once_with(result)
        mock_calc.assert_called_once_with(result)


def test_analyze_continues_execution_if_check_method_raises_exception(mock_analyzer):
    """Test that analyze continues execution even if one check method fails."""
    with patch.object(mock_analyzer, '_check_duplicate_blocks', side_effect=Exception("Test error")), \
         patch.object(mock_analyzer, '_check_repeated_imports') as mock_imp, \
         patch.object(mock_analyzer, '_check_inline_logic') as mock_inline, \
         patch.object(mock_analyzer, '_calculate_score') as mock_calc:
        
        # Should not raise exception despite _check_duplicate_blocks failing
        result = mock_analyzer.analyze()
        
        # Verify subsequent methods are still called
        mock_imp.assert_called_once()
        mock_inline.assert_called_once()
        mock_calc.assert_called_once()
        assert isinstance(result, AnalyzerResult)


def test_analyze_preserves_result_modifications(mock_analyzer):
    """Test that analyze preserves modifications made to result by check methods."""
    def modify_result(result):
        result.score = 85
        result.issues = ["test issue"]
    
    with patch.object(mock_analyzer, '_check_duplicate_blocks'), \
         patch.object(mock_analyzer, '_check_repeated_imports'), \
         patch.object(mock_analyzer, '_check_inline_logic'), \
         patch.object(mock_analyzer, '_calculate_score', side_effect=modify_result):
        
        result = mock_analyzer.analyze()
        
        assert result.score == 85
        assert result.issues == ["test issue"]


def test_analyze_creates_result_with_correct_analyzer_name(mock_analyzer):
    """Test that analyze creates result with the correct analyzer name."""
    mock_analyzer.name = "custom_reusability_analyzer"
    
    with patch.object(mock_analyzer, '_check_duplicate_blocks'), \
         patch.object(mock_analyzer, '_check_repeated_imports'), \
         patch.object(mock_analyzer, '_check_inline_logic'), \
         patch.object(mock_analyzer, '_calculate_score'):
        
        result = mock_analyzer.analyze()
        
        assert result.analyzer_name == "custom_reusability_analyzer"
