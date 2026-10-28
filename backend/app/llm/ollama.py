"""Ollama local LLM provider for AURORA."""

from collections.abc import AsyncIterator
import json
import logging
from typing import Any

import httpx

from app.llm.base import (
    GenerationResult,
    LLMConfigurationError,
    LLMProvider,
    LLMProviderError,
    StreamingGenerationEvent,
)

logger = logging.getLogger(__name__)


class OllamaLLMProvider:
    provider_name = "ollama"

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        model_name: str = "qwen3:8b",
        num_ctx: int = 4096,
        timeout_seconds: float = 180.0,
        think: bool = False,
    ):
        if not base_url or not base_url.strip():
            raise LLMConfigurationError("Ollama base URL is not configured")
        if not model_name or not model_name.strip():
            raise LLMConfigurationError("Ollama model name is not configured")
        self.base_url = base_url.strip().rstrip("/")
        self.model_name = model_name.strip()
        self.num_ctx = num_ctx
        self.timeout_seconds = timeout_seconds
        self.think = think

    def _chat_payload(
        self, system_instruction: str, user_prompt: str, stream: bool = False
    ) -> dict[str, Any]:
        return {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt},
            ],
            "stream": stream,
            "think": self.think,
            "options": {
                "num_ctx": self.num_ctx,
                "num_predict": 4096,
                "temperature": 0.2,
            },
        }

    def generate(self, system_instruction: str, user_prompt: str) -> GenerationResult:
        """Execute non-streaming generation via Ollama /api/chat."""
        url = f"{self.base_url}/api/chat"
        payload = self._chat_payload(system_instruction, user_prompt, stream=False)
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(url, json=payload)
                if response.status_code == 404:
                    raise LLMProviderError(
                        f"Ollama model '{self.model_name}' was not found. "
                        f"Run 'ollama pull {self.model_name}' to download it."
                    )
                response.raise_for_status()
                data = response.json()
                message = data.get("message", {})
                content = message.get("content", "").strip()
                if not content:
                    raise LLMProviderError("Ollama returned an empty response")
                return GenerationResult(
                    text=content,
                    model_name=f"ollama/{self.model_name}",
                    finish_reason=data.get("done_reason", "stop"),
                )
        except httpx.ConnectError as exc:
            logger.warning("Ollama connection failed at %s: %s", url, exc)
            raise LLMProviderError(
                f"Ollama is not reachable at {self.base_url}. Ensure the Ollama server is running."
            ) from exc
        except httpx.TimeoutException as exc:
            logger.warning("Ollama request timed out after %.1fs: %s", self.timeout_seconds, exc)
            raise LLMProviderError(
                f"Ollama generation timed out after {self.timeout_seconds}s"
            ) from exc
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.warning("Ollama request failed: %s", exc)
            raise LLMProviderError(f"Ollama request failed: {exc}") from exc
        except LLMProviderError:
            raise
        except Exception as exc:
            logger.exception("Unexpected error during Ollama generation: %s", exc)
            raise LLMProviderError(f"Ollama generation failed: {exc}") from exc

    async def stream_generate(
        self, system_instruction: str, user_prompt: str
    ) -> AsyncIterator[StreamingGenerationEvent]:
        """Stream generation tokens via Ollama /api/chat ndjson."""
        url = f"{self.base_url}/api/chat"
        payload = self._chat_payload(system_instruction, user_prompt, stream=True)
        received_text = False
        finish_reason = None
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code == 404:
                        raise LLMProviderError(
                            f"Ollama model '{self.model_name}' was not found. "
                            f"Run 'ollama pull {self.model_name}' to download it."
                        )
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line or not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            logger.warning("Malformed JSON from Ollama stream: %s", line)
                            continue
                        delta = data.get("message", {}).get("content", "")
                        if delta:
                            received_text = True
                            yield StreamingGenerationEvent(
                                event_type="text_delta", text=delta
                            )
                        if data.get("done"):
                            finish_reason = data.get("done_reason", "stop")
            if not received_text:
                raise LLMProviderError("Ollama streaming returned no text")
            yield StreamingGenerationEvent(
                event_type="completion",
                model_name=f"ollama/{self.model_name}",
                finish_reason=finish_reason,
            )
        except httpx.ConnectError as exc:
            logger.warning("Ollama connection failed at %s: %s", url, exc)
            raise LLMProviderError(
                f"Ollama is not reachable at {self.base_url}. Ensure the Ollama server is running."
            ) from exc
        except httpx.TimeoutException as exc:
            logger.warning("Ollama stream timed out after %.1fs: %s", self.timeout_seconds, exc)
            raise LLMProviderError(
                f"Ollama generation timed out after {self.timeout_seconds}s"
            ) from exc
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.warning("Ollama stream request failed: %s", exc)
            raise LLMProviderError(f"Ollama streaming failed: {exc}") from exc
        except LLMProviderError:
            raise
        except Exception as exc:
            logger.exception("Unexpected error during Ollama streaming: %s", exc)
            raise LLMProviderError(f"Ollama streaming failed: {exc}") from exc
