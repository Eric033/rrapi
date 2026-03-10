"""Tests for LLM provider base classes."""

import json
import os
import pytest
from unittest.mock import MagicMock, patch

from flowgenius.llm.base import (
    LLMProvider,
    MockLLMProvider,
)


class TestMockLLMProvider:
    """Tests for MockLLMProvider class."""

    def test_generate_default_response(self):
        """Test generating with default response."""
        provider = MockLLMProvider()

        result = provider.generate("test prompt")

        assert result == "{}"

    def test_generate_with_pattern_response(self):
        """Test generating response based on pattern matching."""
        provider = MockLLMProvider(
            responses={
                "analyze": '{"result": "analysis"}',
                "generate": '{"code": "test"}',
            }
        )

        result1 = provider.generate("Please analyze this data")
        result2 = provider.generate("Generate some code")

        assert result1 == '{"result": "analysis"}'
        assert result2 == '{"code": "test"}'

    def test_generate_json(self):
        """Test generating JSON response."""
        provider = MockLLMProvider(
            default_response='{"key": "value"}'
        )

        result = provider.generate_json("test prompt")

        assert isinstance(result, dict)
        assert result["key"] == "value"

    def test_generate_json_invalid(self):
        """Test generating JSON with invalid response."""
        provider = MockLLMProvider(
            default_response="not valid json"
        )

        result = provider.generate_json("test prompt")

        assert "error" in result

    def test_set_response(self):
        """Test setting response dynamically."""
        provider = MockLLMProvider()

        provider.set_response("test", "test response")
        result = provider.generate("this is a test prompt")

        assert result == "test response"

    def test_call_history(self):
        """Test that calls are recorded in history."""
        provider = MockLLMProvider()

        provider.generate("prompt 1")
        provider.generate("prompt 2", temperature=0.5)

        assert len(provider.call_history) == 2
        assert provider.call_history[0]["prompt"] == "prompt 1"
        assert provider.call_history[1]["kwargs"]["temperature"] == 0.5

    def test_reset_history(self):
        """Test resetting call history."""
        provider = MockLLMProvider()

        provider.generate("prompt")
        assert len(provider.call_history) == 1

        provider.reset_history()
        assert len(provider.call_history) == 0

    def test_generate_with_retry_success(self):
        """Test generate_with_retry on success."""
        provider = MockLLMProvider()

        result = provider.generate_with_retry("test")

        assert result == "{}"

    def test_generate_with_retry_failure(self):
        """Test generate_with_retry on failure."""
        provider = MockLLMProvider()
        provider.generate = MagicMock(side_effect=Exception("API Error"))

        with pytest.raises(Exception, match="API Error"):
            provider.generate_with_retry("test", retry_count=2, retry_delay=0.1)


class TestOpenAIProvider:
    """Tests for OpenAIProvider class."""

    def test_init_with_api_key(self):
        """Test initialization with API key."""
        from flowgenius.llm.base import OpenAIProvider

        provider = OpenAIProvider(api_key="test-key")

        assert provider.config.api_key == "test-key"

    def test_generate_mock(self):
        """Test generate method with mocked client."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Generated text"
        mock_client.chat.completions.create.return_value = mock_response

        from flowgenius.llm.base import OpenAIProvider

        provider = OpenAIProvider(api_key="test-key")
        provider._client = mock_client  # Inject mock client

        result = provider.generate("test prompt")

        assert result == "Generated text"
        mock_client.chat.completions.create.assert_called_once()

    def test_generate_json_mock(self):
        """Test generate_json method with mocked client."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{"result": "success"}'
        mock_client.chat.completions.create.return_value = mock_response

        from flowgenius.llm.base import OpenAIProvider

        provider = OpenAIProvider(api_key="test-key")
        provider._client = mock_client  # Inject mock client

        result = provider.generate_json("test prompt")

        assert result == {"result": "success"}

    def test_import_error(self):
        """Test that ImportError is raised when openai is not installed."""
        from flowgenius.llm.base import OpenAIProvider

        provider = OpenAIProvider(api_key="test-key")
        provider._client = None  # Reset client

        # Mock the import to raise ImportError
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "openai":
                raise ImportError("openai not installed")
            return real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=mock_import):
            with pytest.raises(ImportError, match="'openai' package is required"):
                provider._get_client()


