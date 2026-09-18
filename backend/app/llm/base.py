from dataclasses import dataclass
from typing import AsyncIterator, Literal, Mapping, Protocol


class LLMConfigurationError(Exception):
    pass


class LLMProviderError(Exception):
    pass


class LLMRateLimitError(LLMProviderError):
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
