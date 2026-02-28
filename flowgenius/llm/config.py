"""
LLM configuration management.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import os


@dataclass
class LLMConfig:
    """LLM configuration settings.

    Attributes:
        provider: LLM provider name ("openai", "anthropic", "local")
        api_key: API key for the provider
        model: Model identifier to use
        temperature: Temperature for response generation
        max_tokens: Maximum tokens in response
        timeout: Request timeout in seconds
        enable_assertion_analysis: Enable LLM-enhanced assertion analysis
        enable_code_generation: Enable LLM-enhanced code generation
        enable_correlation_analysis: Enable LLM-enhanced correlation analysis
        fallback_to_rules: Fall back to rule-based methods on LLM failure
        retry_count: Number of retries on API failure
        retry_delay: Delay between retries in seconds
    """

    provider: str = "openai"
    api_key: Optional[str] = None
    model: str = "gpt-4"
    temperature: float = 0.3
    max_tokens: int = 2000
    timeout: int = 30

    # Feature toggles
    enable_assertion_analysis: bool = True
    enable_code_generation: bool = True
    enable_correlation_analysis: bool = True

    # Fallback settings
    fallback_to_rules: bool = True
    retry_count: int = 3
    retry_delay: float = 1.0

    # Additional provider-specific settings
    extra_params: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.temperature < 0 or self.temperature > 2:
            raise ValueError("Temperature must be between 0 and 2")
        if self.max_tokens < 1:
            raise ValueError("max_tokens must be at least 1")
        if self.timeout < 1:
            raise ValueError("timeout must be at least 1 second")

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Create LLMConfig from environment variables.

        Environment variables:
            LLM_PROVIDER: Provider name (default: "openai")
            OPENAI_API_KEY: OpenAI API key
            ANTHROPIC_API_KEY: Anthropic API key
            LLM_MODEL: Model identifier (default: "gpt-4")
            LLM_TEMPERATURE: Temperature (default: 0.3)
            LLM_MAX_TOKENS: Max tokens (default: 2000)
            LLM_TIMEOUT: Timeout in seconds (default: 30)
            LLM_FALLBACK_TO_RULES: Enable fallback (default: "true")

        Returns:
            LLMConfig instance
        """
        provider = os.getenv("LLM_PROVIDER", "openai").lower()

        # Get API key based on provider
        api_key = None
        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
        elif provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")

        return cls(
            provider=provider,
            api_key=api_key,
            model=os.getenv("LLM_MODEL", "gpt-4" if provider == "openai" else "claude-3-opus-20240229"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.3")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "2000")),
            timeout=int(os.getenv("LLM_TIMEOUT", "30")),
            fallback_to_rules=os.getenv("LLM_FALLBACK_TO_RULES", "true").lower() == "true",
        )

    def validate(self) -> bool:
        """Validate that the configuration is complete.

        Returns:
            True if configuration is valid

        Raises:
            ValueError: If required configuration is missing
        """
        if not self.api_key:
            raise ValueError(f"API key is required for provider '{self.provider}'")
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary.

        Returns:
            Dictionary representation of the configuration
        """
        return {
            "provider": self.provider,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
            "enable_assertion_analysis": self.enable_assertion_analysis,
            "enable_code_generation": self.enable_code_generation,
            "enable_correlation_analysis": self.enable_correlation_analysis,
            "fallback_to_rules": self.fallback_to_rules,
            "retry_count": self.retry_count,
            "retry_delay": self.retry_delay,
        }