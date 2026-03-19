import pytest
from unittest.mock import patch, MagicMock
from code_improvement_agent.report import generate_report


@pytest.fixture
def mock_analyzer_result():
    result = MagicMock()
    result.file_path = "test_file.py"
    result.issues = []
    return result


@pytest.fixture
def mock_repo_score():
    score = MagicMock()
    score.overall_score = 85
    score.security_score = 90
    score.maintainability_score = 80
    return score


@pytest.fixture
def sample_analyzer_results(mock_analyzer_result):
    return [mock_analyzer_result]


@pytest.fixture
def sample_file_list():
    return ["file1.py", "file2.py", "test_file.py"]


@patch('code_improvement_agent.report._footer')
@patch('code_improvement_agent.report._next_iteration')
@patch('code_improvement_agent.report._file_analysis')
@patch('code_improvement_agent.report._top_improvements')
@patch('code_improvement_agent.report._summary')
@patch('code_improvement_agent.report._header')
def test_generate_report_calls_all_sections(
    mock_header, mock_summary, mock_top_improvements,
    mock_file_analysis, mock_next_iteration, mock_footer,
    sample_analyzer_results, mock_repo_score, sample_file_list
):
    mock_header.return_value = "# Header"
    mock_summary.return_value = "## Summary"
    mock_top_improvements.return_value = "## Top Improvements"
    mock_file_analysis.return_value = "## File Analysis"
    mock_next_iteration.return_value = "## Next Iteration"
    mock_footer.return_value = "---"

    result = generate_report(
        repo_path="/path/to/repo",
        app_description="Test app",
        analyzer_results=sample_analyzer_results,
        score=mock_repo_score,
        file_list=sample_file_list
    )

    mock_header.assert_called_once_with("/path/to/repo")
    mock_summary.assert_called_once_with("Test app", mock_repo_score, sample_analyzer_results, sample_file_list)
    mock_top_improvements.assert_called_once_with(sample_analyzer_results)
    mock_file_analysis.assert_called_once_with(sample_analyzer_results)
    mock_next_iteration.assert_called_once_with(sample_analyzer_results, mock_repo_score)
    mock_footer.assert_called_once()


@patch('code_improvement_agent.report._footer')
@patch('code_improvement_agent.report._next_iteration')
@patch('code_improvement_agent.report._file_analysis')
@patch('code_improvement_agent.report._top_improvements')
@patch('code_improvement_agent.report._summary')
@patch('code_improvement_agent.report._header')
def test_generate_report_joins_sections_with_double_newlines(
    mock_header, mock_summary, mock_top_improvements,
    mock_file_analysis, mock_next_iteration, mock_footer,
    sample_analyzer_results, mock_repo_score, sample_file_list
):
    mock_header.return_value = "Header"
    mock_summary.return_value = "Summary"
    mock_top_improvements.return_value = "Improvements"
    mock_file_analysis.return_value = "Analysis"
    mock_next_iteration.return_value = "Next"
    mock_footer.return_value = "Footer"

    result = generate_report(
        repo_path="/path/to/repo",
        app_description="Test app",
        analyzer_results=sample_analyzer_results,
        score=mock_repo_score,
        file_list=sample_file_list
    )

    expected = "Header\n\nSummary\n\nImprovements\n\nAnalysis\n\nNext\n\nFooter"
    assert result == expected


@patch('code_improvement_agent.report._footer')
@patch('code_improvement_agent.report._next_iteration')
@patch('code_improvement_agent.report._file_analysis')
@patch('code_improvement_agent.report._top_improvements')
@patch('code_improvement_agent.report._summary')
@patch('code_improvement_agent.report._header')
def test_generate_report_with_empty_analyzer_results(
    mock_header, mock_summary, mock_top_improvements,
    mock_file_analysis, mock_next_iteration, mock_footer,
    mock_repo_score, sample_file_list
):
    mock_header.return_value = "Header"
    mock_summary.return_value = "Summary"
    mock_top_improvements.return_value = "Improvements"
    mock_file_analysis.return_value = "Analysis"
    mock_next_iteration.return_value = "Next"
    mock_footer.return_value = "Footer"

    result = generate_report(
        repo_path="/path/to/repo",
        app_description="Test app",
        analyzer_results=[],
        score=mock_repo_score,
        file_list=sample_file_list
    )

    mock_summary.assert_called_once_with("Test app", mock_repo_score, [], sample_file_list)
    mock_top_improvements.assert_called_once_with([])
    mock_file_analysis.assert_called_once_with([])
    mock_next_iteration.assert_called_once_with([], mock_repo_score)
    assert result == "Header\n\nSummary\n\nImprovements\n\nAnalysis\n\nNext\n\nFooter"


@patch('code_improvement_agent.report._footer')
@patch('code_improvement_agent.report._next_iteration')
@patch('code_improvement_agent.report._file_analysis')
@patch('code_improvement_agent.report._top_improvements')
@patch('code_improvement_agent.report._summary')
@patch('code_improvement_agent.report._header')
def test_generate_report_with_empty_file_list(
    mock_header, mock_summary, mock_top_improvements,
    mock_file_analysis, mock_next_iteration, mock_footer,
    sample_analyzer_results, mock_repo_score
):
    mock_header.return_value = "Header"
    mock_summary.return_value = "Summary"
    mock_top_improvements.return_value = "Improvements"
    mock_file_analysis.return_value = "Analysis"
    mock_next_iteration.return_value = "Next"
    mock_footer.return_value = "Footer"

    result = generate_report(
        repo_path="/path/to/repo",
        app_description="Test app",
        analyzer_results=sample_analyzer_results,
        score=mock_repo_score,
        file_list=[]
    )

    mock_summary.assert_called_once_with("Test app", mock_repo_score, sample_analyzer_results, [])
    assert result == "Header\n\nSummary\n\nImprovements\n\nAnalysis\n\nNext\n\nFooter"


@patch('code_improvement_agent.report._footer')
@patch('code_improvement_agent.report._next_iteration')
@patch('code_improvement_agent.report._file_analysis')
@patch('code_improvement_agent.report._top_improvements')
@patch('code_improvement_agent.report._summary')
@patch('code_improvement_agent.report._header')
def test_generate_report_with_empty_strings_from_sections(
    mock_header, mock_summary, mock_top_improvements,
    mock_file_analysis, mock_next_iteration, mock_footer,
    sample_analyzer_results, mock_repo_score, sample_file_list
):
    mock_header.return_value = ""
    mock_summary.return_value = ""
    mock_top_improvements.return_value = ""
    mock_file_analysis.return_value = ""
    mock_next_iteration.return_value = ""
    mock_footer.return_value = ""

    result = generate_report(
        repo_path="/path/to/repo",
        app_description="Test app",
        analyzer_results=sample_analyzer_results,
        score=mock_repo_score,
        file_list=sample_file_list
    )

    assert result == "\n\n\n\n\n\n"
