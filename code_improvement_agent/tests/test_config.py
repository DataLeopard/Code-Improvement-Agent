import pytest
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock
import warnings

from code_improvement_agent.config import Config, load_config


@pytest.fixture
def sample_yaml_data():
    return {
        "scoring": {"weight": 1.0},
        "clarity": {"max_function_lines": 50},
        "functionality": {"require_tests": True},
        "structure": {"max_depth": 5},
        "reusability": {"min_abstraction": 3},
        "security": {"check_hardcoded_secrets": True},
        "tags": {"priority": "high"}
    }


@pytest.fixture
def config_with_data(sample_yaml_data):
    return Config(sample_yaml_data)


@pytest.fixture
def empty_config():
    return Config(None)


class TestConfig:
    def test_scoring_returns_scoring_section(self, config_with_data):
        result = config_with_data.scoring()
        assert result == {"weight": 1.0}

    def test_scoring_returns_empty_dict_when_missing(self, empty_config):
        result = empty_config.scoring()
        assert result == {}

    def test_clarity_returns_clarity_section(self, config_with_data):
        result = config_with_data.clarity()
        assert result == {"max_function_lines": 50}

    def test_clarity_returns_empty_dict_when_missing(self, empty_config):
        result = empty_config.clarity()
        assert result == {}

    def test_functionality_returns_functionality_section(self, config_with_data):
        result = config_with_data.functionality()
        assert result == {"require_tests": True}

    def test_functionality_returns_empty_dict_when_missing(self, empty_config):
        result = empty_config.functionality()
        assert result == {}

    def test_structure_returns_structure_section(self, config_with_data):
        result = config_with_data.structure()
        assert result == {"max_depth": 5}

    def test_structure_returns_empty_dict_when_missing(self, empty_config):
        result = empty_config.structure()
        assert result == {}

    def test_reusability_returns_reusability_section(self, config_with_data):
        result = config_with_data.reusability()
        assert result == {"min_abstraction": 3}

    def test_reusability_returns_empty_dict_when_missing(self, empty_config):
        result = empty_config.reusability()
        assert result == {}

    def test_security_returns_security_section(self, config_with_data):
        result = config_with_data.security()
        assert result == {"check_hardcoded_secrets": True}

    def test_security_returns_empty_dict_when_missing(self, empty_config):
        result = empty_config.security()
        assert result == {}

    def test_tags_returns_tags_section(self, config_with_data):
        result = config_with_data.tags()
        assert result == {"priority": "high"}

    def test_tags_returns_empty_dict_when_missing(self, empty_config):
        result = empty_config.tags()
        assert result == {}

    def test_get_returns_nested_value(self, config_with_data):
        result = config_with_data.get("clarity", "max_function_lines")
        assert result == 50

    def test_get_returns_default_when_section_missing(self, config_with_data):
        result = config_with_data.get("missing_section", "key", "default_value")
        assert result == "default_value"

    def test_get_returns_default_when_key_missing(self, config_with_data):
        result = config_with_data.get("clarity", "missing_key", "default_value")
        assert result == "default_value"

    def test_get_returns_none_when_no_default(self, config_with_data):
        result = config_with_data.get("missing_section", "missing_key")
        assert result is None


class TestLoadConfig:
    @patch("code_improvement_agent.config.Path")
    @patch("builtins.open", new_callable=mock_open, read_data="scoring:\n  weight: 2.0")
    @patch("code_improvement_agent.config.yaml")
    def test_load_config_uses_explicit_config_path(self, mock_yaml, mock_file, mock_path):
        mock_yaml.safe_load.return_value = {"scoring": {"weight": 2.0}}
        mock_path_instance = MagicMock()
        mock_path_instance.is_file.return_value = True
        mock_path.return_value = mock_path_instance

        result = load_config(config_path="/explicit/config.yaml")
        
        mock_path.assert_called_with("/explicit/config.yaml")
        assert isinstance(result, Config)

    @patch("code_improvement_agent.config.Path")
    @patch("builtins.open", new_callable=mock_open, read_data="scoring:\n  weight: 2.0")
    @patch("code_improvement_agent.config.yaml")
    def test_load_config_uses_repo_path_when_explicit_missing(self, mock_yaml, mock_file, mock_path):
        mock_yaml.safe_load.return_value = {"scoring": {"weight": 2.0}}
        
        # Mock Path objects for search order
        explicit_path = MagicMock()
        explicit_path.is_file.return_value = False
        repo_path = MagicMock()
        repo_path.is_file.return_value = True
        
        mock_path.side_effect = [explicit_path, repo_path, MagicMock()]

        result = load_config(repo_path="/repo", config_path="/missing/config.yaml")
        
        assert isinstance(result, Config)

    @patch("code_improvement_agent.config.Path")
    def test_load_config_uses_defaults_when_no_files_found(self, mock_path):
        mock_path_instance = MagicMock()
        mock_path_instance.is_file.return_value = False
        mock_path.return_value = mock_path_instance

        result = load_config()
        
        assert isinstance(result, Config)

    @patch("code_improvement_agent.config.Path")
    @patch("builtins.open", new_callable=mock_open, read_data="scoring:\n  weight: 2.0")
    @patch("code_improvement_agent.config.yaml")
    def test_load_config_searches_cwd_when_others_missing(self, mock_yaml, mock_file, mock_path):
        mock_yaml.safe_load.return_value = {"scoring": {"weight": 2.0}}
        
        # Mock search paths - only CWD path exists
        repo_path = MagicMock()
        repo_path.is_file.return_value = False
        cwd_path = MagicMock()
        cwd_path.is_file.return_value = True
        
        mock_path.side_effect = [repo_path, cwd_path]

        result = load_config(repo_path="/repo")
        
        assert isinstance(result, Config)

    @patch("code_improvement_agent.config.Path")
    @patch("builtins.open", side_effect=OSError("File not readable"))
    def test_load_config_handles_file_read_error(self, mock_file, mock_path):
        mock_path_instance = MagicMock()
        mock_path_instance.is_file.return_value = True
        mock_path.return_value = mock_path_instance

        # Should not raise exception, should use defaults
        result = load_config()
        
        assert isinstance(result, Config)

    @patch("code_improvement_agent.config.Path")
    @patch("builtins.open", new_callable=mock_open, read_data="scoring:\n  weight: 2.0")
    def test_load_config_warns_when_yaml_not_available(self, mock_file, mock_path):
        mock_path_instance = MagicMock()
        mock_path_instance.is_file.return_value = True
        mock_path.return_value = mock_path_instance

        # Simulate ImportError for yaml
        with patch("code_improvement_agent.config.yaml", side_effect=ImportError):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                result = load_config()
                
                assert len(w) == 1
                assert "PyYAML is not installed" in str(w[0].message)
                assert isinstance(result, Config)

    @patch("code_improvement_agent.config.Path")
    @patch("builtins.open", new_callable=mock_open, read_data="invalid: yaml: content:")
    @patch("code_improvement_agent.config.yaml")
    def test_load_config_handles_invalid_yaml(self, mock_yaml, mock_file, mock_path):
        mock_yaml.safe_load.side_effect = Exception("Invalid YAML")
        mock_path_instance = MagicMock()
        mock_path_instance.is_file.return_value = True
        mock_path.return_value = mock_path_instance

        # Should not raise exception, should use defaults
        result = load_config()
        
        assert isinstance(result, Config)
