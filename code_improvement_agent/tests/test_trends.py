import json
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock
from datetime import datetime

from code_improvement_agent.trends import save_run, load_history, format_trend_section


@pytest.fixture
def temp_repo_path():
    return "/tmp/test_repo"


@pytest.fixture
def sample_scores():
    return {
        "quality": 8.5,
        "structure": 7.2,
        "security": 9.0,
        "usefulness": 6.8,
        "overall": 7.9
    }


@pytest.fixture
def sample_metadata():
    return {
        "total_findings": 42,
        "files_analyzed": 15,
        "mode": "static"
    }


@pytest.fixture
def mock_history():
    return {
        "version": "1.0",
        "runs": []
    }


@pytest.fixture
def mock_history_with_runs():
    return {
        "version": "1.0",
        "runs": [
            {
                "timestamp": "2023-01-01T10:00:00",
                "scores": {
                    "quality": 7.0,
                    "structure": 6.5,
                    "security": 8.5,
                    "usefulness": 6.0,
                    "overall": 7.0
                },
                "findings_count": 35,
                "files_analyzed": 12,
                "mode": "static"
            },
            {
                "timestamp": "2023-01-02T11:00:00",
                "scores": {
                    "quality": 8.0,
                    "structure": 7.0,
                    "security": 9.0,
                    "usefulness": 6.5,
                    "overall": 7.6
                },
                "findings_count": 28,
                "files_analyzed": 14,
                "mode": "static"
            }
        ]
    }


class TestSaveRun:
    @patch('code_improvement_agent.trends._load_raw')
    @patch('code_improvement_agent.trends._history_path')
    @patch('code_improvement_agent.trends.datetime')
    def test_save_run_creates_new_entry(self, mock_datetime, mock_history_path, mock_load_raw, 
                                       temp_repo_path, sample_scores, sample_metadata, mock_history):
        mock_datetime.now.return_value.isoformat.return_value = "2023-01-01T12:00:00"
        mock_load_raw.return_value = mock_history
        mock_path = MagicMock()
        mock_history_path.return_value = mock_path
        
        save_run(temp_repo_path, sample_scores, sample_metadata)
        
        mock_load_raw.assert_called_once_with(temp_repo_path)
        expected_entry = {
            "timestamp": "2023-01-01T12:00:00",
            "scores": {
                "quality": 8.5,
                "structure": 7.2,
                "security": 9.0,
                "usefulness": 6.8,
                "overall": 7.9,
            },
            "findings_count": 42,
            "files_analyzed": 15,
            "mode": "static",
        }
        assert mock_history["runs"] == [expected_entry]
        mock_path.write_text.assert_called_once()

    @patch('code_improvement_agent.trends._load_raw')
    @patch('code_improvement_agent.trends._history_path')
    @patch('code_improvement_agent.trends.datetime')
    def test_save_run_handles_missing_scores(self, mock_datetime, mock_history_path, mock_load_raw, 
                                           temp_repo_path, mock_history):
        mock_datetime.now.return_value.isoformat.return_value = "2023-01-01T12:00:00"
        mock_load_raw.return_value = mock_history
        mock_path = MagicMock()
        mock_history_path.return_value = mock_path
        
        save_run(temp_repo_path, {}, {})
        
        expected_entry = {
            "timestamp": "2023-01-01T12:00:00",
            "scores": {
                "quality": 0.0,
                "structure": 0.0,
                "security": 0.0,
                "usefulness": 0.0,
                "overall": 0.0,
            },
            "findings_count": 0,
            "files_analyzed": 0,
            "mode": "static",
        }
        assert mock_history["runs"] == [expected_entry]

    @patch('code_improvement_agent.trends._load_raw')
    @patch('code_improvement_agent.trends._history_path')
    @patch('code_improvement_agent.trends.datetime')
    def test_save_run_handles_partial_scores(self, mock_datetime, mock_history_path, mock_load_raw, 
                                           temp_repo_path, mock_history):
        mock_datetime.now.return_value.isoformat.return_value = "2023-01-01T12:00:00"
        mock_load_raw.return_value = mock_history
        mock_path = MagicMock()
        mock_history_path.return_value = mock_path
        
        partial_scores = {"quality": 5.0, "overall": 6.0}
        partial_metadata = {"total_findings": 10, "mode": "dynamic"}
        
        save_run(temp_repo_path, partial_scores, partial_metadata)
        
        expected_entry = {
            "timestamp": "2023-01-01T12:00:00",
            "scores": {
                "quality": 5.0,
                "structure": 0.0,
                "security": 0.0,
                "usefulness": 0.0,
                "overall": 6.0,
            },
            "findings_count": 10,
            "files_analyzed": 0,
            "mode": "dynamic",
        }
        assert mock_history["runs"] == [expected_entry]

    @patch('code_improvement_agent.trends._load_raw')
    @patch('code_improvement_agent.trends._history_path')
    @patch('code_improvement_agent.trends.datetime')
    @patch('code_improvement_agent.trends.logger')
    def test_save_run_handles_write_error(self, mock_logger, mock_datetime, mock_history_path, 
                                        mock_load_raw, temp_repo_path, sample_scores, sample_metadata, mock_history):
        mock_datetime.now.return_value.isoformat.return_value = "2023-01-01T12:00:00"
        mock_load_raw.return_value = mock_history
        mock_path = MagicMock()
        mock_path.write_text.side_effect = OSError("Permission denied")
        mock_history_path.return_value = mock_path
        
        save_run(temp_repo_path, sample_scores, sample_metadata)
        
        mock_logger.warning.assert_called_once_with("Could not write trend history: %s", mock_path.write_text.side_effect)


