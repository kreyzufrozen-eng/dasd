class AIProviderError(Exception):
    """Base error for anything that goes wrong talking to an AI provider."""


class AIResponseValidationError(AIProviderError):
    """Raised when the AI's response could not be parsed/validated as
    LeadAnalysis even after retries. Callers (the pipeline) must catch
    this, log it, and continue — never let it crash the worker."""
