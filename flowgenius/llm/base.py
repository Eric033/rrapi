"""
LLM provider base classes and implementations.
"""
import json
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from flowgenius.llm.config import LLMConfig
from flowgenius.utils.logger import get_logger


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    This class defines the interface that all LLM providers must implement.
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        """Initialize the LLM provider.

        Args:
            config: LLM configuration. If None, will load from environment.
        """
        self.config = config or LLMConfig.from_env()
        self.logger = get_logger(f"flowgenius.llm.{self.__class__.__name__}")

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text from a prompt.

        Args:
            prompt: The input prompt
            **kwargs: Additional provider-specific parameters

        Returns:
            Generated text
        """
        pass

    @abstractmethod
    def generate_json(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate a JSON response from a prompt.

        Args:
            prompt: The input prompt
            **kwargs: Additional provider-specific parameters

        Returns:
            Parsed JSON dictionary

        Raises:
            ValueError: If response cannot be parsed as JSON
        """
        pass

    def generate_with_retry(
        self,
        prompt: str,
        retry_count: Optional[int] = None,
        retry_delay: Optional[float] = None,
        **kwargs
    ) -> str:
        """Generate text with automatic retry on failure.

        Args:
            prompt: The input prompt
            retry_count: Number of retries (uses config default if None)
            retry_delay: Delay between retries (uses config default if None)
            **kwargs: Additional provider-specific parameters

        Returns:
            Generated text

        Raises:
            Exception: If all retries fail
        """
        retries = retry_count if retry_count is not None else self.config.retry_count
        delay = retry_delay if retry_delay is not None else self.config.retry_delay

        last_error = None
        for attempt in range(retries + 1):
            try:
                return self.generate(prompt, **kwargs)
            except Exception as e:
                last_error = e
                self.logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < retries:
                    time.sleep(delay)

        raise last_error