class TestLoadHistory:
    @patch('code_improvement_agent.trends._load_raw')
    def test_load_history_returns_runs(self, mock_load_raw, temp_repo_path, mock_history_with_runs):
        mock_load_raw.return_value = mock_history_with_runs
        
        result = load_history(temp_repo_path)
        
        assert result == mock_history_with_runs["runs"]
        mock_load_raw.assert_called_once_with(temp_repo_path)

    @patch('code_improvement_agent.trends._load_raw')
    def test_load_history_returns_empty_list_when_no_runs(self, mock_load_raw, temp_repo_path):
        mock_load_raw.return_value = {"version": "1.0"}
        
        result = load_history(temp_repo_path)
        
        assert result == []

    @patch('code_improvement_agent.trends._load_raw')
    def test_load_history_returns_empty_list_when_runs_is_none(self, mock_load_raw, temp_repo_path):
        mock_load_raw.return_value = {"version": "1.0", "runs": None}
        
        result = load_history(temp_repo_path)
        
        assert result == []


class TestFormatTrendSection:
    @patch('code_improvement_agent.trends.load_history')
    @patch('code_improvement_agent.trends._first_run_section')
    def test_format_trend_section_first_run_no_history(self, mock_first_run, mock_load_history, 
                                                      temp_repo_path, sample_scores):
        mock_load_history.return_value = []
        mock_first_run.return_value = "## First Run\nWelcome!"
        
        result = format_trend_section(temp_repo_path, sample_scores)
        
        assert result == "## First Run\nWelcome!"
        mock_first_run.assert_called_once()

    @patch('code_improvement_agent.trends.load_history')
    @patch('code_improvement_agent.trends._first_run_section')
    def test_format_trend_section_first_run_single_entry(self, mock_first_run, mock_load_history, 
                                                        temp_repo_path, sample_scores):
        mock_load_history.return_value = [{"timestamp": "2023-01-01T10:00:00"}]
        mock_first_run.return_value = "## First Run\nWelcome!"
        
        result = format_trend_section(temp_repo_path, sample_scores)
        
        assert result == "## First Run\nWelcome!"
        mock_first_run.assert_called_once()

    @patch('code_improvement_agent.trends.load_history')
    def test_format_trend_section_with_improvement(self, mock_load_history, temp_repo_path):
        mock_load_history.return_value = [
            {
                "scores": {
                    "quality": 7.0,
                    "structure": 6.5,
                    "security": 8.5,
                    "usefulness": 6.0,
                    "overall": 7.0
                }
            },
            {
                "scores": {
                    "quality": 8.0,
                    "structure": 7.0,
                    "security": 9.0,
                    "usefulness": 6.5,
                    "overall": 7.6
                }
            }
        ]
        current_scores = {
            "quality": 8.5,
            "structure": 7.2,
            "security": 9.0,
            "usefulness": 6.8,
            "overall": 7.9
        }
        
        result = format_trend_section(temp_repo_path, current_scores)
        
        assert "## Trend Tracking" in result
        assert "**Runs tracked:** 2" in result
        assert "| Quality | 8.0 | 8.5 | ↑ +0.5 |" in result
        assert "| Structure | 7.0 | 7.2 | ↑ +0.2 |" in result
        assert "| **Overall** | 7.6 | 7.9 | ↑ +0.3 |" in result
        assert "**Best overall score:** 7.9" in result
        assert "**Worst overall score:** 7.0" in result

    @patch('code_improvement_agent.trends.load_history')
    def test_format_trend_section_with_regression(self, mock_load_history, temp_repo_path):
        mock_load_history.return_value = [
            {
                "scores": {
                    "quality": 8.0,
                    "structure": 7.0,
                    "security": 9.0,
                    "usefulness": 7.0,
                    "overall": 7.8
                }
            },
            {
                "scores": {
                    "quality": 8.5,
                    "structure": 7.5,
                    "security": 8.5,
                    "usefulness": 6.5,
                    "overall": 7.7
                }
            }
        ]
        current_scores = {
            "quality": 7.5,
            "structure": 7.0,
            "security": 8.0,
            "usefulness": 6.0,
            "overall": 7.1
        }
        
        result = format_trend_section(temp_repo_path, current_scores)
        
        assert "### Regression Warnings" in result
        assert "**Quality** dropped from 8.5 to 7.5 (-1.0)" in result
        assert "**Structure** dropped from 7.5 to 7.0 (-0.5)" in result
        assert "**Security** dropped from 8.5 to 8.0 (-0.5)" in result
        assert "**Usefulness** dropped from 6.5 to 6.0 (-0.5)" in result
        assert "**Overall** dropped from 7.7 to 7.1 (-0.6)" in result

    @patch('code_improvement_agent.trends.load_history')
    def test_format_trend_section_with_no_change(self, mock_load_history, temp_repo_path):
        mock_load_history.return_value = [
            {
                "scores": {
                    "quality": 8.0,
                    "structure": 7.0,
                    "security": 9.0,
                    "usefulness": 6.0,
                    "overall": 7.5
                }
            },
            {
                "scores": {
                    "quality": 8.0,
                    "structure": 7.0,
                    "security": 9.0,
                    "usefulness": 6.0,
                    "overall": 7.5
                }
            }
        ]
        current_scores = {
            "quality": 8.0,
            "structure": 7.0,
            "security": 9.0,
            "usefulness": 6.0,
            "overall": 7.5
        }
        
        result = format_trend_section(temp_repo_path, current_scores)
        
        assert "| Quality | 8.0 | 8.0 | → 0.0 |" in result
        assert "| **Overall** | 7.5 | 7.5 | → 0.0 |" in result
        assert "### Regression Warnings" not in result

    @patch('code_improvement_agent.trends.load_history')
    def test_format_trend_section_handles_missing_scores(self, mock_load_history, temp_repo_path):
        mock_load_history.return_value = [
            {
                "scores": {}
            },
            {
                "scores": {
                    "quality": 5.0
                }
            }
        ]
        current_scores = {
            "quality": 6.0,
            "overall": 7.0
        }
        
        result = format_trend_section(temp_repo_path, current_scores)
        
        assert "| Quality | 5.0 | 6.0 | ↑ +1.0 |" in result
        assert "| Structure | 0.0 | 0.0 | → 0.0 |" in result
        assert "| **Overall** | 0.0 | 7.0 | ↑ +7.0 |" in result
