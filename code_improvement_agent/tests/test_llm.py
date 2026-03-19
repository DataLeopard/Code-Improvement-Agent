import os
import pytest
from unittest.mock import Mock, patch, MagicMock
import time

from code_improvement_agent.llm import get_client, call_claude, estimate_cost


class TestGetClient:
    def test_get_client_with_valid_api_key(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test-key"}):
            with patch("anthropic.Anthropic") as mock_anthropic:
                mock_client = Mock()
                mock_anthropic.return_value = mock_client
                
                client = get_client()
                
                mock_anthropic.assert_called_once_with(api_key="sk-ant-test-key")
                assert client == mock_client

    def test_get_client_no_api_key_raises_error(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                get_client()
            
            error_msg = str(exc_info.value)
            assert "ANTHROPIC_API_KEY not set" in error_msg
            assert "Set env var" in error_msg
            assert "Create a .env file" in error_msg

    def test_get_client_empty_api_key_raises_error(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
            with pytest.raises(ValueError) as exc_info:
                get_client()
            
            assert "ANTHROPIC_API_KEY not set" in str(exc_info.value)


class TestCallClaude:
    @pytest.fixture
    def mock_client(self):
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text="Test response")]
        mock_client.messages.create.return_value = mock_response
        return mock_client

    def test_call_claude_success_with_defaults(self, mock_client):
        with patch("code_improvement_agent.llm.get_client", return_value=mock_client):
            result = call_claude("Test prompt")
            
            assert result == "Test response"
            mock_client.messages.create.assert_called_once_with(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system="You are an expert code reviewer.",
                messages=[{"role": "user", "content": "Test prompt"}]
            )

    def test_call_claude_with_custom_parameters(self, mock_client):
        with patch("code_improvement_agent.llm.get_client", return_value=mock_client):
            result = call_claude(
                prompt="Custom prompt",
                system="Custom system",
                max_tokens=2000,
                model="claude-opus-3"
            )
            
            assert result == "Test response"
            mock_client.messages.create.assert_called_once_with(
                model="claude-opus-3",
                max_tokens=2000,
                system="Custom system",
                messages=[{"role": "user", "content": "Custom prompt"}]
            )

    def test_call_claude_with_empty_system_uses_default(self, mock_client):
        with patch("code_improvement_agent.llm.get_client", return_value=mock_client):
            call_claude("Test prompt", system="")
            
            mock_client.messages.create.assert_called_once_with(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system="You are an expert code reviewer.",
                messages=[{"role": "user", "content": "Test prompt"}]
            )

    def test_call_claude_rate_limit_retry_success(self, mock_client):
        rate_limit_error = Exception("Rate limit exceeded (429)")
        mock_client.messages.create.side_effect = [
            rate_limit_error,
            rate_limit_error,
            Mock(content=[Mock(text="Success after retries")])
        ]
        
        with patch("code_improvement_agent.llm.get_client", return_value=mock_client):
            with patch("time.sleep") as mock_sleep:
                result = call_claude("Test prompt")
                
                assert result == "Success after retries"
                assert mock_client.messages.create.call_count == 3
                assert mock_sleep.call_count == 2
                mock_sleep.assert_any_call(5)  # 2^0 * 5
                mock_sleep.assert_any_call(10)  # 2^1 * 5

    def test_call_claude_rate_limit_max_retries_exceeded(self, mock_client):
        rate_limit_error = Exception("rate_limit error")
        mock_client.messages.create.side_effect = rate_limit_error
        
        with patch("code_improvement_agent.llm.get_client", return_value=mock_client):
            with patch("time.sleep"):
                with pytest.raises(RuntimeError) as exc_info:
                    call_claude("Test prompt")
                
                assert "Failed after 3 retries due to rate limiting" in str(exc_info.value)
                assert mock_client.messages.create.call_count == 3

    def test_call_claude_non_rate_limit_error_no_retry(self, mock_client):
        non_rate_limit_error = Exception("Different error")
        mock_client.messages.create.side_effect = non_rate_limit_error
        
        with patch("code_improvement_agent.llm.get_client", return_value=mock_client):
            with pytest.raises(Exception) as exc_info:
                call_claude("Test prompt")
            
            assert str(exc_info.value) == "Different error"
            assert mock_client.messages.create.call_count == 1

    def test_call_claude_429_status_code_retry(self, mock_client):
        error_429 = Exception("HTTP 429 error")
        mock_client.messages.create.side_effect = [
            error_429,
            Mock(content=[Mock(text="Success")])
        ]
        
        with patch("code_improvement_agent.llm.get_client", return_value=mock_client):
            with patch("time.sleep") as mock_sleep:
                result = call_claude("Test prompt")
                
                assert result == "Success"
                assert mock_client.messages.create.call_count == 2
                mock_sleep.assert_called_once_with(5)


class TestEstimateCost:
    def test_estimate_cost_smart_mode_default(self):
        file_contents = {
            "file1.py": "a" * 1000,
            "file2.py": "b" * 2000
        }
        
        result = estimate_cost(file_contents)
        
        expected_input_tokens = 3000 // 4 // 4  # total_chars / 4 / 4 for smart mode
        expected_output_tokens = 2000
        expected_cost = (expected_input_tokens * 3 + expected_output_tokens * 15) / 1_000_000
        
        assert result["input_tokens"] == expected_input_tokens
        assert result["output_tokens"] == expected_output_tokens
        assert result["estimated_cost_usd"] == round(expected_cost, 4)
        assert result["file_count"] == 2

    def test_estimate_cost_smart_mode_explicit(self):
        file_contents = {"test.py": "x" * 4000}
        
        result = estimate_cost(file_contents, mode="smart")
        
        expected_input_tokens = 4000 // 4 // 4  # 250 tokens
        expected_output_tokens = 2000
        expected_cost = (250 * 3 + 2000 * 15) / 1_000_000
        
        assert result["input_tokens"] == 250
        assert result["output_tokens"] == 2000
        assert result["estimated_cost_usd"] == round(expected_cost, 4)
        assert result["file_count"] == 1

    def test_estimate_cost_auto_fix_mode(self):
        file_contents = {"test.py": "x" * 8000}
        
        result = estimate_cost(file_contents, mode="auto-fix")
        
        expected_input_tokens = 8000 // 4  # 2000 tokens
        expected_output_tokens = expected_input_tokens // 2  # 1000 tokens
        expected_cost = (2000 * 3 + 1000 * 15) / 1_000_000
        
        assert result["input_tokens"] == 2000
        assert result["output_tokens"] == 1000
        assert result["estimated_cost_usd"] == round(expected_cost, 4)
        assert result["file_count"] == 1

    def test_estimate_cost_empty_files(self):
        file_contents = {}
        
        result = estimate_cost(file_contents)
        
        assert result["input_tokens"] == 0
        assert result["output_tokens"] == 2000
        assert result["estimated_cost_usd"] == round(2000 * 15 / 1_000_000, 4)
        assert result["file_count"] == 0

    def test_estimate_cost_single_empty_file(self):
        file_contents = {"empty.py": ""}
        
        result = estimate_cost(file_contents)
        
        assert result["input_tokens"] == 0
        assert result["output_tokens"] == 2000
        assert result["file_count"] == 1

    def test_estimate_cost_multiple_files_mixed_sizes(self):
        file_contents = {
            "small.py": "x" * 100,
            "medium.py": "y" * 1000,
            "large.py": "z" * 10000
        }
        
        result = estimate_cost(file_contents, mode="auto-fix")
        
        total_chars = 100 + 1000 + 10000
        expected_input_tokens = total_chars // 4
        expected_output_tokens = expected_input_tokens // 2
        expected_cost = (expected_input_tokens * 3 + expected_output_tokens * 15) / 1_000_000
        
        assert result["input_tokens"] == expected_input_tokens
        assert result["output_tokens"] == expected_output_tokens
        assert result["estimated_cost_usd"] == round(expected_cost, 4)
        assert result["file_count"] == 3
