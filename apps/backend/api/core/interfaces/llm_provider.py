from abc import ABC, abstractmethod
from typing import Any, Dict


class LLMUnavailableError(Exception):
    """The provider (e.g. Ollama) could not be reached at all - connection refused,
    DNS failure, timeout. Retryable; callers should surface a clear "model unavailable"
    state rather than a generic 500."""


class LLMGenerationError(Exception):
    """The provider was reached but returned something unusable - empty text,
    malformed JSON where JSON was required, or a non-2xx application error."""


class LLMModelNotFoundError(LLMGenerationError):
    """The provider was reached, but the configured model isn't pulled/available on it
    (e.g. Ollama's 404 for an unknown model tag). A subclass of LLMGenerationError -
    callers that only catch the parent still get correct "don't blindly retry with the
    same input" behavior - but callers that want to react specifically to a
    configuration/deployment mismatch (rather than a bad generation) can catch this."""


class LLMProvider(ABC):
    """Abstract interface for all LLM inference operations."""
    
    @abstractmethod
    def generate(self, prompt: str, system_prompt: str = "", temperature: float = 0.7, **kwargs) -> str:
        """Generate text from a prompt."""
        pass
        
    @abstractmethod
    def generate_json(self, prompt: str, system_prompt: str = "", schema: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        """Generate structured JSON output."""
        pass
