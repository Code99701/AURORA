import asyncio
import json
import logging

import httpx

from app.llm.base import (
    GenerationResult,
    LLMConfigurationError,
    LLMProviderError,
    LLMRateLimitError,
    StreamingGenerationEvent,
)


logger = logging.getLogger(__name__)
TRANSIENT_PROVIDER_STATUSES = {408, 429, 500, 502, 503, 504}
STREAM_MAX_ATTEMPTS = 2


class GeminiLLMProvider:
    provider_name = "gemini"

    def __init__(
        self,
        api_key: str | None,
        model_name: str,
        max_output_tokens: int,
    ):
        if not api_key or not api_key.strip():
            raise LLMConfigurationError("Gemini API key is not configured")
        if not model_name.strip():
            raise LLMConfigurationError("Gemini generation model is not configured")
        self.model_name = model_name.strip()
        self.max_output_tokens = max_output_tokens
        self._api_key = api_key.strip()

    def _request_body(self, system_instruction: str, user_prompt: str) -> dict:
        return {
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "contents": [
                {"role": "user", "parts": [{"text": user_prompt}]}
            ],
            "generationConfig": {"maxOutputTokens": self.max_output_tokens},
        }

    def generate(self, system_instruction: str, user_prompt: str) -> GenerationResult:
        try:
            response = httpx.post(
                "https://generativelanguage.googleapis.com/"
                f"v1beta/models/{self.model_name}:generateContent",
                headers={"x-goog-api-key": self._api_key},
                json=self._request_body(system_instruction, user_prompt),
                timeout=60.0,
            )
            if response.status_code == 429:
                logger.warning(
                    "Gemini generation request rate limited (status=%s)",
                    response.status_code,
                )
                raise LLMRateLimitError("Generation provider rate limit reached")
            response.raise_for_status()
            payload = response.json()
            candidates = payload.get("candidates") or []
            if not candidates:
                raise LLMProviderError("Generation provider returned no candidate")
            candidate = candidates[0]
            parts = candidate.get("content", {}).get("parts", [])
            answer = "".join(
                part.get("text", "")
                for part in parts
                if isinstance(part, dict) and not part.get("thought")
            ).strip()
            if not answer:
                raise LLMProviderError("Generation provider returned no text")
            return GenerationResult(
                text=answer,
                model_name=payload.get("modelVersion") or self.model_name,
                finish_reason=candidate.get("finishReason"),
            )
        except LLMProviderError:
            raise
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Gemini generation request rejected (status=%s)",
                exc.response.status_code,
            )
            raise LLMProviderError("Generation provider request failed") from exc
        except httpx.RequestError as exc:
            logger.warning(
                "Gemini generation request could not reach provider (error=%s)",
                type(exc).__name__,
            )
            raise LLMProviderError("Generation provider request failed") from exc
        except Exception as exc:
            raise LLMProviderError("Generation provider request failed") from exc

    async def stream_generate(self, system_instruction: str, user_prompt: str):
        """Normalize Gemini's SSE response into provider-neutral events."""
        model_name = self.model_name
        finish_reason = None
        usage = None
        received_text = False
        try:
            for attempt in range(1, STREAM_MAX_ATTEMPTS + 1):
                try:
                    async with httpx.AsyncClient(timeout=60.0) as client:
                        async with client.stream(
                            "POST",
                            "https://generativelanguage.googleapis.com/"
                            f"v1beta/models/{self.model_name}:streamGenerateContent?alt=sse",
                            headers={"x-goog-api-key": self._api_key},
                            json=self._request_body(system_instruction, user_prompt),
                        ) as response:
                            if response.status_code == 429:
                                raise LLMRateLimitError(
                                    "Generation provider rate limit reached"
                                )
                            response.raise_for_status()
                            async for line in response.aiter_lines():
                                if not line or line.startswith(":"):
                                    continue
                                if not line.startswith("data:"):
                                    raise LLMProviderError(
                                        "Generation provider returned a malformed stream"
                                    )
                                raw_payload = line[5:].strip()
                                if not raw_payload or raw_payload == "[DONE]":
                                    continue
                                try:
                                    payload = json.loads(raw_payload)
                                except json.JSONDecodeError as exc:
                                    raise LLMProviderError(
                                        "Generation provider returned a malformed stream"
                                    ) from exc
                                model_name = payload.get("modelVersion") or model_name
                                usage_payload = payload.get("usageMetadata")
                                if isinstance(usage_payload, dict):
                                    usage = {
                                        key: value
                                        for key, value in usage_payload.items()
                                        if isinstance(value, int)
                                    }
                                    if usage:
                                        yield StreamingGenerationEvent(
                                            event_type="usage", usage=usage
                                        )
                                candidates = payload.get("candidates") or []
                                if not candidates:
                                    continue
                                candidate = candidates[0]
                                finish_reason = (
                                    candidate.get("finishReason") or finish_reason
                                )
                                parts = candidate.get("content", {}).get("parts", [])
                                delta = "".join(
                                    part.get("text", "")
                                    for part in parts
                                    if isinstance(part, dict)
                                    and not part.get("thought")
                                )
                                if delta:
                                    received_text = True
                                    yield StreamingGenerationEvent(
                                        event_type="text_delta", text=delta
                                    )
                    break
                except LLMRateLimitError:
                    if received_text or attempt == STREAM_MAX_ATTEMPTS:
                        raise
                    logger.warning(
                        "Retrying Gemini generation stream before first text "
                        "(attempt=%s, status=429)",
                        attempt,
                    )
                    await asyncio.sleep(0.25)
                except httpx.HTTPStatusError as exc:
                    if (
                        received_text
                        or attempt == STREAM_MAX_ATTEMPTS
                        or exc.response.status_code not in TRANSIENT_PROVIDER_STATUSES
                    ):
                        raise
                    logger.warning(
                        "Retrying Gemini generation stream before first text "
                        "(attempt=%s, status=%s)",
                        attempt,
                        exc.response.status_code,
                    )
                    await asyncio.sleep(0.25)
                except httpx.RequestError as exc:
                    if received_text or attempt == STREAM_MAX_ATTEMPTS:
                        raise
                    logger.warning(
                        "Retrying Gemini generation stream before first text "
                        "(attempt=%s, error=%s)",
                        attempt,
                        type(exc).__name__,
                    )
                    await asyncio.sleep(0.25)
            if not received_text:
                raise LLMProviderError("Generation provider returned no text")
            yield StreamingGenerationEvent(
                event_type="completion",
                model_name=model_name,
                finish_reason=finish_reason,
                usage=usage,
            )
        except LLMProviderError:
            raise
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                raise LLMRateLimitError(
                    "Generation provider rate limit reached"
                ) from exc
            raise LLMProviderError("Generation provider request failed") from exc
        except Exception as exc:
            raise LLMProviderError("Generation provider request failed") from exc
