import json
import pytest
from unittest.mock import Mock, patch, MagicMock

from code_improvement_agent.smart_analyzer import validate_findings, deep_review
from code_improvement_agent.analyzers.base import Finding, AnalyzerResult


class TestValidateFindings:
    
    @pytest.fixture
    def sample_findings(self):
        return [
            Finding(
                file="test.py",
                category="security",
                severity="high",
                title="SQL Injection Risk",
                description="Unsanitized user input",
                suggestion="Use parameterized queries",
                line=42
            ),
            Finding(
                file="test.py",
                category="bugs",
                severity="medium", 
                title="Null Pointer",
                description="Missing null check",
                suggestion="Add validation",
                line=55
            )
        ]
    
    @pytest.fixture
    def file_contents(self):
        return {
            "test.py": "def vulnerable_query(user_id):\n    return f'SELECT * FROM users WHERE id={user_id}'"
        }

    def test_validate_findings_empty_list_returns_empty(self):
        result = validate_findings([], {})
        assert result == []

    def test_validate_findings_no_file_contents_keeps_findings(self, sample_findings):
        result = validate_findings(sample_findings, {})
        assert len(result) == 2
        assert result == sample_findings

    @patch('code_improvement_agent.smart_analyzer.call_claude')
    def test_validate_findings_valid_response_filters_findings(self, mock_claude, sample_findings, file_contents):
        mock_claude.return_value = json.dumps([
            {
                "index": 1,
                "valid": True,
                "reason": "Real SQL injection vulnerability",
                "improved_suggestion": "Use SQLAlchemy with parameters"
            },
            {
                "index": 2,
                "valid": False,
                "reason": "False positive - variable is checked elsewhere",
                "improved_suggestion": None
            }
        ])
        
        result = validate_findings(sample_findings, file_contents)
        
        assert len(result) == 1
        assert result[0].title == "SQL Injection Risk"
        assert "Real SQL injection vulnerability" in result[0].description
        assert result[0].suggestion == "Use SQLAlchemy with parameters"

    @patch('code_improvement_agent.smart_analyzer.call_claude')
    def test_validate_findings_markdown_json_response(self, mock_claude, sample_findings, file_contents):
        mock_claude.return_value = "```json\n[{\"index\": 1, \"valid\": true, \"reason\": \"test\"}]\n```"
        
        result = validate_findings(sample_findings, file_contents)
        
        assert len(result) == 1

    @patch('code_improvement_agent.smart_analyzer.call_claude')
    def test_validate_findings_invalid_json_keeps_originals(self, mock_claude, sample_findings, file_contents):
        mock_claude.return_value = "invalid json response"
        
        result = validate_findings(sample_findings, file_contents)
        
        assert len(result) == 2
        assert result == sample_findings

    @patch('code_improvement_agent.smart_analyzer.call_claude')
    def test_validate_findings_claude_exception_keeps_originals(self, mock_claude, sample_findings, file_contents):
        mock_claude.side_effect = Exception("API error")
        
        result = validate_findings(sample_findings, file_contents)
        
        assert len(result) == 2
        assert result == sample_findings

    def test_validate_findings_groups_by_file(self, file_contents):
        findings = [
            Finding(file="file1.py", category="test", severity="low", title="Issue 1", description="", suggestion="", line=1),
            Finding(file="file2.py", category="test", severity="low", title="Issue 2", description="", suggestion="", line=1),
            Finding(file="file1.py", category="test", severity="low", title="Issue 3", description="", suggestion="", line=2)
        ]
        
        with patch('code_improvement_agent.smart_analyzer.call_claude') as mock_claude:
            mock_claude.return_value = json.dumps([
                {"index": 1, "valid": True, "reason": "test"}
            ])
            
            validate_findings(findings, {"file1.py": "content"})
            
            # Should be called twice - once for file1.py (2 findings), once for file2.py (1 finding)
            assert mock_claude.call_count == 2

    def test_validate_findings_multifile_finding_uses_first_file(self, file_contents):
        findings = [
            Finding(file="test.py, other.py", category="test", severity="low", title="Multi-file", description="", suggestion="", line=1)
        ]
        
        with patch('code_improvement_agent.smart_analyzer.call_claude') as mock_claude:
            mock_claude.return_value = json.dumps([{"index": 1, "valid": True, "reason": "test"}])
            
            result = validate_findings(findings, file_contents)
            
            mock_claude.assert_called_once()
            assert "test.py" in mock_claude.call_args[0][0]

    def test_validate_findings_truncates_long_content(self):
        long_content = "x" * 10000
        findings = [Finding(file="test.py", category="test", severity="low", title="Test", description="", suggestion="", line=1)]
        
        with patch('code_improvement_agent.smart_analyzer.call_claude') as mock_claude:
            mock_claude.return_value = json.dumps([{"index": 1, "valid": True, "reason": "test"}])
            
            validate_findings(findings, {"test.py": long_content})
            
            call_args = mock_claude.call_args[0][0]
            # Should be truncated to 8000 chars plus some extra text
            assert len(call_args) < len(long_content) + 1000

    @patch('code_improvement_agent.smart_analyzer.call_claude')
    def test_validate_findings_invalid_index_ignored(self, mock_claude, sample_findings, file_contents):
        mock_claude.return_value = json.dumps([
            {"index": 999, "valid": True, "reason": "Invalid index"},
            {"index": 1, "valid": True, "reason": "Valid"}
        ])
        
        result = validate_findings(sample_findings, file_contents)
        
        assert len(result) == 1
        assert "Valid" in result[0].description


