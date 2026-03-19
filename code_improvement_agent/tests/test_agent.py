import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from code_improvement_agent.agent import collect_files, infer_app_description, run_analysis


@pytest.fixture
def temp_repo():
    """Create a temporary directory with sample files for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)
        
        # Create some test files
        (repo_path / "main.py").write_text('"""Main module docstring"""\nprint("hello")')
        (repo_path / "utils.py").write_text("def helper(): pass")
        (repo_path / ".gitignore").write_text("*.pyc\n__pycache__/")
        (repo_path / "README.md").write_text("# My Project\n\nThis is a test project.")
        
        # Create subdirectory with file
        subdir = repo_path / "subdir"
        subdir.mkdir()
        (subdir / "module.py").write_text("class TestClass: pass")
        
        # Create ignored directory
        ignored_dir = repo_path / "node_modules"
        ignored_dir.mkdir()
        (ignored_dir / "package.js").write_text("module.exports = {}")
        
        yield str(repo_path)


@pytest.fixture
def empty_repo():
    """Create an empty temporary directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


def test_collect_files_normal_case(temp_repo):
    """Test collecting files from a repository with various file types."""
    result = collect_files(temp_repo)
    
    assert isinstance(result, dict)
    assert len(result) >= 4
    assert "main.py" in result
    assert "utils.py" in result
    assert ".gitignore" in result
    assert "README.md" in result
    assert "subdir/module.py" in result
    
    # Check content is read correctly
    assert '"""Main module docstring"""' in result["main.py"]
    assert "This is a test project." in result["README.md"]


def test_collect_files_skips_ignored_directories(temp_repo):
    """Test that ignored directories are skipped."""
    result = collect_files(temp_repo)
    
    # Should not contain files from node_modules
    node_modules_files = [k for k in result.keys() if k.startswith("node_modules/")]
    assert len(node_modules_files) == 0


def test_collect_files_empty_repo(empty_repo):
    """Test collecting files from an empty repository."""
    result = collect_files(empty_repo)
    
    assert result == {}


def test_collect_files_nonexistent_path():
    """Test collecting files from a nonexistent path."""
    result = collect_files("/nonexistent/path")
    
    assert result == {}


@patch('code_improvement_agent.agent.MAX_FILE_SIZE', 10)
def test_collect_files_skips_large_files(temp_repo):
    """Test that files larger than MAX_FILE_SIZE are skipped."""
    # Create a large file
    large_file = Path(temp_repo) / "large.py"
    large_file.write_text("x" * 20)  # Larger than mocked MAX_FILE_SIZE of 10
    
    result = collect_files(temp_repo)
    
    assert "large.py" not in result


def test_collect_files_handles_unicode_errors(temp_repo):
    """Test that files with unicode decode errors are skipped gracefully."""
    # Create a file with binary content that will cause UnicodeDecodeError
    binary_file = Path(temp_repo) / "binary.py"
    binary_file.write_bytes(b'\x80\x81\x82\x83')
    
    # Should not raise exception
    result = collect_files(temp_repo)
    
    # Binary file should be skipped
    assert "binary.py" not in result


def test_infer_app_description_from_readme():
    """Test inferring description from README.md."""
    file_contents = {
        "README.md": "# My App\n\nThis is a great application that does amazing things.\n\nMore details here.",
        "main.py": '"""Module docstring"""\ncode here'
    }
    
    result = infer_app_description(file_contents)
    
    assert result == "This is a great application that does amazing things."


def test_infer_app_description_from_readme_variants():
    """Test inferring description from different README file names."""
    test_cases = [
        ("readme.md", "# Project\n\nDescription from lowercase readme."),
        ("README.rst", "Project Title\n=============\n\nRST format description."),
        ("README.txt", "Plain text description in README.txt")
    ]
    
    for filename, content in test_cases:
        file_contents = {filename: content}
        result = infer_app_description(file_contents)
        assert len(result) > 0
        assert not result.startswith("#")