class OpenAIProvider(LLMProvider):
    """OpenAI API provider implementation."""

    def __init__(self, config: Optional[LLMConfig] = None, api_key: Optional[str] = None):
        """Initialize OpenAI provider.

        Args:
            config: LLM configuration
            api_key: OpenAI API key (overrides config)
        """
        super().__init__(config)

        # Override API key if provided directly
        if api_key:
            self.config.api_key = api_key

        self._client = None

    def _get_client(self):
        """Get or create the OpenAI client.

        Returns:
            OpenAI client instance

        Raises:
            ImportError: If openai package is not installed
        """
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self.config.api_key,
                    timeout=self.config.timeout,
                )
            except ImportError:
                raise ImportError(
                    "The 'openai' package is required for OpenAI provider.\n\n"
                    "Install it with:\n"
                    "  pip install openai\n\n"
                    "Or install FlowGenius with LLM support:\n"
                    "  pip install flowgenius-smartadapter[llm]\n"
                )
        return self._client

    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text using OpenAI API.

        Args:
            prompt: The input prompt
            **kwargs: Additional parameters (model, temperature, etc.)

        Returns:
            Generated text
        """
        client = self._get_client()

        # Merge config defaults with kwargs
        model = kwargs.get("model", self.config.model)
        temperature = kwargs.get("temperature", self.config.temperature)
        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)

        self.logger.debug(f"Generating with model={model}, temperature={temperature}")

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert API test engineer."},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return response.choices[0].message.content

    def generate_json(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate JSON response using OpenAI API.

        Args:
            prompt: The input prompt
            **kwargs: Additional parameters

        Returns:
            Parsed JSON dictionary
        """
        # Add JSON format instruction if not present
        json_prompt = prompt
        if "JSON" not in prompt.upper() and "json" not in prompt:
            json_prompt = f"{prompt}\n\n请以有效的 JSON 格式返回结果。"

        client = self._get_client()

        model = kwargs.get("model", self.config.model)
        temperature = kwargs.get("temperature", self.config.temperature)
        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert API test engineer. Always respond with valid JSON."},
                {"role": "user", "content": json_prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"} if "gpt-4" in model else None,
        )

        content = response.choices[0].message.content

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON response: {content}")
            raise ValueError(
                f"Failed to parse JSON response from OpenAI.\n\n"
                f"JSON Error: {e}\n\n"
                f"Raw response (first 500 chars):\n{content[:500]}\n\n"
                "Tips:\n"
                "- Ensure the prompt clearly asks for JSON output\n"
                "- Try using a more capable model (e.g., gpt-4)\n"
            )


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider implementation."""

    def __init__(self, config: Optional[LLMConfig] = None, api_key: Optional[str] = None):
        """Initialize Anthropic provider.

        Args:
            config: LLM configuration
            api_key: Anthropic API key (overrides config)
        """
        super().__init__(config)

        if api_key:
            self.config.api_key = api_key

        self._client = None

    def _get_client(self):
        """Get or create the Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(
                    api_key=self.config.api_key,
                    timeout=self.config.timeout,
                )
            except ImportError:
                raise ImportError(
                    "The 'anthropic' package is required for Anthropic provider.\n\n"
                    "Install it with:\n"
                    "  pip install anthropic\n\n"
                    "You can get your API key from: https://console.anthropic.com/\n"
                )
        return self._client

    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text using Anthropic API.

        Args:
            prompt: The input prompt
            **kwargs: Additional parameters

        Returns:
            Generated text
        """
        client = self._get_client()

        model = kwargs.get("model", self.config.model)
        temperature = kwargs.get("temperature", self.config.temperature)
        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)

        self.logger.debug(f"Generating with model={model}, temperature={temperature}")

        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system="You are an expert API test engineer.",
            messages=[
                {"role": "user", "content": prompt}
            ],
        )

        return response.content[0].text

    def generate_json(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate JSON response using Anthropic API.

        Args:
            prompt: The input prompt
            **kwargs: Additional parameters

        Returns:
            Parsed JSON dictionary
        """
        json_prompt = prompt
        if "JSON" not in prompt.upper() and "json" not in prompt:
            json_prompt = f"{prompt}\n\n请以有效的 JSON 格式返回结果，不要包含任何其他文本。"

        content = self.generate(json_prompt, **kwargs)

        # Extract JSON from response (handle markdown code blocks)
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            content = content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            content = content[start:end].strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON response: {content}")
            raise ValueError(
                f"Failed to parse JSON response from Anthropic.\n\n"
                f"JSON Error: {e}\n\n"
                f"Raw response (first 500 chars):\n{content[:500]}\n\n"
                "Tips:\n"
                "- Ensure the prompt clearly asks for JSON output\n"
                "- The response may contain markdown code blocks - try removing them\n"
            )


