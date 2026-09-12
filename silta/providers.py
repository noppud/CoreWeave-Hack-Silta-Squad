"""Async, typed adapter over OpenAI-compatible chat completions with accounting.

Never logs, traces, or includes the API key in any message or exception.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass
from typing import Literal, Protocol

import httpx
from dotenv import load_dotenv


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    model: str
    base_url: str
    api_key: str
    project: str | None = None


@dataclass(frozen=True)
class Completion:
    text: str
    parsed: dict | None
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_s: float
    finish_reason: str
    request_id: str | None
    cost_usd: float | None
    cost_status: Literal["known", "unknown", "not_applicable"]


class ProviderError(RuntimeError):
    """Base provider error."""


class ProviderAuthError(ProviderError):
    """Authentication failure. Do not retry."""


class ProviderTimeout(ProviderError):
    """Request timeout."""


class ProviderTruncated(ProviderError):
    """finish_reason != 'stop' is a FAILURE, not partial success."""


class Provider(Protocol):
    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema: dict,
        max_tokens: int,
        timeout_s: float,
    ) -> Completion: ...

    async def capabilities(self) -> dict: ...


class NullProvider:
    """Raises ProviderError when called. Used when no provider is configured."""

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema: dict,
        max_tokens: int,
        timeout_s: float,
    ) -> Completion:
        raise ProviderError("no inference provider configured")

    async def capabilities(self) -> dict:
        return {"provider": "null", "models": [], "features": {}}


class WandbInferenceProvider:
    """W&B Inference provider using OpenAI-compatible chat completions."""

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                **({"OpenAI-Project": config.project} if config.project else {}),
            },
            timeout=httpx.Timeout(300.0),
        )

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema: dict,
        max_tokens: int,
        timeout_s: float,
    ) -> Completion:
        started = time.perf_counter()
        deadline = started + timeout_s

        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.7,
        }

        # Try to use JSON schema if we think it's supported
        # (we'll fall back to validation if the provider doesn't enforce it)
        if schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "plan_draft",
                    "strict": False,
                    "schema": schema,
                },
            }

        attempt = 0
        last_error: Exception | None = None

        while attempt <= 2:  # initial + 2 retries
            try:
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    raise ProviderTimeout(f"Deadline exceeded before attempt {attempt}")

                response = await self._client.post(
                    "/chat/completions",
                    json=payload,
                    timeout=min(remaining, timeout_s),
                )

                if response.status_code in (401, 403):
                    raise ProviderAuthError(f"Authentication failed: {response.status_code}")

                if response.status_code == 429:
                    retry_after = float(response.headers.get("Retry-After", "2"))
                    if attempt < 2:
                        await asyncio.sleep(min(retry_after, 10.0))
                        attempt += 1
                        continue
                    raise ProviderError(f"Rate limited after {attempt + 1} attempts")

                if response.status_code >= 500:
                    if attempt < 2:
                        backoff = min(2.0 * (2**attempt), 10.0)
                        await asyncio.sleep(backoff)
                        attempt += 1
                        continue
                    raise ProviderError(
                        f"Server error {response.status_code} after {attempt + 1} attempts"
                    )

                response.raise_for_status()
                data = response.json()

                latency = time.perf_counter() - started
                choice = data["choices"][0]
                finish_reason = choice["finish_reason"]

                if finish_reason != "stop":
                    raise ProviderTruncated(f"Incomplete response: finish_reason={finish_reason}")

                text = choice["message"]["content"]
                usage = data.get("usage", {})

                # Always validate the JSON locally
                parsed = None
                if text:
                    try:
                        parsed = json.loads(text)
                    except json.JSONDecodeError as e:
                        raise ProviderError(f"Invalid JSON in response: {e}") from e

                return Completion(
                    text=text,
                    parsed=parsed,
                    provider=self.config.provider,
                    model=data.get("model", self.config.model),
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    latency_s=latency,
                    finish_reason=finish_reason,
                    request_id=response.headers.get("x-request-id"),
                    cost_usd=None,
                    cost_status="unknown",
                )

            except (TimeoutError, httpx.TimeoutException) as e:
                if attempt < 2:
                    attempt += 1
                    continue
                raise ProviderTimeout(f"Request timeout after {attempt + 1} attempts") from e

            except (httpx.NetworkError, httpx.ConnectError) as e:
                if attempt < 2:
                    backoff = min(2.0 * (2**attempt), 10.0)
                    await asyncio.sleep(backoff)
                    attempt += 1
                    last_error = e
                    continue
                raise ProviderError(f"Network error after {attempt + 1} attempts") from e

            except (ProviderAuthError, ProviderTruncated):
                raise

            except Exception as e:
                if attempt < 2 and not isinstance(
                    e, (ProviderError, ProviderAuthError, ProviderTruncated)
                ):
                    attempt += 1
                    last_error = e
                    continue
                raise

        # Should not reach here, but just in case
        if last_error:
            raise ProviderError(f"All attempts failed: {type(last_error).__name__}") from last_error
        raise ProviderError("Unexpected retry loop exit")

    async def capabilities(self) -> dict:
        """List models from /models endpoint and report feature support."""
        try:
            response = await self._client.get("/models", timeout=10.0)
            response.raise_for_status()
            data = response.json()
            models = [m["id"] for m in data.get("data", [])]
        except Exception:
            models = []

        # We cannot verify features without actual credits/tests
        return {
            "provider": self.config.provider,
            "base_url": self.config.base_url,
            "models": models,
            "features": {
                "json_schema": "unverified",
                "vision": "unverified",
            },
        }

    async def close(self) -> None:
        await self._client.aclose()


def load_provider_from_env(role: Literal["planner", "vision"]) -> ProviderConfig | None:
    """Load provider config from environment variables.

    Returns None if no API key is configured (normal state, not an error).
    """
    load_dotenv()

    # Role-specific config
    provider_key = f"{role.upper()}_PROVIDER"
    model_key = f"{role.upper()}_MODEL"

    provider = os.getenv(provider_key)
    model = os.getenv(model_key)

    # Fallback to W&B inference defaults
    if not provider:
        provider = "wandb"
    if not model:
        model = os.getenv("WANDB_INFERENCE_MODEL")

    # API key
    api_key = os.getenv("WANDB_API_KEY")
    if not api_key:
        return None

    # W&B specifics
    entity = os.getenv("WANDB_ENTITY")
    project = os.getenv("WANDB_PROJECT")
    project_header = f"{entity}/{project}" if entity and project else None

    base_url = "https://api.inference.wandb.ai/v1"

    return ProviderConfig(
        provider=provider,
        model=model or "default",
        base_url=base_url,
        api_key=api_key,
        project=project_header,
    )