class TestDeepReview:
    
    @pytest.fixture
    def sample_file_contents(self):
        return {
            "main.py": "def main():\n    print('Hello World')",
            "utils.py": "def helper():\n    pass",
            "config.json": '{"key": "value"}',  # Should be skipped
        }

    def test_deep_review_empty_contents_returns_empty_result(self):
        result = deep_review({})
        
        assert result.analyzer_name == "AI Deep Review"
        assert len(result.findings) == 0
        assert result.score == 10.0

    def test_deep_review_skips_non_code_files(self, sample_file_contents):
        with patch('code_improvement_agent.smart_analyzer.call_claude') as mock_claude:
            mock_claude.return_value = "[]"
            
            deep_review(sample_file_contents)
            
            call_args = mock_claude.call_args[0][0]
            assert "main.py" in call_args
            assert "utils.py" in call_args
            assert "config.json" not in call_args

    @patch('code_improvement_agent.smart_analyzer.call_claude')
    def test_deep_review_valid_response_creates_findings(self, mock_claude, sample_file_contents):
        mock_claude.return_value = json.dumps([
            {
                "file": "main.py",
                "severity": "high",
                "title": "Missing Error Handling",
                "description": "No exception handling around print statement",
                "suggestion": "Add try-catch block",
                "line": 2
            }
        ])
        
        result = deep_review(sample_file_contents)
        
        assert len(result.findings) == 1
        finding = result.findings[0]
        assert finding.file == "main.py"
        assert finding.severity == "high"
        assert finding.title == "Missing Error Handling"
        assert finding.line == 2
        assert finding.category == "ai_review"

    @patch('code_improvement_agent.smart_analyzer.call_claude')
    def test_deep_review_markdown_json_response(self, mock_claude, sample_file_contents):
        mock_claude.return_value = "```json\n[{\"file\": \"test.py\", \"severity\": \"low\", \"title\": \"Test\", \"description\": \"Test desc\", \"suggestion\": \"Test fix\"}]\n```"
        
        result = deep_review(sample_file_contents)
        
        assert len(result.findings) == 1

    @patch('code_improvement_agent.smart_analyzer.call_claude')
    def test_deep_review_invalid_json_handles_gracefully(self, mock_claude, sample_file_contents):
        mock_claude.return_value = "invalid json"
        
        result = deep_review(sample_file_contents)
        
        assert len(result.findings) == 0
        assert result.score == 10.0

    @patch('code_improvement_agent.smart_analyzer.call_claude')
    def test_deep_review_claude_exception_handles_gracefully(self, mock_claude, sample_file_contents):
        mock_claude.side_effect = Exception("API error")
        
        result = deep_review(sample_file_contents)
        
        assert len(result.findings) == 0
        assert result.score == 10.0

    @patch('code_improvement_agent.smart_analyzer.call_claude')
    def test_deep_review_score_deduction_by_severity(self, mock_claude, sample_file_contents):
        mock_claude.return_value = json.dumps([
            {"file": "test.py", "severity": "critical", "title": "Critical", "description": "", "suggestion": ""},
            {"file": "test.py", "severity": "high", "title": "High", "description": "", "suggestion": ""},
            {"file": "test.py", "severity": "medium", "title": "Medium", "description": "", "suggestion": ""},
            {"file": "test.py", "severity": "low", "title": "Low", "description": "", "suggestion": ""}
        ])
        
        result = deep_review(sample_file_contents)
        
        # Starting score 10.0 - 3.0 (critical) - 2.0 (high) - 1.0 (medium) - 0.3 (low) = 3.7
        expected_score = 10.0 - 3.0 - 2.0 - 1.0 - 0.3
        assert result.score == expected_score

    @patch('code_improvement_agent.smart_analyzer.call_claude')
    def test_deep_review_minimum_score_limit(self, mock_claude, sample_file_contents):
        # Create many critical findings to test minimum score
        findings = [{"file": "test.py", "severity": "critical", "title": f"Critical {i}", "description": "", "suggestion": ""} for i in range(10)]
        mock_claude.return_value = json.dumps(findings)
        
        result = deep_review(sample_file_contents)
        
        assert result.score == 1.0  # Should not go below 1.0

    def test_deep_review_truncates_long_files(self):
        long_content = "x" * 10000
        file_contents = {"test.py": long_content}
        
        with patch('code_improvement_agent.smart_analyzer.call_claude') as mock_claude:
            mock_claude.return_value = "[]"
            
            deep_review(file_contents)
            
            call_args = mock_claude.call_args[0][0]
            assert "file continues" in call_args

    def test_deep_review_respects_total_char_limit(self):
        # Create many files that would exceed 80k chars
        large_files = {f"file{i}.py": "x" * 5000 for i in range(20)}
        
        with patch('code_improvement_agent.smart_analyzer.call_claude') as mock_claude:
            mock_claude.return_value = "[]"
            
            deep_review(large_files)
            
            call_args = mock_claude.call_args[0][0]
            assert "skipped" in call_args
            assert len(call_args) < 90000  # Should stay within reasonable limits

    @patch('code_improvement_agent.smart_analyzer.call_claude')
    def test_deep_review_missing_fields_use_defaults(self, mock_claude, sample_file_contents):
        mock_claude.return_value = json.dumps([
            {"title": "Minimal Finding"}  # Missing most fields
        ])
        
        result = deep_review(sample_file_contents)
        
        assert len(result.findings) == 1
        finding = result.findings[0]
        assert finding.file == "(unknown)"
        assert finding.severity == "medium"
        assert finding.title == "Minimal Finding"
        assert finding.description == ""
        assert finding.suggestion == ""
        assert finding.line is None
