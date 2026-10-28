from dataclasses import dataclass
from typing import AsyncIterator, Literal, Mapping, Protocol


class LLMConfigurationError(Exception):
    pass


class LLMProviderError(Exception):
    pass


class LLMRateLimitError(LLMProviderError):
    def __init__(
        self,
        message: str = "Generation provider rate limit reached",
        delay: float | None = None,
    ):
        super().__init__(message)
        self.delay = delay


class LLMQuotaExhaustedError(LLMRateLimitError):
    """Raised when the non-recoverable daily quota (e.g. 20 RPD) is exhausted."""

    pass


@dataclass(frozen=True)
class GenerationResult:
    text: str
    model_name: str
    finish_reason: str | None = None


@dataclass(frozen=True)
class StreamingGenerationEvent:
    """Provider-neutral incremental generation output."""

    event_type: Literal["text_delta", "usage", "completion"]
    text: str = ""
    model_name: str | None = None
    finish_reason: str | None = None
    usage: Mapping[str, int] | None = None


class LLMProvider(Protocol):
    provider_name: str
    model_name: str

    def generate(self, system_instruction: str, user_prompt: str) -> GenerationResult: ...

    def stream_generate(
        self, system_instruction: str, user_prompt: str
    ) -> AsyncIterator[StreamingGenerationEvent]: ...
