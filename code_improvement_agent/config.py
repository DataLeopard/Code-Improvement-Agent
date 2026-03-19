"""Configuration system — loads from .code-improve.yaml with sensible defaults."""

import os
from pathlib import Path
from dataclasses import dataclass, field


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base, returning a new dict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# Default configuration — all hardcoded values live here
DEFAULTS = {
    "scoring": {
        "weights": {
            "quality": 0.30,
            "structure": 0.25,
            "security": 0.25,
            "usefulness": 0.20,
        },
        "max_deduction_per_analyzer": 6.0,
    },
    "clarity": {
        "max_function_lines": 50,
        "nesting_threshold": 5,
        "magic_number_whitelist": [0, 1, 2, 100, 255],
        "magic_number_threshold": 10,
        "allowed_single_letter_vars": "ijkxynmfe_",
    },
    "functionality": {
        "todo_markers": ["TODO", "FIXME", "HACK", "XXX", "BUG"],
    },
    "structure": {
        "root_file_threshold": 5,
        "mixed_concern_threshold": 3,
    },
    "reusability": {
        "block_size": 3,
        "min_block_length": 30,
        "import_repetition_threshold": 3,
    },
    "security": {
        "ignore_test_files": False,
    },
    "tags": {
        "custom_keywords": {},
    },
}


class Config:
    """Configuration holder loaded from .code-improve.yaml with defaults."""

    def __init__(self, data: dict | None = None):
        self._data = _deep_merge(DEFAULTS, data or {})

    # --- Top-level section accessors ---

    @property
    def scoring(self) -> dict:
        return self._data["scoring"]

    @property
    def clarity(self) -> dict:
        return self._data["clarity"]

    @property
    def functionality(self) -> dict:
        return self._data["functionality"]

    @property
    def structure(self) -> dict:
        return self._data["structure"]

    @property
    def reusability(self) -> dict:
        return self._data["reusability"]

    @property
    def security(self) -> dict:
        return self._data["security"]

    @property
    def tags(self) -> dict:
        return self._data["tags"]

    def get(self, section: str, key: str, default=None):
        """Get a config value: config.get('clarity', 'max_function_lines')."""
        return self._data.get(section, {}).get(key, default)


def load_config(repo_path: str | None = None, config_path: str | None = None) -> Config:
    """Load configuration from .code-improve.yaml.

    Search order:
        1. Explicit config_path (--config flag)
        2. repo_path/.code-improve.yaml (repo being analyzed)
        3. CWD/.code-improve.yaml
        4. Built-in defaults
    """
    yaml_data = None
    config_file = ".code-improve.yaml"

    search_paths = []
    if config_path:
        search_paths.append(Path(config_path))
    if repo_path:
        search_paths.append(Path(repo_path) / config_file)
    search_paths.append(Path.cwd() / config_file)

    for path in search_paths:
        if path.is_file():
            try:
                import yaml
            except ImportError:
                import warnings
                warnings.warn(
                    f"Found {path} but PyYAML is not installed. "
                    "Install with: pip install pyyaml. Using defaults.",
                    stacklevel=2,
                )
                break

            with open(path, "r", encoding="utf-8") as f:
                yaml_data = yaml.safe_load(f)
            break

    return Config(yaml_data)
