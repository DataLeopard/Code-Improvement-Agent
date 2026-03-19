import json
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import pytest

from code_improvement_agent.auto_fix import generate_fixes, apply_patches, format_patches_report


class MockFinding:
    def __init__(self, severity, file, title, line, description, suggestion):
        self.severity = severity
        self.file = file
        self.title = title
        self.line = line
        self.description = description
        self.suggestion = suggestion


@pytest.fixture
def sample_findings():
    return [
        MockFinding("critical", "test.py", "SQL Injection", 10, "Unsafe query", "Use parameterized queries"),
        MockFinding("high", "test.py", "XSS Vulnerability", 20, "Unescaped output", "Escape user input"),
        MockFinding("low", "test.py", "Minor Issue", 30, "Small problem", "Fix it"),
        MockFinding("medium", "multi,file.py", "Multi-file Issue", 40, "Spans files", "Refactor"),
        MockFinding("critical", "missing.py", "Missing File", 50, "File not in contents", "Add file"),
    ]


@pytest.fixture
def file_contents():
    return {
        "test.py": "def vulnerable_function():\n    query = 'SELECT * FROM users WHERE id = ' + user_id\n    return execute(query)"
    }


def test_generate_fixes_filters_non_fixable_findings(sample_findings, file_contents):
    with patch('code_improvement_agent.auto_fix.call_claude') as mock_claude:
        mock_claude.return_value = "[]"
        
        patches = generate_fixes(sample_findings, file_contents, "/repo")
        
        # Should only process critical/high/medium findings in available files, excluding multi-file
        mock_claude.assert_called_once()
        call_args = mock_claude.call_args[0][0]
        assert "SQL Injection" in call_args
        assert "XSS Vulnerability" in call_args
        assert "Minor Issue" not in call_args  # low severity
        assert "Multi-file Issue" not in call_args  # contains comma
        assert "Missing File" not in call_args  # not in file_contents


def test_generate_fixes_returns_empty_when_no_fixable_findings():
    findings = [
        MockFinding("low", "test.py", "Minor", 10, "desc", "sugg"),
        MockFinding("critical", "missing.py", "Missing", 20, "desc", "sugg"),
    ]
    file_contents = {"test.py": "content"}
    
    with patch('code_improvement_agent.auto_fix.logger') as mock_logger:
        patches = generate_fixes(findings, file_contents, "/repo")
        
        assert patches == []
        mock_logger.info.assert_called_with("No fixable findings to generate patches for")


def test_generate_fixes_groups_findings_by_file(sample_findings, file_contents):
    with patch('code_improvement_agent.auto_fix.call_claude') as mock_claude:
        mock_claude.return_value = "[]"
        
        generate_fixes(sample_findings, file_contents, "/repo")
        
        # Should be called once for test.py with both critical and high findings
        assert mock_claude.call_count == 1
        call_args = mock_claude.call_args[0][0]
        assert "1. [CRITICAL] SQL Injection" in call_args
        assert "2. [HIGH] XSS Vulnerability" in call_args


def test_generate_fixes_creates_patches_from_valid_response(sample_findings, file_contents):
    claude_response = json.dumps([
        {
            "finding_index": 1,
            "original": "query = 'SELECT * FROM users WHERE id = ' + user_id",
            "fixed": "query = 'SELECT * FROM users WHERE id = %s'\nexecute(query, (user_id,))",
            "explanation": "Fixed SQL injection by using parameterized query"
        }
    ])
    
    with patch('code_improvement_agent.auto_fix.call_claude', return_value=claude_response):
        patches = generate_fixes(sample_findings, file_contents, "/repo")
        
        assert len(patches) == 1
        patch = patches[0]
        assert patch["file"] == "test.py"
        assert patch["finding"] == "SQL Injection"
        assert patch["original"] == "query = 'SELECT * FROM users WHERE id = ' + user_id"
        assert "parameterized query" in patch["fixed"]
        assert patch["explanation"] == "Fixed SQL injection by using parameterized query"


