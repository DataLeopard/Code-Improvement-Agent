import pytest
from unittest.mock import Mock, patch
from code_improvement_agent.analyzers.automation import AutomationAnalyzer
from code_improvement_agent.analyzers.base import AnalyzerResult
from code_improvement_agent.config import Config


@pytest.fixture
def automation_analyzer():
    """Create an AutomationAnalyzer instance for testing."""
    return AutomationAnalyzer("/fake", {}, config=Config())


@pytest.fixture
def mock_analyzer_result():
    """Create a mock AnalyzerResult for testing."""
    return Mock(spec=AnalyzerResult)


def test_analyze_returns_analyzer_result(automation_analyzer):
    """Test that analyze returns an AnalyzerResult instance."""
    with patch.object(automation_analyzer, '_check_ci_cd'), \
         patch.object(automation_analyzer, '_check_testing'), \
         patch.object(automation_analyzer, '_check_linting'), \
         patch.object(automation_analyzer, '_check_hook_points'), \
         patch.object(automation_analyzer, '_calculate_score'):
        
        result = automation_analyzer.analyze()
        
        assert isinstance(result, AnalyzerResult)
        assert result.analyzer_name == automation_analyzer.name


def test_analyze_calls_all_check_methods_in_order(automation_analyzer):
    """Test that analyze calls all private check methods in the correct order."""
    with patch.object(automation_analyzer, '_check_ci_cd') as mock_ci_cd, \
         patch.object(automation_analyzer, '_check_testing') as mock_testing, \
         patch.object(automation_analyzer, '_check_linting') as mock_linting, \
         patch.object(automation_analyzer, '_check_hook_points') as mock_hooks, \
         patch.object(automation_analyzer, '_calculate_score') as mock_score:
        
        result = automation_analyzer.analyze()
        
        # Verify all methods were called once
        mock_ci_cd.assert_called_once_with(result)
        mock_testing.assert_called_once_with(result)
        mock_linting.assert_called_once_with(result)
        mock_hooks.assert_called_once_with(result)
        mock_score.assert_called_once_with(result)
        
        # Verify call order by checking call counts at each step
        assert mock_ci_cd.call_count == 1
        assert mock_testing.call_count == 1
        assert mock_linting.call_count == 1
        assert mock_hooks.call_count == 1
        assert mock_score.call_count == 1


def test_analyze_passes_same_result_to_all_methods(automation_analyzer):
    """Test that analyze passes the same AnalyzerResult instance to all check methods."""
    captured_results = []
    
    def capture_result(result):
        captured_results.append(result)
    
    with patch.object(automation_analyzer, '_check_ci_cd', side_effect=capture_result), \
         patch.object(automation_analyzer, '_check_testing', side_effect=capture_result), \
         patch.object(automation_analyzer, '_check_linting', side_effect=capture_result), \
         patch.object(automation_analyzer, '_check_hook_points', side_effect=capture_result), \
         patch.object(automation_analyzer, '_calculate_score', side_effect=capture_result):
        
        returned_result = automation_analyzer.analyze()
        
        # All methods should receive the same result instance
        assert len(captured_results) == 5
        assert all(result is captured_results[0] for result in captured_results)
        assert returned_result is captured_results[0]


def test_analyze_handles_exception_in_check_methods(automation_analyzer):
    """Test that analyze handles exceptions raised by check methods."""
    with patch.object(automation_analyzer, '_check_ci_cd', side_effect=Exception("CI/CD check failed")), \
         patch.object(automation_analyzer, '_check_testing'), \
         patch.object(automation_analyzer, '_check_linting'), \
         patch.object(automation_analyzer, '_check_hook_points'), \
         patch.object(automation_analyzer, '_calculate_score'):
        
        # Should raise the exception since we're not handling it in the method
        with pytest.raises(Exception, match="CI/CD check failed"):
            automation_analyzer.analyze()


def test_analyze_continues_after_successful_checks(automation_analyzer):
    """Test that analyze continues execution through all check methods when they succeed."""
    call_order = []
    
    def track_ci_cd(result):
        call_order.append('ci_cd')
    
    def track_testing(result):
        call_order.append('testing')
    
    def track_linting(result):
        call_order.append('linting')
    
    def track_hooks(result):
        call_order.append('hooks')
    
    def track_score(result):
        call_order.append('score')
    
    with patch.object(automation_analyzer, '_check_ci_cd', side_effect=track_ci_cd), \
         patch.object(automation_analyzer, '_check_testing', side_effect=track_testing), \
         patch.object(automation_analyzer, '_check_linting', side_effect=track_linting), \
         patch.object(automation_analyzer, '_check_hook_points', side_effect=track_hooks), \
         patch.object(automation_analyzer, '_calculate_score', side_effect=track_score):
        
        result = automation_analyzer.analyze()
        
        assert call_order == ['ci_cd', 'testing', 'linting', 'hooks', 'score']
        assert isinstance(result, AnalyzerResult)


@patch('code_improvement_agent.analyzers.automation.AnalyzerResult')
def test_analyze_creates_result_with_analyzer_name(mock_result_class, automation_analyzer):
    """Test that analyze creates AnalyzerResult with the correct analyzer name."""
    mock_instance = Mock()
    mock_result_class.return_value = mock_instance
    
    with patch.object(automation_analyzer, '_check_ci_cd'), \
         patch.object(automation_analyzer, '_check_testing'), \
         patch.object(automation_analyzer, '_check_linting'), \
         patch.object(automation_analyzer, '_check_hook_points'), \
         patch.object(automation_analyzer, '_calculate_score'):
        
        result = automation_analyzer.analyze()
        
        mock_result_class.assert_called_once_with(analyzer_name=automation_analyzer.name)
        assert result is mock_instance
