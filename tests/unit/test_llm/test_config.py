"""Tests for LLM configuration management."""

import os
import pytest
from unittest.mock import patch

from flowgenius.llm.config import LLMConfig


class TestLLMConfig:
    """Tests for LLMConfig class."""

    def test_default_config(self):
        """Test default configuration values."""
        config = LLMConfig()

        assert config.provider == "openai"
        assert config.model == "gpt-4"
        assert config.temperature == 0.3
        assert config.max_tokens == 2000
        assert config.timeout == 30
        assert config.enable_assertion_analysis is True
        assert config.enable_code_generation is True
        assert config.enable_correlation_analysis is True
        assert config.fallback_to_rules is True

    def test_custom_config(self):
        """Test custom configuration values."""
        config = LLMConfig(
            provider="anthropic",
            api_key="test-key",
            model="claude-3-opus",
            temperature=0.5,
            max_tokens=4000,
        )

        assert config.provider == "anthropic"
        assert config.api_key == "test-key"
        assert config.model == "claude-3-opus"
        assert config.temperature == 0.5
        assert config.max_tokens == 4000

    def test_invalid_temperature(self):
        """Test that invalid temperature raises error."""
        with pytest.raises(ValueError, match="Temperature must be between 0 and 2"):
            LLMConfig(temperature=3.0)

        with pytest.raises(ValueError, match="Temperature must be between 0 and 2"):
            LLMConfig(temperature=-0.5)

    def test_invalid_max_tokens(self):
        """Test that invalid max_tokens raises error."""
        with pytest.raises(ValueError, match="max_tokens must be at least 1"):
            LLMConfig(max_tokens=0)

    def test_invalid_timeout(self):
        """Test that invalid timeout raises error."""
        with pytest.raises(ValueError, match="timeout must be at least 1 second"):
            LLMConfig(timeout=0)

    def test_from_env(self):
        """Test loading configuration from environment variables."""
        env_vars = {
            "LLM_PROVIDER": "anthropic",
            "ANTHROPIC_API_KEY": "anthropic-key",
            "LLM_MODEL": "claude-3-opus",
            "LLM_TEMPERATURE": "0.7",
            "LLM_MAX_TOKENS": "3000",
            "LLM_TIMEOUT": "60",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            config = LLMConfig.from_env()

        assert config.provider == "anthropic"
        assert config.api_key == "anthropic-key"
        assert config.model == "claude-3-opus"
        assert config.temperature == 0.7
        assert config.max_tokens == 3000
        assert config.timeout == 60

    def test_from_env_openai(self):
        """Test loading OpenAI configuration from environment."""
        env_vars = {
            "LLM_PROVIDER": "openai",
            "OPENAI_API_KEY": "openai-key",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            config = LLMConfig.from_env()

        assert config.provider == "openai"
        assert config.api_key == "openai-key"

    def test_validate(self):
        """Test configuration validation."""
        config = LLMConfig(api_key="test-key")
        assert config.validate() is True

        config_no_key = LLMConfig()
        with pytest.raises(ValueError, match="API key is required"):
            config_no_key.validate()

    def test_to_dict(self):
        """Test converting configuration to dictionary."""
        config = LLMConfig(
            provider="openai",
            model="gpt-4",
            temperature=0.3,
        )

        result = config.to_dict()

        assert isinstance(result, dict)
        assert result["provider"] == "openai"
        assert result["model"] == "gpt-4"
        assert result["temperature"] == 0.3
        assert "enable_assertion_analysis" in result
        assert "fallback_to_rules" in result