def test_infer_app_description_skips_markdown_artifacts():
    """Test that markdown artifacts are skipped when finding description."""
    file_contents = {
        "README.md": "# Title\n\n![image](url)\n\n<!-- comment -->\n\n```code```\n\n---\n\nActual description here."
    }
    
    result = infer_app_description(file_contents)
    
    assert result == "Actual description here."


def test_infer_app_description_from_docstring():
    """Test falling back to module docstrings when no README exists."""
    file_contents = {
        "main.py": '"""This is the main module that handles everything."""\ndef main(): pass',
        "utils.py": "def helper(): pass"
    }
    
    result = infer_app_description(file_contents)
    
    assert result == "This is the main module that handles everything."


def test_infer_app_description_truncates_long_text():
    """Test that descriptions are truncated to 300 characters."""
    long_description = "x" * 500
    file_contents = {
        "README.md": f"# Title\n\n{long_description}"
    }
    
    result = infer_app_description(file_contents)
    
    assert len(result) == 300
    assert result == "x" * 300


def test_infer_app_description_no_sources():
    """Test fallback message when no README or docstrings found."""
    file_contents = {
        "main.py": "def main(): pass",
        "utils.py": "# Just a comment\nprint('hello')"
    }
    
    result = infer_app_description(file_contents)
    
    assert result == "(Could not determine — no README or module docstrings found)"


@patch('code_improvement_agent.agent.load_config')
@patch('code_improvement_agent.agent.collect_files')
@patch('code_improvement_agent.agent.infer_app_description')
@patch('code_improvement_agent.agent.ALL_ANALYZERS', [])
@patch('code_improvement_agent.agent.compute_repo_score')
@patch('code_improvement_agent.agent.classify_tag')
@patch('code_improvement_agent.agent.recommend_action')
@patch('code_improvement_agent.agent.generate_report')
@patch('code_improvement_agent.agent._build_metadata')
@patch('code_improvement_agent.agent._insert_trend_section')
def test_run_analysis_basic_flow(mock_trend, mock_metadata, mock_report, mock_recommend, 
                                mock_classify, mock_score, mock_description, mock_collect, 
                                mock_config):
    """Test basic flow of run_analysis without optional features."""
    # Setup mocks
    mock_config.return_value = {}
    mock_collect.return_value = {"main.py": "code"}
    mock_description.return_value = "Test app"
    mock_score.return_value = Mock(tag=None, recommendation=None)
    mock_classify.return_value = "web"
    mock_recommend.return_value = "good"
    mock_report.return_value = "Test report\n---\n\n*Generated by"
    mock_metadata.return_value = {"files": 1}
    mock_trend.return_value = "Final report"
    
    report, metadata = run_analysis("/test/repo")
    
    assert report == "Final report"
    assert metadata == {"files": 1}
    mock_collect.assert_called_once()
    mock_description.assert_called_once()
    mock_report.assert_called_once()


@patch('code_improvement_agent.agent.load_config')
@patch('code_improvement_agent.agent.collect_files')
def test_run_analysis_no_files_found(mock_collect, mock_config):
    """Test run_analysis when no analyzable files are found."""
    mock_config.return_value = {}
    mock_collect.return_value = {}
    
    report, metadata = run_analysis("/test/repo")
    
    assert report == "ERROR: No analyzable files found in the repository."
    assert metadata == {}


@patch('code_improvement_agent.agent.load_config')
@patch('code_improvement_agent.agent.collect_files')
@patch('code_improvement_agent.agent.infer_app_description')
@patch('code_improvement_agent.agent.ALL_ANALYZERS', [])
@patch('code_improvement_agent.agent.compute_repo_score')
@patch('code_improvement_agent.agent.classify_tag')
@patch('code_improvement_agent.agent.recommend_action')
@patch('code_improvement_agent.agent.generate_report')
@patch('code_improvement_agent.agent._build_metadata')
@patch('code_improvement_agent.agent._insert_trend_section')
@patch('code_improvement_agent.agent._run_smart_analysis')
def test_run_analysis_smart_mode(mock_smart, mock_trend, mock_metadata, mock_report, 
                                mock_recommend, mock_classify, mock_score, mock_description, 
                                mock_collect, mock_config):
    """Test run_analysis with smart mode enabled."""
    # Setup mocks
    mock_config.return_value = {}
    mock_collect.return_value = {"main.py": "code"}
    mock_description.return_value = "Test app"
    mock_score.return_value = Mock(tag=None, recommendation=None)
    mock_classify.return_value = "web"
    mock_recommend.return_value = "good"
    mock_report.return_value = "Test report\nAgent Version:** 1.0.0\n---\n\n*Generated by"
    mock_metadata.return_value = {"files": 1}
    mock_trend.return_value = "Final report"
    
    report, metadata = run_analysis("/test/repo", smart=True)
    
    mock_smart.assert_called_once()
    assert "Agent Version:** 2.0.0 (Smart)" in report


