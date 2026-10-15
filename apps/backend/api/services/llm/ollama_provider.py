import json
import logging
import httpx
from typing import Any, Dict, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from api.core.interfaces.llm_provider import (
    LLMProvider, LLMUnavailableError, LLMGenerationError, LLMModelNotFoundError,
)
from api.core.config import settings

logger = logging.getLogger(__name__)

# Only retry genuine connectivity failures - a malformed/empty response from a model that
# IS responding won't be fixed by hammering it again with the exact same prompt.
_RETRYABLE_EXCEPTIONS = (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.TimeoutException)


class OllamaProvider(LLMProvider):
    """
    Implementation of LLMProvider using Ollama.
    Uses open-source models only (Qwen2.5 default) - see docs/PROJECT_RULES.md Rule 1:
    business logic never talks to a model directly, only through this interface, so
    swapping models/providers never touches agent code.
    """
    def __init__(self, model: Optional[str] = None, base_url: Optional[str] = None,
                 fallback_model: Optional[str] = None, timeout: Optional[float] = None):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL
        self.fallback_model = fallback_model if fallback_model is not None else settings.OLLAMA_FALLBACK_MODEL
        self.timeout = timeout or settings.OLLAMA_TIMEOUT_SECONDS

    def is_available(self) -> bool:
        """Cheap connectivity check for health checks - does NOT run inference."""
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False

    def list_available_models(self) -> Optional[list]:
        """Best-effort list of model tags actually pulled on this Ollama instance, for
        building actionable "model not found" errors. Returns None (never raises) if
        Ollama itself can't be reached - that's a separate, already-clear failure mode."""
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                return [m["name"] for m in response.json().get("models", [])]
        except Exception:
            return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
        reraise=True,
    )
    def _post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status()
            return response.json()

    def _generate_with_model(self, model: str, prompt: str, system_prompt: str, temperature: float,
                              response_format: Optional[str], **kwargs) -> str:
        payload = {
            "model": model,
            "prompt": prompt,
            "system": system_prompt,
            "temperature": temperature,
            "stream": False,
            **({"format": response_format} if response_format else {}),
            **kwargs,
        }
        try:
            data = self._post(payload)
        except _RETRYABLE_EXCEPTIONS as exc:
            raise LLMUnavailableError(f"Ollama at {self.base_url} is unreachable (model={model}): {exc}") from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                # Ollama is reachable but this exact tag isn't pulled - a config/deployment
                # mismatch, not a transient problem. Give an actionable error rather than a
                # bare status code; never guess at a substitute model on our own.
                available = self.list_available_models()
                hint = (f"Available local models: {available}" if available is not None
                        else "Could not list available models (Ollama unreachable for /api/tags).")
                raise LLMModelNotFoundError(
                    f"Configured Ollama model '{model}' is unavailable (404 from {self.base_url}). {hint}"
                ) from exc
            # Other non-2xx application errors - not a transient/connectivity problem, don't retry.
            raise LLMGenerationError(f"Ollama returned {exc.response.status_code} for model={model}: {exc}") from exc
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(f"Ollama request failed (model={model}): {exc}") from exc

        text = (data.get("response") or "").strip()
        if not text:
            raise LLMGenerationError(f"Ollama returned an empty response for model={model}.")
        return text

    def generate(self, prompt: str, system_prompt: str = "", temperature: float = 0.7, **kwargs) -> str:
        try:
            return self._generate_with_model(self.model, prompt, system_prompt, temperature, None, **kwargs)
        except (LLMUnavailableError, LLMModelNotFoundError) as exc:
            # Both "Ollama is down" and "this exact model tag isn't pulled" are cases
            # where a caller who explicitly configured a fallback model wants it tried -
            # we never pick a substitute model on our own otherwise.
            if self.fallback_model:
                logger.warning(f"Primary model '{self.model}' unavailable ({exc}), falling back to '{self.fallback_model}'.")
                return self._generate_with_model(self.fallback_model, prompt, system_prompt, temperature, None, **kwargs)
            raise

    def generate_json(self, prompt: str, system_prompt: str = "", schema: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        def _attempt(model: str) -> Dict[str, Any]:
            text = self._generate_with_model(model, prompt, system_prompt, temperature=0.1,
                                              response_format="json", **kwargs)
            try:
                return json.loads(text)
            except json.JSONDecodeError as exc:
                raise LLMGenerationError(f"Ollama (model={model}) returned invalid JSON: {exc}. Raw: {text[:200]!r}") from exc

        try:
            return _attempt(self.model)
        except (LLMUnavailableError, LLMModelNotFoundError) as exc:
            if self.fallback_model:
                logger.warning(f"Primary model '{self.model}' unavailable ({exc}), falling back to '{self.fallback_model}'.")
                return _attempt(self.fallback_model)
            raise