class ZhipuProvider(LLMProvider):
    """智谱AI GLM系列模型 Provider.

    使用 OpenAI 兼容 API 接口调用智谱AI的大模型服务。
    支持模型: glm-4, glm-4-flash, glm-3-turbo
    """

    # 智谱AI OpenAI兼容 API base URL
    ZHIPU_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"

    def __init__(self, config: Optional[LLMConfig] = None, api_key: Optional[str] = None):
        """Initialize Zhipu provider.

        Args:
            config: LLM configuration
            api_key: 智谱AI API key (overrides config, can also use ZHIPU_API_KEY env var)
        """
        super().__init__(config)

        # Override API key if provided directly
        if api_key:
            self.config.api_key = api_key

        # If no API key, try ZHIPU_API_KEY environment variable
        if not self.config.api_key:
            import os
            self.config.api_key = os.getenv("ZHIPU_API_KEY")

        # Set default model if not specified
        if self.config.model == "gpt-4":  # Default from LLMConfig
            self.config.model = "glm-4-flash"

        self._client = None

    def _get_client(self):
        """Get or create the OpenAI client for Zhipu API.

        Returns:
            OpenAI client instance configured for Zhipu API

        Raises:
            ImportError: If openai package is not installed
            ValueError: If API key is not configured
        """
        if self._client is None:
            if not self.config.api_key:
                raise ValueError(
                    "Zhipu API key is required for using GLM models.\n\n"
                    "Please provide your API key in one of the following ways:\n\n"
                    "1. Pass the api_key parameter:\n"
                    "   provider = ZhipuProvider(api_key='your-api-key')\n\n"
                    "2. Set the ZHIPU_API_KEY environment variable:\n"
                    "   export ZHIPU_API_KEY='your-api-key'\n\n"
                    "You can get your API key from: https://open.bigmodel.cn/\n"
                )
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self.config.api_key,
                    base_url=self.ZHIPU_BASE_URL,
                    timeout=self.config.timeout,
                )
            except ImportError:
                raise ImportError(
                    "The 'openai' package is required for Zhipu AI provider.\n\n"
                    "Zhipu AI uses OpenAI-compatible API, so you need the openai SDK.\n\n"
                    "Install it with:\n"
                    "  pip install openai\n\n"
                    "Or install FlowGenius with LLM support:\n"
                    "  pip install flowgenius-smartadapter[llm]\n"
                )
        return self._client

    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text using Zhipu AI API.

        Args:
            prompt: The input prompt
            **kwargs: Additional parameters (model, temperature, etc.)

        Returns:
            Generated text
        """
        client = self._get_client()

        # Merge config defaults with kwargs
        model = kwargs.get("model", self.config.model)
        temperature = kwargs.get("temperature", self.config.temperature)
        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)

        self.logger.debug(f"Generating with Zhipu model={model}, temperature={temperature}")

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一个专业的API测试工程师，擅长编写高质量的Python测试代码。"},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return response.choices[0].message.content

    def generate_json(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate JSON response using Zhipu AI API.

        Args:
            prompt: The input prompt
            **kwargs: Additional parameters

        Returns:
            Parsed JSON dictionary
        """
        # Add JSON format instruction if not present
        json_prompt = prompt
        if "JSON" not in prompt.upper() and "json" not in prompt:
            json_prompt = f"{prompt}\n\n请以有效的 JSON 格式返回结果，不要包含任何其他文本。"

        client = self._get_client()

        model = kwargs.get("model", self.config.model)
        temperature = kwargs.get("temperature", self.config.temperature)
        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一个专业的API测试工程师，擅长分析API响应并生成JSON格式的结果。"},
                {"role": "user", "content": json_prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        content = response.choices[0].message.content

        # Extract JSON from response (handle markdown code blocks)
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            content = content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            # Skip language identifier on first line
            first_newline = content.find("\n", start)
            if first_newline > 0:
                start = first_newline + 1
            end = content.find("```", start)
            if end > start:
                content = content[start:end].strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON response: {content}")
            raise ValueError(
                f"Failed to parse JSON response from Zhipu AI.\n\n"
                f"JSON Error: {e}\n\n"
                f"Raw response (first 500 chars):\n{content[:500]}\n\n"
                "Tips:\n"
                "- Ensure the prompt clearly asks for JSON output\n"
                "- The response may contain markdown code blocks - they are auto-extracted\n"
                "- Try using glm-4 model for better JSON formatting\n"
            )


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing purposes.

    This provider returns pre-configured responses and is useful for testing
    without making actual API calls.
    """

    def __init__(
        self,
        config: Optional[LLMConfig] = None,
        responses: Optional[Dict[str, str]] = None,
        default_response: str = "{}"
    ):
        """Initialize mock provider.

        Args:
            config: LLM configuration
            responses: Dictionary mapping prompt patterns to responses
            default_response: Default response when no pattern matches
        """
        super().__init__(config)
        self.responses = responses or {}
        self.default_response = default_response
        self.call_history: List[Dict[str, Any]] = []

    def generate(self, prompt: str, **kwargs) -> str:
        """Generate a mock response.

        Args:
            prompt: The input prompt
            **kwargs: Additional parameters (ignored)

        Returns:
            Mock response
        """
        self.call_history.append({"prompt": prompt, "kwargs": kwargs})

        # Check for matching patterns
        for pattern, response in self.responses.items():
            if pattern.lower() in prompt.lower():
                return response

        return self.default_response

    def generate_json(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate a mock JSON response.

        Args:
            prompt: The input prompt
            **kwargs: Additional parameters (ignored)

        Returns:
            Parsed JSON dictionary
        """
        response = self.generate(prompt, **kwargs)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {"error": "Invalid JSON in mock response", "raw": response}

    def set_response(self, pattern: str, response: str) -> None:
        """Set a response for a specific pattern.

        Args:
            pattern: Pattern to match in prompts
            response: Response to return
        """
        self.responses[pattern] = response

    def reset_history(self) -> None:
        """Clear the call history."""
        self.call_history = []