@patch('code_improvement_agent.agent.load_config')
@patch('code_improvement_agent.agent.collect_files')
@patch('code_improvement_agent.agent.infer_app_description')
@patch('code_improvement_agent.agent.ALL_ANALYZERS', [])
@patch('code_improvement_agent.agent.compute_repo_score')
@patch('code_improvement_agent.agent.classify_tag')
@patch('code_improvement_agent.agent.recommend_action')
@patch('code_improvement_agent.agent.generate_report')
@patch('code_improvement_agent.agent._build_metadata')
@patch('code_improvement_agent.agent._insert_trend_section')
@patch('code_improvement_agent.agent._run_auto_fix')
def test_run_analysis_auto_fix_mode(mock_auto_fix, mock_trend, mock_metadata, mock_report, 
                                   mock_recommend, mock_classify, mock_score, mock_description, 
                                   mock_collect, mock_config):
    """Test run_analysis with auto_fix mode enabled."""
    # Setup mocks
    mock_config.return_value = {}
    mock_collect.return_value = {"main.py": "code"}
    mock_description.return_value = "Test app"
    mock_score.return_value = Mock(tag=None, recommendation=None)
    mock_classify.return_value = "web"
    mock_recommend.return_value = "good"
    mock_report.return_value = "Test report\n---\n\n*Generated by"
    mock_metadata.return_value = {"files": 1}
    mock_trend.return_value = "Final report"
    mock_auto_fix.return_value = "Patches applied"
    
    report, metadata = run_analysis("/test/repo", auto_fix=True, apply_fixes=True)
    
    mock_auto_fix.assert_called_once()
    assert "Patches applied" in report


@patch('code_improvement_agent.agent.load_config')
@patch('code_improvement_agent.agent.collect_files')
@patch('code_improvement_agent.agent.infer_app_description')
@patch('code_improvement_agent.agent.ALL_ANALYZERS', [])
@patch('code_improvement_agent.agent.compute_repo_score')
@patch('code_improvement_agent.agent.classify_tag')
@patch('code_improvement_agent.agent.recommend_action')
@patch('code_improvement_agent.agent.generate_report')
@patch('code_improvement_agent.agent._build_metadata')
@patch('code_improvement_agent.agent._insert_trend_section')
@patch('code_improvement_agent.agent.generate_tests')
@patch('code_improvement_agent.agent.format_test_report')
def test_run_analysis_generate_tests(mock_format_test, mock_gen_tests, mock_trend, mock_metadata, 
                                    mock_report, mock_recommend, mock_classify, mock_score, 
                                    mock_description, mock_collect, mock_config):
    """Test run_analysis with test generation enabled."""
    # Setup mocks
    mock_config.return_value = {}
    mock_collect.return_value = {"main.py": "code"}
    mock_description.return_value = "Test app"
    mock_score.return_value = Mock(tag=None, recommendation=None)
    mock_classify.return_value = "web"
    mock_recommend.return_value = "good"
    mock_report.return_value = "Test report\n---\n\n*Generated by"
    mock_metadata.return_value = {"files": 1}
    mock_trend.return_value = "Final report"
    mock_gen_tests.return_value = {"generated": 5}
    mock_format_test.return_value = "Test generation report"
    
    report, metadata = run_analysis("/test/repo", gen_tests=True, write_tests=True)
    
    mock_gen_tests.assert_called_once()
    mock_format_test.assert_called_once()
    assert "Test generation report" in report
