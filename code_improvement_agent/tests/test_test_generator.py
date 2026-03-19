import pytest
from unittest.mock import patch, Mock, mock_open
from pathlib import Path
from code_improvement_agent.test_generator import generate_tests, format_test_report


class TestGenerateTests:
    @pytest.fixture
    def sample_file_contents(self):
        return {
            "utils.py": '''def public_function():
    """A public function."""
    return "hello"

def _private_function():
    """A private function."""
    return "private"

class MyClass:
    def public_method(self):
        """A public method."""
        return "method"
''',
            "main.py": '''def main():
    """Main function."""
    print("Hello world")
''',
            "config.json": '{"key": "value"}'
        }

    @pytest.fixture
    def mock_collect_functions(self):
        return [
            {
                "name": "public_function",
                "class": None,
                "line": 1,
                "source": "def public_function():\n    return 'hello'"
            },
            {
                "name": "public_method",
                "class": "MyClass",
                "line": 8,
                "source": "def public_method(self):\n    return 'method'"
            }
        ]

    @pytest.fixture
    def mock_claude_response(self):
        return '''import pytest
from utils import public_function

def test_public_function_returns_hello():
    result = public_function()
    assert result == "hello"
'''

    def test_generate_tests_filters_non_python_files(self, sample_file_contents):
        with patch('code_improvement_agent.test_generator._collect_functions') as mock_collect, \
             patch('code_improvement_agent.test_generator.call_claude') as mock_claude:
            mock_collect.return_value = []
            
            result = generate_tests(sample_file_contents, "/repo")
            
            # Should only call _collect_functions for .py files
            assert mock_collect.call_count == 2
            mock_collect.assert_any_call("utils.py", sample_file_contents["utils.py"])
            mock_collect.assert_any_call("main.py", sample_file_contents["main.py"])

    def test_generate_tests_no_functions_found(self):
        file_contents = {"empty.py": "# No functions"}
        
        with patch('code_improvement_agent.test_generator._collect_functions', return_value=[]):
            result = generate_tests(file_contents, "/repo")
            
            assert result == {
                "tests_generated": 0,
                "files_created": [],
                "test_code": {}
            }

    @patch('code_improvement_agent.test_generator.logger')
    def test_generate_tests_no_functions_logs_info(self, mock_logger):
        file_contents = {"empty.py": "# No functions"}
        
        with patch('code_improvement_agent.test_generator._collect_functions', return_value=[]):
            generate_tests(file_contents, "/repo")
            
            mock_logger.info.assert_called_with("No public Python functions found to test")

    def test_generate_tests_successful_generation(self, sample_file_contents, mock_collect_functions, mock_claude_response):
        with patch('code_improvement_agent.test_generator._collect_functions', return_value=mock_collect_functions), \
             patch('code_improvement_agent.test_generator.call_claude', return_value=mock_claude_response), \
             patch('code_improvement_agent.test_generator._test_path_for', return_value="test_utils.py"):
            
            result = generate_tests(sample_file_contents, "/repo")
            
            assert result["tests_generated"] == 1  # One "def test_" found
            assert result["files_created"] == []  # write=False
            assert "test_utils.py" in result["test_code"]
            assert result["test_code"]["test_utils.py"] == mock_claude_response

    def test_generate_tests_creates_correct_prompt(self, mock_collect_functions):
        file_contents = {"utils.py": "def func(): pass"}
        
        with patch('code_improvement_agent.test_generator._collect_functions', return_value=mock_collect_functions), \
             patch('code_improvement_agent.test_generator.call_claude') as mock_claude, \
             patch('code_improvement_agent.test_generator._test_path_for', return_value="test_utils.py"):
            
            generate_tests(file_contents, "/repo")
            
            prompt = mock_claude.call_args[0][0]
            assert "utils.py" in prompt
            assert "public_function()" in prompt
            assert "MyClass.public_method()" in prompt
            assert "line 1" in prompt
            assert "line 8" in prompt
            assert "from utils" in prompt

    def test_generate_tests_handles_claude_code_blocks(self, mock_collect_functions):
        file_contents = {"utils.py": "def func(): pass"}
        claude_response = "```python\nimport pytest\n\ndef test_func():\n    pass\n```"
        
        with patch('code_improvement_agent.test_generator._collect_functions', return_value=mock_collect_functions), \
             patch('code_improvement_agent.test_generator.call_claude', return_value=claude_response), \
             patch('code_improvement_agent.test_generator._test_path_for', return_value="test_utils.py"):
            
            result = generate_tests(file_contents, "/repo")
            
            expected_code = "import pytest\n\ndef test_func():\n    pass"
            assert result["test_code"]["test_utils.py"] == expected_code

    def test_generate_tests_counts_async_tests(self, mock_collect_functions):
        file_contents = {"utils.py": "def func(): pass"}
        claude_response = "async def test_async():\n    pass\n\ndef test_sync():\n    pass"
        
        with patch('code_improvement_agent.test_generator._collect_functions', return_value=mock_collect_functions), \
             patch('code_improvement_agent.test_generator.call_claude', return_value=claude_response), \
             patch('code_improvement_agent.test_generator._test_path_for', return_value="test_utils.py"):
            
            result = generate_tests(file_contents, "/repo")
            
            assert result["tests_generated"] == 2

    def test_generate_tests_writes_files_when_enabled(self, mock_collect_functions, mock_claude_response, tmp_path):
        file_contents = {"utils.py": "def func(): pass"}
        
        with patch('code_improvement_agent.test_generator._collect_functions', return_value=mock_collect_functions), \
             patch('code_improvement_agent.test_generator.call_claude', return_value=mock_claude_response), \
             patch('code_improvement_agent.test_generator._test_path_for', return_value="test_utils.py"):
            
            result = generate_tests(file_contents, str(tmp_path), write=True)
            
            assert result["files_created"] == ["test_utils.py"]
            test_file = tmp_path / "test_utils.py"
            assert test_file.exists()
            assert test_file.read_text() == mock_claude_response

    def test_generate_tests_creates_parent_directories(self, mock_collect_functions, mock_claude_response, tmp_path):
        file_contents = {"utils.py": "def func(): pass"}
        
        with patch('code_improvement_agent.test_generator._collect_functions', return_value=mock_collect_functions), \
             patch('code_improvement_agent.test_generator.call_claude', return_value=mock_claude_response), \
             patch('code_improvement_agent.test_generator._test_path_for', return_value="tests/unit/test_utils.py"):
            
            generate_tests(file_contents, str(tmp_path), write=True)
            
            test_file = tmp_path / "tests" / "unit" / "test_utils.py"
            assert test_file.exists()
            assert test_file.read_text() == mock_claude_response

    @patch('code_improvement_agent.test_generator.logger')
    def test_generate_tests_handles_claude_exception(self, mock_logger, mock_collect_functions):
        file_contents = {"utils.py": "def func(): pass"}
        
        with patch('code_improvement_agent.test_generator._collect_functions', return_value=mock_collect_functions), \
             patch('code_improvement_agent.test_generator.call_claude', side_effect=Exception("API error")), \
             patch('code_improvement_agent.test_generator._test_path_for', return_value="test_utils.py"):
            
            result = generate_tests(file_contents, "/repo")
            
            assert result["tests_generated"] == 0
            assert result["test_code"] == {}
            mock_logger.warning.assert_called_with("Test generation failed for utils.py: API error")

    def test_generate_tests_handles_windows_paths(self, mock_collect_functions, mock_claude_response):
        file_contents = {"src\\utils.py": "def func(): pass"}
        
        with patch('code_improvement_agent.test_generator._collect_functions', return_value=mock_collect_functions), \
             patch('code_improvement_agent.test_generator.call_claude', return_value=mock_claude_response) as mock_claude, \
             patch('code_improvement_agent.test_generator._test_path_for', return_value="test_utils.py"):
            
            generate_tests(file_contents, "/repo")
            
            prompt = mock_claude.call_args[0][0]
            assert "from src.utils" in prompt

    def test_generate_tests_multiple_files(self):
        file_contents = {
            "utils.py": "def func1(): pass",
            "helpers.py": "def func2(): pass"
        }
        mock_funcs = [{"name": "func", "class": None, "line": 1, "source": "def func(): pass"}]
        
        with patch('code_improvement_agent.test_generator._collect_functions', return_value=mock_funcs), \
             patch('code_improvement_agent.test_generator.call_claude', return_value="def test_func(): pass"), \
             patch('code_improvement_agent.test_generator._test_path_for', side_effect=lambda f: f"test_{f}"):
            
            result = generate_tests(file_contents, "/repo")
            
            assert result["tests_generated"] == 2
            assert len(result["test_code"]) == 2
            assert "test_utils.py" in result["test_code"]
            assert "test_helpers.py" in result["test_code"]


