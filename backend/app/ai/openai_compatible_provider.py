"""AIProvider implementation for any OpenAI-compatible /chat/completions API.

Works with OpenAI itself and any self-hosted/third-party endpoint that
speaks the same wire format (many local model servers do). Model, base
URL, and key all come from environment variables — nothing hardcoded.
"""
import json
from typing import Any, Optional, Type, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.ai.base import AIProvider
from app.ai.exceptions import AIProviderError, AIResponseValidationError
from app.ai.json_utils import extract_json_object
from app.ai.profile_builder_prompts import (
    PROFILE_DRAFT_SYSTEM_PROMPT,
    build_profile_draft_user_prompt,
)
from app.ai.prompts import build_repair_prompt, build_user_prompt
from app.core.logging import get_logger
from app.schemas.ai_analysis import LeadAnalysis
from app.schemas.profile_draft import ProfileDraft

logger = get_logger(__name__)

ModelT = TypeVar("ModelT", bound=BaseModel)


class OpenAICompatibleProvider(AIProvider):
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str],
        model: str,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        if not base_url:
            raise ValueError("AI_BASE_URL is required for openai_compatible provider")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    async def _call_completion(self, messages: list[dict[str, str]]) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions", headers=headers, json=payload
            )
            response.raise_for_status()
            data = response.json()

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderError(f"Unexpected AI response shape: {data!r}") from exc

    async def _complete_and_validate(
        self, system_prompt: str, user_prompt: str, response_model: Type[ModelT]
    ) -> ModelT:
        """Shared retry/repair loop: call the model, extract+parse JSON,
        validate against `response_model`; on failure, ask the model to
        fix its own output and try again, up to max_retries times. Used
        by both analyze_lead and generate_profile_draft — same contract,
        different schema."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        last_error: Optional[str] = None
        raw_content: Optional[str] = None

        for attempt in range(1, self.max_retries + 2):  # first try + N retries
            if last_error is not None:
                messages.append({"role": "user", "content": build_repair_prompt(last_error)})

            try:
                raw_content = await self._call_completion(messages)
            except httpx.HTTPError as exc:
                logger.exception("AI provider HTTP call failed (attempt %s): %s", attempt, exc)
                raise AIProviderError(f"AI request failed: {exc}") from exc

            json_str = extract_json_object(raw_content)
            try:
                data = json.loads(json_str)
                return response_model.model_validate(data)
            except (json.JSONDecodeError, ValidationError) as exc:
                logger.warning(
                    "AI response failed JSON/schema validation (attempt %s/%s): %s",
                    attempt,
                    self.max_retries + 1,
                    exc,
                )
                last_error = str(exc)
                continue

        logger.error(
            "AI response invalid after %s attempts, giving up. Last raw response: %r",
            self.max_retries + 1,
            raw_content,
        )
        raise AIResponseValidationError(
            f"AI did not return valid JSON matching {response_model.__name__} "
            f"after {self.max_retries + 1} attempts"
        )

    async def analyze_lead(
        self, text: str, system_prompt: str, context: Optional[dict[str, Any]] = None
    ) -> LeadAnalysis:
        return await self._complete_and_validate(
            system_prompt, build_user_prompt(text, context), LeadAnalysis
        )

    async def generate_profile_draft(self, description: str) -> ProfileDraft:
        return await self._complete_and_validate(
            PROFILE_DRAFT_SYSTEM_PROMPT,
            build_profile_draft_user_prompt(description),
            ProfileDraft,
        )