class TestAnthropicProvider:
    """Tests for AnthropicProvider class."""

    def test_generate_mock(self):
        """Test generate method with mocked client."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = "Generated text"
        mock_client.messages.create.return_value = mock_response

        from flowgenius.llm.base import AnthropicProvider

        provider = AnthropicProvider(api_key="test-key")
        provider._client = mock_client  # Inject mock client

        result = provider.generate("test prompt")

        assert result == "Generated text"

    def test_generate_json_with_markdown(self):
        """Test generate_json extracts JSON from markdown."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = '```json\n{"key": "value"}\n```'
        mock_client.messages.create.return_value = mock_response

        from flowgenius.llm.base import AnthropicProvider

        provider = AnthropicProvider(api_key="test-key")
        provider._client = mock_client  # Inject mock client

        result = provider.generate_json("test prompt")

        assert result == {"key": "value"}


class TestZhipuProvider:
    """Tests for ZhipuProvider class."""

    def test_init_with_api_key(self):
        """Test initialization with API key."""
        from flowgenius.llm.base import ZhipuProvider

        provider = ZhipuProvider(api_key="test-key")

        assert provider.config.api_key == "test-key"
        assert provider.config.model == "glm-4-flash"  # Default for zhipu

    def test_init_with_env_var(self):
        """Test initialization with ZHIPU_API_KEY environment variable."""
        from flowgenius.llm.base import ZhipuProvider

        # Temporarily set environment variable
        os.environ["ZHIPU_API_KEY"] = "env-test-key"

        try:
            provider = ZhipuProvider()
            assert provider.config.api_key == "env-test-key"
        finally:
            # Clean up environment variable
            del os.environ["ZHIPU_API_KEY"]

    def test_generate_mock(self):
        """Test generate method with mocked client."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Generated text from Zhipu"
        mock_client.chat.completions.create.return_value = mock_response

        from flowgenius.llm.base import ZhipuProvider

        provider = ZhipuProvider(api_key="test-key")
        provider._client = mock_client  # Inject mock client

        result = provider.generate("test prompt")

        assert result == "Generated text from Zhipu"
        mock_client.chat.completions.create.assert_called_once()
        # Verify the call was made with correct parameters
        call_args = mock_client.chat.completions.create.call_args
        assert call_args[1]['model'] == 'glm-4-flash'  # Default model for Zhipu

    def test_generate_json_mock(self):
        """Test generate_json method with mocked client."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{"result": "zhipu-success"}'
        mock_client.chat.completions.create.return_value = mock_response

        from flowgenius.llm.base import ZhipuProvider

        provider = ZhipuProvider(api_key="test-key")
        provider._client = mock_client  # Inject mock client

        result = provider.generate_json("test prompt")

        assert result == {"result": "zhipu-success"}

    def test_no_api_key_error(self):
        """Test that ValueError is raised when no API key is provided."""
        from flowgenius.llm.base import ZhipuProvider

        # Ensure no ZHIPU_API_KEY is set
        if "ZHIPU_API_KEY" in os.environ:
            del os.environ["ZHIPU_API_KEY"]

        provider = ZhipuProvider()
        provider._client = None  # Reset client to force error

        with pytest.raises(ValueError, match="Zhipu API key is required"):
            provider._get_client()

    def test_import_error(self):
        """Test that ImportError is raised when openai is not installed."""
        from flowgenius.llm.base import ZhipuProvider

        provider = ZhipuProvider(api_key="test-key")
        provider._client = None  # Reset client

        # Mock the import to raise ImportError
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "openai":
                raise ImportError("openai not installed")
            return real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=mock_import):
            with pytest.raises(ImportError, match="'openai' package is required"):
                provider._get_client()