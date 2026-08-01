"""Abstract LLM Provider interface."""

from abc import ABC, abstractmethod
from typing import Any, Callable


class LLMProviderError(RuntimeError):
    """Safe, structured failure from a real LLM provider.

    Provider credentials and raw response payloads must never cross this
    boundary. ``details`` only contains operational metadata that is safe to
    persist in traces and return to the product UI.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        timing: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.details = details or {}
        self.timing = timing or {}


class LLMProviderCancelled(RuntimeError):
    """A user-requested streaming cancellation with an optional partial response."""

    def __init__(self, partial_content: str, *, timing: dict[str, Any] | None = None):
        super().__init__("Provider generation was cancelled by the user.")
        self.partial_content = partial_content
        self.timing = timing or {}


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    All providers (OpenAI-compatible, local simulation, and other adapters) implement this interface.
    """

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str,
                 context: dict[str, Any] | None = None) -> dict:
        """Generate a response.

        Returns:
            dict with keys:
                content: str — the generated text
                model: str — model name used
                provider: str — provider identifier
                usage: dict | None — token usage info
                finish_reason: str | None
                warnings: list[str] — any warnings (e.g. simulation fallback)
        """
        ...

    def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        on_delta: Callable[[str], None],
        should_cancel: Callable[[], bool],
        context: dict[str, Any] | None = None,
    ) -> dict:
        """Stream a real response. Providers must override this to support Web streaming."""
        raise LLMProviderError(
            "LLM_PROVIDER_STREAMING_UNSUPPORTED",
            "The configured Provider does not support real streaming.",
            details={"provider": self.provider_name},
        )

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...

    @property
    @abstractmethod
    def is_simulation(self) -> bool:
        ...