def test_generate_fixes_handles_claude_response_with_code_blocks(sample_findings, file_contents):
    claude_response = "```json\n" + json.dumps([
        {
            "finding_index": 1,
            "original": "query = 'SELECT * FROM users WHERE id = ' + user_id",
            "fixed": "query = 'SELECT * FROM users WHERE id = %s'",
            "explanation": "Fixed"
        }
    ]) + "\n```"
    
    with patch('code_improvement_agent.auto_fix.call_claude', return_value=claude_response):
        patches = generate_fixes(sample_findings, file_contents, "/repo")
        
        assert len(patches) == 1


def test_generate_fixes_skips_patches_with_original_not_in_file(sample_findings, file_contents):
    claude_response = json.dumps([
        {
            "finding_index": 1,
            "original": "nonexistent code",
            "fixed": "fixed code",
            "explanation": "Fix"
        }
    ])
    
    with patch('code_improvement_agent.auto_fix.call_claude', return_value=claude_response), \
         patch('code_improvement_agent.auto_fix.logger') as mock_logger:
        patches = generate_fixes(sample_findings, file_contents, "/repo")
        
        assert len(patches) == 0
        mock_logger.debug.assert_called_with("Skipping patch for test.py: original text not found in file")


def test_generate_fixes_handles_json_decode_error(sample_findings, file_contents):
    with patch('code_improvement_agent.auto_fix.call_claude', return_value="invalid json"), \
         patch('code_improvement_agent.auto_fix.logger') as mock_logger:
        patches = generate_fixes(sample_findings, file_contents, "/repo")
        
        assert patches == []
        mock_logger.warning.assert_called()
        assert "Could not parse fix response" in str(mock_logger.warning.call_args)


def test_generate_fixes_handles_claude_api_error(sample_findings, file_contents):
    with patch('code_improvement_agent.auto_fix.call_claude', side_effect=Exception("API Error")), \
         patch('code_improvement_agent.auto_fix.logger') as mock_logger:
        patches = generate_fixes(sample_findings, file_contents, "/repo")
        
        assert patches == []
        mock_logger.warning.assert_called()
        assert "Fix generation failed" in str(mock_logger.warning.call_args)


def test_generate_fixes_skips_files_with_empty_content(sample_findings):
    file_contents = {"test.py": ""}
    
    with patch('code_improvement_agent.auto_fix.call_claude') as mock_claude:
        patches = generate_fixes(sample_findings, file_contents, "/repo")
        
        mock_claude.assert_not_called()
        assert patches == []


@pytest.fixture
def sample_patches():
    return [
        {
            "file": "test.py",
            "finding": "SQL Injection",
            "original": "old_code = 'vulnerable'",
            "fixed": "new_code = 'safe'",
            "explanation": "Fixed vulnerability"
        }
    ]


def test_apply_patches_dry_run_default(sample_patches):
    with patch('pathlib.Path.exists', return_value=True), \
         patch('pathlib.Path.read_text', return_value="old_code = 'vulnerable'\nother_code"), \
         patch('code_improvement_agent.auto_fix.logger') as mock_logger:
        
        result = apply_patches(sample_patches, "/repo")
        
        assert len(result) == 1
        assert result[0]["status"] == "would_apply"
        mock_logger.info.assert_called_with("[DRY RUN] Would fix 'SQL Injection' in test.py")


def test_apply_patches_actual_apply(sample_patches):
    mock_file = mock_open(read_data="old_code = 'vulnerable'\nother_code")
    
    with patch('pathlib.Path.exists', return_value=True), \
         patch('pathlib.Path.read_text', return_value="old_code = 'vulnerable'\nother_code"), \
         patch('pathlib.Path.write_text') as mock_write, \
         patch('code_improvement_agent.auto_fix.logger') as mock_logger:
        
        result = apply_patches(sample_patches, "/repo", dry_run=False)
        
        assert len(result) == 1
        assert result[0]["status"] == "applied"
        mock_write.assert_called_once_with("new_code = 'safe'\nother_code", encoding="utf-8")
        mock_logger.info.assert_called_with("Applied fix: 'SQL Injection' in test.py")


def test_apply_patches_file_not_found(sample_patches):
    with patch('pathlib.Path.exists', return_value=False), \
         patch('code_improvement_agent.auto_fix.logger') as mock_logger:
        
        result = apply_patches(sample_patches, "/repo")
        
        assert result == []
        mock_logger.warning.assert_called_with("File not found: /repo/test.py")


