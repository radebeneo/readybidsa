"""LLM provider adapter.

The adapter is capability-aware. Models that support strict JSON schema output on Groq get
`response_format={"type": "json_schema", "strict": true, ...}`; this includes the default
`openai/gpt-oss-120b`. Other models get JSON object mode. In both cases the caller validates
the output with Pydantic, so the format option is a convenience, never a guarantee.

Provider failures are surfaced as `LLMError`. Nothing here fabricates a fallback result.
"""

from collections.abc import Sequence
from typing import Any, Protocol

import groq

# Groq models documented with strict `json_schema` support. Check a model here before
# relying on strict mode. Anything else uses JSON object mode plus Pydantic validation.
STRICT_JSON_SCHEMA_MODELS = frozenset(
    {
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "qwen/qwen3.8-27b",
        "meta-models/muse-spark-open",
    }
)

Message = dict[str, str]


def supports_strict_json_schema(model: str) -> bool:
    return model in STRICT_JSON_SCHEMA_MODELS


class LLMError(Exception):
    """A provider call failed. `fatal` means further calls in this run will fail too."""

    def __init__(self, code: str, message: str, *, fatal: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.fatal = fatal


class LLMInvalidOutputError(LLMError):
    """The model produced output that is not usable JSON. Callers may ask for a repair."""


class LLMProvider(Protocol):
    model: str

    def complete_json(
        self, messages: Sequence[Message], *, schema_name: str, json_schema: dict[str, Any]
    ) -> str:
        """Return the raw JSON text produced by the model."""
        ...


_JSON_FAILURE_MARKERS = (
    "json_validate_failed",
    "Generated JSON does not match",
    "Failed to generate JSON",
)


class GroqProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_completion_tokens: int,
        client: groq.Groq | None = None,
    ) -> None:
        self.model = model
        self._max_completion_tokens = max_completion_tokens
        self._timeout = timeout_seconds
        # The SDK retries connection errors, 429 and 5xx responses up to max_retries times.
        self._client = client or groq.Groq(api_key=api_key, timeout=timeout_seconds, max_retries=2)

    def _response_format(self, schema_name: str, json_schema: dict[str, Any]) -> dict[str, Any]:
        if supports_strict_json_schema(self.model):
            return {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "strict": True, "schema": json_schema},
            }
        return {"type": "json_object"}

    def complete_json(
        self, messages: Sequence[Message], *, schema_name: str, json_schema: dict[str, Any]
    ) -> str:
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=list(messages),  # type: ignore[arg-type]
                response_format=self._response_format(schema_name, json_schema),  # type: ignore[arg-type]
                temperature=0,
                max_completion_tokens=self._max_completion_tokens,
                timeout=self._timeout,
            )
        except groq.AuthenticationError:
            raise LLMError(
                "auth_failed", "The model provider rejected the API key.", fatal=True
            ) from None
        except groq.PermissionDeniedError:
            raise LLMError(
                "permission_denied", "The API key cannot use this model.", fatal=True
            ) from None
        except groq.NotFoundError:
            raise LLMError(
                "model_not_found", f"Model '{self.model}' is not available.", fatal=True
            ) from None
        except groq.BadRequestError as error:
            text = str(error)
            if any(marker in text for marker in _JSON_FAILURE_MARKERS):
                raise LLMInvalidOutputError(
                    "invalid_json", "The model did not produce valid JSON."
                ) from None
            raise LLMError("bad_request", "The model provider rejected the request.") from None
        except groq.RateLimitError:
            raise LLMError("rate_limited", "The model provider rate limit was reached.") from None
        except groq.APITimeoutError:
            raise LLMError("timeout", "The model call timed out.") from None
        except groq.APIConnectionError:
            raise LLMError("connection_failed", "Could not reach the model provider.") from None
        except groq.APIStatusError as error:
            raise LLMError(
                "provider_error", f"The model provider returned HTTP {error.status_code}."
            ) from None

        if not response.choices:
            raise LLMInvalidOutputError("empty_response", "The model returned no choices.")
        choice = response.choices[0]
        content = choice.message.content
        if choice.finish_reason == "length":
            raise LLMInvalidOutputError(
                "truncated", "The model output was cut off at the token limit."
            )
        if not content or not content.strip():
            raise LLMInvalidOutputError("empty_response", "The model returned empty content.")
        return content
