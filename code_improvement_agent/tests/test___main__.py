import argparse
import sys
import pytest
from unittest.mock import Mock, patch, mock_open
from pathlib import Path
from code_improvement_agent.__main__ import main


@pytest.fixture
def mock_dependencies():
    """Mock all external dependencies for main()"""
    with patch('code_improvement_agent.__main__.run_analysis') as mock_run_analysis, \
         patch('code_improvement_agent.__main__._print_cost_estimate') as mock_cost_estimate, \
         patch('code_improvement_agent.__main__._write_output') as mock_write_output, \
         patch('sys.exit') as mock_exit:
        
        mock_run_analysis.return_value = ("Mock report", {"scores": {"overall": 8}, "tag": "good", "recommendation": "minor improvements", "total_findings": 3, "mode": "static"})
        yield {
            'run_analysis': mock_run_analysis,
            'cost_estimate': mock_cost_estimate,
            'write_output': mock_write_output,
            'exit': mock_exit
        }


def test_main_with_default_arguments(mock_dependencies, tmp_path):
    """Test main() with default arguments (current directory)"""
    with patch('sys.argv', ['code-improvement-agent']), \
         patch('pathlib.Path.resolve', return_value=tmp_path), \
         patch('pathlib.Path.is_dir', return_value=True):
        
        main()
        
        mock_dependencies['run_analysis'].assert_called_once_with(
            str(tmp_path),
            smart=False,
            auto_fix=False,
            apply_fixes=False,
            config_path=None,
            gen_tests=False,
            write_tests=False
        )


def test_main_with_custom_repo_path(mock_dependencies, tmp_path):
    """Test main() with custom repository path"""
    repo_path = tmp_path / "custom_repo"
    repo_path.mkdir()
    
    with patch('sys.argv', ['code-improvement-agent', str(repo_path)]), \
         patch('pathlib.Path.resolve', return_value=repo_path), \
         patch('pathlib.Path.is_dir', return_value=True):
        
        main()
        
        mock_dependencies['run_analysis'].assert_called_once_with(
            str(repo_path),
            smart=False,
            auto_fix=False,
            apply_fixes=False,
            config_path=None,
            gen_tests=False,
            write_tests=False
        )


def test_main_with_output_file(mock_dependencies, tmp_path):
    """Test main() with output file argument"""
    with patch('sys.argv', ['code-improvement-agent', '--output', 'report.txt']), \
         patch('pathlib.Path.resolve', return_value=tmp_path), \
         patch('pathlib.Path.is_dir', return_value=True):
        
        main()
        
        mock_dependencies['write_output'].assert_called_once_with(
            "Mock report",
            {"scores": {"overall": 8}, "tag": "good", "recommendation": "minor improvements", "total_findings": 3, "mode": "static"},
            'report.txt',
            False,
            False
        )


def test_main_with_json_output(mock_dependencies, tmp_path):
    """Test main() with JSON output flag"""
    with patch('sys.argv', ['code-improvement-agent', '--json']), \
         patch('pathlib.Path.resolve', return_value=tmp_path), \
         patch('pathlib.Path.is_dir', return_value=True):
        
        main()
        
        mock_dependencies['write_output'].assert_called_once_with(
            "Mock report",
            {"scores": {"overall": 8}, "tag": "good", "recommendation": "minor improvements", "total_findings": 3, "mode": "static"},
            None,
            True,
            False
        )


def test_main_with_quiet_flag(mock_dependencies, tmp_path):
    """Test main() with quiet flag"""
    with patch('sys.argv', ['code-improvement-agent', '--quiet']), \
         patch('pathlib.Path.resolve', return_value=tmp_path), \
         patch('pathlib.Path.is_dir', return_value=True):
        
        main()
        
        mock_dependencies['write_output'].assert_called_once_with(
            "Mock report",
            {"scores": {"overall": 8}, "tag": "good", "recommendation": "minor improvements", "total_findings": 3, "mode": "static"},
            None,
            False,
            True
        )


def test_main_with_smart_mode(mock_dependencies, tmp_path):
    """Test main() with smart mode enabled"""
    with patch('sys.argv', ['code-improvement-agent', '--smart']), \
         patch('pathlib.Path.resolve', return_value=tmp_path), \
         patch('pathlib.Path.is_dir', return_value=True), \
         patch('logging.basicConfig') as mock_logging:
        
        main()
        
        mock_logging.assert_called_once()
        mock_dependencies['run_analysis'].assert_called_once_with(
            str(tmp_path),
            smart=True,
            auto_fix=False,
            apply_fixes=False,
            config_path=None,
            gen_tests=False,
            write_tests=False
        )


def test_main_with_auto_fix_mode(mock_dependencies, tmp_path):
    """Test main() with auto-fix mode enabled"""
    with patch('sys.argv', ['code-improvement-agent', '--auto-fix']), \
         patch('pathlib.Path.resolve', return_value=tmp_path), \
         patch('pathlib.Path.is_dir', return_value=True), \
         patch('logging.basicConfig') as mock_logging:
        
        main()
        
        mock_logging.assert_called_once()
        mock_dependencies['run_analysis'].assert_called_once_with(
            str(tmp_path),
            smart=False,
            auto_fix=True,
            apply_fixes=False,
            config_path=None,
            gen_tests=False,
            write_tests=False
        )