def test_apply_patches_original_not_found(sample_patches):
    with patch('pathlib.Path.exists', return_value=True), \
         patch('pathlib.Path.read_text', return_value="different_code = 'content'"), \
         patch('code_improvement_agent.auto_fix.logger') as mock_logger:
        
        result = apply_patches(sample_patches, "/repo")
        
        assert result == []
        mock_logger.warning.assert_called_with("Original text not found in test.py — skipping")


def test_apply_patches_multiple_occurrences(sample_patches):
    content_with_duplicates = "old_code = 'vulnerable'\nold_code = 'vulnerable'"
    
    with patch('pathlib.Path.exists', return_value=True), \
         patch('pathlib.Path.read_text', return_value=content_with_duplicates), \
         patch('code_improvement_agent.auto_fix.logger') as mock_logger:
        
        result = apply_patches(sample_patches, "/repo")
        
        assert result == []
        mock_logger.warning.assert_called_with("Original text appears 2 times in test.py — skipping for safety")


def test_apply_patches_handles_unicode_errors():
    patches = [{
        "file": "test.py",
        "finding": "Test",
        "original": "old",
        "fixed": "new",
        "explanation": "fix"
    }]
    
    with patch('pathlib.Path.exists', return_value=True), \
         patch('pathlib.Path.read_text', return_value="old code"), \
         patch('pathlib.Path.write_text') as mock_write:
        
        apply_patches(patches, "/repo", dry_run=False)
        
        # Verify encoding parameters are used
        mock_write.assert_called_with("new code", encoding="utf-8")


def test_format_patches_report_empty_patches():
    result = format_patches_report([])
    
    assert "## Auto-Fix Patches" in result
    assert "No patches generated." in result


def test_format_patches_report_single_patch():
    patches = [{
        "file": "test.py",
        "finding": "SQL Injection",
        "original": "old_code = 'bad'",
        "fixed": "new_code = 'good'",
        "explanation": "Fixed the vulnerability",
        "status": "applied"
    }]
    
    result = format_patches_report(patches)
    
    assert "## Auto-Fix Patches" in result
    assert "**1 patches generated**" in result
    assert "### Patch 1: SQL Injection" in result
    assert "**File:** `test.py` | **Status:** done" in result
    assert "Fixed the vulnerability" in result
    assert "```diff" in result
    assert "- old_code = 'bad'" in result
    assert "+ new_code = 'good'" in result


def test_format_patches_report_multiple_patches():
    patches = [
        {
            "file": "test1.py",
            "finding": "Issue 1",
            "original": "old1",
            "fixed": "new1",
            "explanation": "Fix 1",
            "status": "would_apply"
        },
        {
            "file": "test2.py",
            "finding": "Issue 2",
            "original": "old2",
            "fixed": "new2",
            "explanation": "Fix 2",
            "status": "generated"
        }
    ]
    
    result = format_patches_report(patches)
    
    assert "**2 patches generated**" in result
    assert "### Patch 1: Issue 1" in result
    assert "### Patch 2: Issue 2" in result
    assert "**Status:** ready" in result  # would_apply -> ready
    assert "**Status:** pending" in result  # generated -> pending


def test_format_patches_report_multiline_code():
    patches = [{
        "file": "test.py",
        "finding": "Multi-line Fix",
        "original": "line1\nline2\nline3",
        "fixed": "fixed1\nfixed2",
        "explanation": "Refactored code"
    }]
    
    result = format_patches_report(patches)
    
    assert "- line1" in result
    assert "- line2" in result
    assert "- line3" in result
    assert "+ fixed1" in result
    assert "+ fixed2" in result


def test_format_patches_report_missing_optional_fields():
    patches = [{
        "file": "test.py",
        "finding": "Basic Fix",
        "original": "old",
        "fixed": "new"
        # Missing explanation and status
    }]
    
    result = format_patches_report(patches)
    
    assert "### Patch 1: Basic Fix" in result
    assert "**Status:** ?" in result  # unknown status
    # Should handle missing explanation gracefully