class TestFormatTestReport:
    def test_format_test_report_no_tests(self):
        result = {
            "tests_generated": 0,
            "files_created": [],
            "test_code": {}
        }
        
        report = format_test_report(result)
        
        assert report == "## Generated Tests\n\nNo tests generated."

    def test_format_test_report_with_tests_no_files_written(self):
        result = {
            "tests_generated": 3,
            "files_created": [],
            "test_code": {
                "test_utils.py": "def test_func():\n    pass",
                "test_helpers.py": "def test_other():\n    pass"
            }
        }
        
        report = format_test_report(result)
        
        assert "## Generated Tests" in report
        assert "**3 tests** generated across **2 files**" in report
        assert "### Files Written" not in report
        assert "### `test_utils.py`" in report
        assert "### `test_helpers.py`" in report
        assert "```python\ndef test_func():\n    pass\n```" in report

    def test_format_test_report_with_files_written(self):
        result = {
            "tests_generated": 2,
            "files_created": ["test_utils.py", "test_helpers.py"],
            "test_code": {
                "test_utils.py": "def test_func():\n    pass"
            }
        }
        
        report = format_test_report(result)
        
        assert "### Files Written" in report
        assert "- `test_utils.py`" in report
        assert "- `test_helpers.py`" in report

    def test_format_test_report_markdown_structure(self):
        result = {
            "tests_generated": 1,
            "files_created": [],
            "test_code": {
                "test_example.py": "import pytest\n\ndef test_example():\n    assert True"
            }
        }
        
        report = format_test_report(result)
        
        lines = report.split("\n")
        assert lines[0] == "## Generated Tests"
        assert lines[1] == ""
        assert "**1 tests**" in lines[2]
        assert lines[4] == "### `test_example.py`"
        assert lines[5] == "```python"
        assert lines[8] == "```"

    def test_format_test_report_preserves_code_formatting(self):
        code = '''import pytest
from mymodule import func

class TestFunc:
    def test_func_basic(self):
        assert func() == "expected"
        
    def test_func_with_args(self):
        assert func("arg") == "result"'''
        
        result = {
            "tests_generated": 2,
            "files_created": [],
            "test_code": {"test_mymodule.py": code}
        }
        
        report = format_test_report(result)
        
        assert f"```python\n{code}\n```" in report
