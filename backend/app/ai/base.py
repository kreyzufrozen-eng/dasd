"""AIProvider abstraction.

Any concrete provider (OpenAI-compatible, future Claude/Gemini/local model)
implements these methods and returns validated Pydantic objects. Callers
never see provider-specific request/response shapes.
"""
from abc import ABC, abstractmethod
from typing import Any, Optional

from app.schemas.ai_analysis import LeadAnalysis
from app.schemas.profile_draft import ProfileDraft


class AIProvider(ABC):
    @abstractmethod
    async def analyze_lead(
        self, text: str, system_prompt: str, context: Optional[dict[str, Any]] = None
    ) -> LeadAnalysis:
        """Analyze a single raw item's text and return a validated LeadAnalysis.

        `system_prompt` is built by the caller from the SearchProfile doing
        the analysis (see app/ai/prompts.py build_system_prompt) — the
        provider itself stays profession-agnostic, just "given this system
        prompt and this text, get me a validated LeadAnalysis".

        Must raise AIProviderError / AIResponseValidationError on failure —
        must never return an unvalidated/partial result.
        """
        raise NotImplementedError

    @abstractmethod
    async def generate_profile_draft(self, description: str) -> ProfileDraft:
        """Onboarding step 1: turn the user's free-text description of
        their work into a structured SearchProfile draft (see
        app/ai/profile_builder_prompts.py). Same failure contract as
        analyze_lead — raises rather than returning a partial result."""
        raise NotImplementedError
