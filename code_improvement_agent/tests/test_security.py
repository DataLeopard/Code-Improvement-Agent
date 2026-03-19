import pytest
from unittest.mock import Mock, patch
from code_improvement_agent.analyzers.security import SecurityAnalyzer
from code_improvement_agent.analyzers.base import AnalyzerResult
from code_improvement_agent.config import Config


@pytest.fixture
def mock_security_analyzer():
    analyzer = SecurityAnalyzer("/fake", {}, config=Config())
    analyzer.name = "SecurityAnalyzer"
    analyzer.file_contents = {}
    return analyzer


@pytest.fixture
def sample_file_contents():
    return {
        "app.py": "import os\nprint('Hello World')",
        "config.py": "API_KEY = 'secret123'\neval(user_input)",
        "utils.py": "import subprocess\nsubprocess.call(['ls'])"
    }


def test_analyze_returns_analyzer_result(mock_security_analyzer):
    with patch.object(mock_security_analyzer, '_check_secrets'), \
         patch.object(mock_security_analyzer, '_check_unsafe_calls'), \
         patch.object(mock_security_analyzer, '_check_env_file'), \
         patch.object(mock_security_analyzer, '_check_gitignore'), \
         patch.object(mock_security_analyzer, '_calculate_score'):
        
        result = mock_security_analyzer.analyze()
        
        assert isinstance(result, AnalyzerResult)
        assert result.analyzer_name == "SecurityAnalyzer"


def test_analyze_calls_all_check_methods_for_each_file(mock_security_analyzer, sample_file_contents):
    mock_security_analyzer.file_contents = sample_file_contents
    
    with patch.object(mock_security_analyzer, '_check_secrets') as mock_secrets, \
         patch.object(mock_security_analyzer, '_check_unsafe_calls') as mock_unsafe, \
         patch.object(mock_security_analyzer, '_check_env_file') as mock_env, \
         patch.object(mock_security_analyzer, '_check_gitignore') as mock_gitignore, \
         patch.object(mock_security_analyzer, '_calculate_score') as mock_score:
        
        result = mock_security_analyzer.analyze()
        
        # Check that file-based methods are called for each file
        assert mock_secrets.call_count == 3
        assert mock_unsafe.call_count == 3
        
        # Check that global methods are called once
        mock_env.assert_called_once_with(result)
        mock_gitignore.assert_called_once_with(result)
        mock_score.assert_called_once_with(result)


def test_analyze_passes_correct_parameters_to_check_methods(mock_security_analyzer, sample_file_contents):
    mock_security_analyzer.file_contents = sample_file_contents
    
    with patch.object(mock_security_analyzer, '_check_secrets') as mock_secrets, \
         patch.object(mock_security_analyzer, '_check_unsafe_calls') as mock_unsafe, \
         patch.object(mock_security_analyzer, '_check_env_file'), \
         patch.object(mock_security_analyzer, '_check_gitignore'), \
         patch.object(mock_security_analyzer, '_calculate_score'):
        
        result = mock_security_analyzer.analyze()
        
        # Verify _check_secrets was called with correct parameters
        expected_calls = [
            ('app.py', "import os\nprint('Hello World')", result),
            ('config.py', "API_KEY = 'secret123'\neval(user_input)", result),
            ('utils.py', "import subprocess\nsubprocess.call(['ls'])", result)
        ]
        
        for i, (filepath, content, _) in enumerate(expected_calls):
            assert mock_secrets.call_args_list[i][0][0] == filepath
            assert mock_secrets.call_args_list[i][0][1] == content
            assert mock_secrets.call_args_list[i][0][2] == result
            
            assert mock_unsafe.call_args_list[i][0][0] == filepath
            assert mock_unsafe.call_args_list[i][0][1] == content
            assert mock_unsafe.call_args_list[i][0][2] == result


def test_analyze_with_empty_file_contents(mock_security_analyzer):
    mock_security_analyzer.file_contents = {}
    
    with patch.object(mock_security_analyzer, '_check_secrets') as mock_secrets, \
         patch.object(mock_security_analyzer, '_check_unsafe_calls') as mock_unsafe, \
         patch.object(mock_security_analyzer, '_check_env_file') as mock_env, \
         patch.object(mock_security_analyzer, '_check_gitignore') as mock_gitignore, \
         patch.object(mock_security_analyzer, '_calculate_score') as mock_score:
        
        result = mock_security_analyzer.analyze()
        
        # File-based methods should not be called
        mock_secrets.assert_not_called()
        mock_unsafe.assert_not_called()
        
        # Global methods should still be called
        mock_env.assert_called_once_with(result)
        mock_gitignore.assert_called_once_with(result)
        mock_score.assert_called_once_with(result)


def test_analyze_with_single_file(mock_security_analyzer):
    mock_security_analyzer.file_contents = {"single.py": "print('test')"}
    
    with patch.object(mock_security_analyzer, '_check_secrets') as mock_secrets, \
         patch.object(mock_security_analyzer, '_check_unsafe_calls') as mock_unsafe, \
         patch.object(mock_security_analyzer, '_check_env_file'), \
         patch.object(mock_security_analyzer, '_check_gitignore'), \
         patch.object(mock_security_analyzer, '_calculate_score'):
        
        mock_security_analyzer.analyze()
        
        mock_secrets.assert_called_once()
        mock_unsafe.assert_called_once()


def test_analyze_preserves_result_modifications_from_check_methods(mock_security_analyzer):
    mock_security_analyzer.file_contents = {"test.py": "test_content"}
    
    def modify_result(filepath, content, result):
        result.issues.append(f"Issue in {filepath}")
    
    with patch.object(mock_security_analyzer, '_check_secrets', side_effect=modify_result), \
         patch.object(mock_security_analyzer, '_check_unsafe_calls'), \
         patch.object(mock_security_analyzer, '_check_env_file'), \
         patch.object(mock_security_analyzer, '_check_gitignore'), \
         patch.object(mock_security_analyzer, '_calculate_score'):
        
        result = mock_security_analyzer.analyze()
        
        assert "Issue in test.py" in result.issues


def test_analyze_handles_exception_in_check_methods_gracefully(mock_security_analyzer):
    mock_security_analyzer.file_contents = {"test.py": "content"}
    
    with patch.object(mock_security_analyzer, '_check_secrets', side_effect=Exception("Test error")), \
         patch.object(mock_security_analyzer, '_check_unsafe_calls'), \
         patch.object(mock_security_analyzer, '_check_env_file'), \
         patch.object(mock_security_analyzer, '_check_gitignore'), \
         patch.object(mock_security_analyzer, '_calculate_score'):
        
        # Should raise the exception since we're not handling it in the method
        with pytest.raises(Exception, match="Test error"):
            mock_security_analyzer.analyze()