def test_main_with_apply_flag(mock_dependencies, tmp_path):
    """Test main() with apply flag"""
    with patch('sys.argv', ['code-improvement-agent', '--apply']), \
         patch('pathlib.Path.resolve', return_value=tmp_path), \
         patch('pathlib.Path.is_dir', return_value=True):
        
        main()
        
        mock_dependencies['run_analysis'].assert_called_once_with(
            str(tmp_path),
            smart=False,
            auto_fix=False,
            apply_fixes=True,
            config_path=None,
            gen_tests=False,
            write_tests=False
        )


def test_main_with_config_path(mock_dependencies, tmp_path):
    """Test main() with custom config path"""
    with patch('sys.argv', ['code-improvement-agent', '--config', 'custom.yaml']), \
         patch('pathlib.Path.resolve', return_value=tmp_path), \
         patch('pathlib.Path.is_dir', return_value=True):
        
        main()
        
        mock_dependencies['run_analysis'].assert_called_once_with(
            str(tmp_path),
            smart=False,
            auto_fix=False,
            apply_fixes=False,
            config_path='custom.yaml',
            gen_tests=False,
            write_tests=False
        )


def test_main_with_gen_tests(mock_dependencies, tmp_path):
    """Test main() with generate tests flag"""
    with patch('sys.argv', ['code-improvement-agent', '--gen-tests']), \
         patch('pathlib.Path.resolve', return_value=tmp_path), \
         patch('pathlib.Path.is_dir', return_value=True), \
         patch('logging.basicConfig') as mock_logging:
        
        main()
        
        mock_logging.assert_called_once()
        mock_dependencies['run_analysis'].assert_called_once_with(
            str(tmp_path),
            smart=False,
            auto_fix=False,
            apply_fixes=False,
            config_path=None,
            gen_tests=True,
            write_tests=False
        )


def test_main_with_write_tests(mock_dependencies, tmp_path):
    """Test main() with write tests flag"""
    with patch('sys.argv', ['code-improvement-agent', '--write-tests']), \
         patch('pathlib.Path.resolve', return_value=tmp_path), \
         patch('pathlib.Path.is_dir', return_value=True):
        
        main()
        
        mock_dependencies['run_analysis'].assert_called_once_with(
            str(tmp_path),
            smart=False,
            auto_fix=False,
            apply_fixes=False,
            config_path=None,
            gen_tests=False,
            write_tests=True
        )


def test_main_with_cost_estimation(mock_dependencies, tmp_path):
    """Test main() with cost estimation mode"""
    with patch('sys.argv', ['code-improvement-agent', '--cost']), \
         patch('pathlib.Path.resolve', return_value=tmp_path), \
         patch('pathlib.Path.is_dir', return_value=True):
        
        main()
        
        mock_dependencies['cost_estimate'].assert_called_once_with(tmp_path, False)
        mock_dependencies['exit'].assert_called_once_with(0)
        mock_dependencies['run_analysis'].assert_not_called()


def test_main_with_cost_and_auto_fix(mock_dependencies, tmp_path):
    """Test main() with cost estimation and auto-fix flags"""
    with patch('sys.argv', ['code-improvement-agent', '--cost', '--auto-fix']), \
         patch('pathlib.Path.resolve', return_value=tmp_path), \
         patch('pathlib.Path.is_dir', return_value=True):
        
        main()
        
        mock_dependencies['cost_estimate'].assert_called_once_with(tmp_path, True)
        mock_dependencies['exit'].assert_called_once_with(0)


def test_main_with_invalid_directory():
    """Test main() with invalid directory path"""
    with patch('sys.argv', ['code-improvement-agent', '/nonexistent/path']), \
         patch('pathlib.Path.is_dir', return_value=False), \
         patch('sys.exit') as mock_exit:
        
        with patch('sys.stderr', new_callable=mock_open) as mock_stderr:
            main()
        
        mock_exit.assert_called_once_with(1)


def test_main_with_error_from_run_analysis(mock_dependencies, tmp_path):
    """Test main() when run_analysis returns an error"""
    mock_dependencies['run_analysis'].return_value = ("ERROR: Something went wrong", {})
    
    with patch('sys.argv', ['code-improvement-agent']), \
         patch('pathlib.Path.resolve', return_value=tmp_path), \
         patch('pathlib.Path.is_dir', return_value=True):
        
        main()
        
        mock_dependencies['exit'].assert_called_once_with(1)


def test_main_output_summary_not_quiet(mock_dependencies, tmp_path):
    """Test main() prints summary when not in quiet mode"""
    with patch('sys.argv', ['code-improvement-agent']), \
         patch('pathlib.Path.resolve', return_value=tmp_path), \
         patch('pathlib.Path.is_dir', return_value=True):
        
        with patch('sys.stderr', new_callable=mock_open) as mock_stderr:
            main()
        
        # Verify that summary information was written to stderr
        mock_stderr().write.assert_called()


def test_main_combined_flags(mock_dependencies, tmp_path):
    """Test main() with multiple flags combined"""
    with patch('sys.argv', ['code-improvement-agent', '--smart', '--auto-fix', '--apply', '--json', '--quiet']), \
         patch('pathlib.Path.resolve', return_value=tmp_path), \
         patch('pathlib.Path.is_dir', return_value=True), \
         patch('logging.basicConfig'):
        
        main()
        
        mock_dependencies['run_analysis'].assert_called_once_with(
            str(tmp_path),
            smart=True,
            auto_fix=True,
            apply_fixes=True,
            config_path=None,
            gen_tests=False,
            write_tests=False
        )
        
        mock_dependencies['write_output'].assert_called_once_with(
            "Mock report",
            {"scores": {"overall": 8}, "tag": "good", "recommendation": "minor improvements", "total_findings": 3, "mode": "static"},
            None,
            True,
            True
        )
