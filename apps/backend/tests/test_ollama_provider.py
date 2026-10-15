import httpx
import pytest

from api.services.llm.ollama_provider import OllamaProvider
from api.core.interfaces.llm_provider import LLMUnavailableError, LLMGenerationError, LLMModelNotFoundError


class FakeResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json_data = json_data or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("POST", "http://fake")
            raise httpx.HTTPStatusError("error", request=request, response=httpx.Response(self.status_code, request=request))

    def json(self):
        return self._json_data


def _provider(**overrides):
    defaults = {"model": "qwen2.5", "base_url": "http://fake-ollama:11434", "timeout": 1.0}
    defaults.update(overrides)
    return OllamaProvider(**defaults)


def test_normal_generation_succeeds(monkeypatch):
    def fake_post(self, url, json=None, **kwargs):
        return FakeResponse(200, {"response": "Hello, world."})

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    provider = _provider()
    assert provider.generate("hi") == "Hello, world."


def test_model_unavailable_raises_llm_unavailable_error(monkeypatch):
    def fake_post(self, url, json=None, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    provider = _provider()
    with pytest.raises(LLMUnavailableError):
        provider.generate("hi")


def test_timeout_raises_llm_unavailable_error(monkeypatch):
    def fake_post(self, url, json=None, **kwargs):
        raise httpx.ReadTimeout("timed out")

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    provider = _provider()
    with pytest.raises(LLMUnavailableError):
        provider.generate("hi")


def test_connectivity_failure_is_retried_three_times(monkeypatch):
    call_count = {"n": 0}

    def fake_post(self, url, json=None, **kwargs):
        call_count["n"] += 1
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    provider = _provider()
    with pytest.raises(LLMUnavailableError):
        provider.generate("hi")
    assert call_count["n"] == 3


def test_empty_response_raises_generation_error_not_silently_returned(monkeypatch):
    def fake_post(self, url, json=None, **kwargs):
        return FakeResponse(200, {"response": ""})

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    provider = _provider()
    with pytest.raises(LLMGenerationError):
        provider.generate("hi")


def test_malformed_json_response_raises_generation_error(monkeypatch):
    def fake_post(self, url, json=None, **kwargs):
        return FakeResponse(200, {"response": "not valid json {{{"})

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    provider = _provider()
    with pytest.raises(LLMGenerationError):
        provider.generate_json("hi")


def test_json_response_is_not_retried_on_malformed_output(monkeypatch):
    call_count = {"n": 0}

    def fake_post(self, url, json=None, **kwargs):
        call_count["n"] += 1
        return FakeResponse(200, {"response": "not json"})

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    provider = _provider()
    with pytest.raises(LLMGenerationError):
        provider.generate_json("hi")
    assert call_count["n"] == 1  # malformed output isn't a connectivity problem - don't waste retries


def test_falls_back_to_secondary_model_when_primary_unavailable(monkeypatch):
    calls = []

    def fake_post(self, url, json=None, **kwargs):
        calls.append(json["model"])
        if json["model"] == "primary-model":
            raise httpx.ConnectError("connection refused")
        return FakeResponse(200, {"response": "fallback worked"})

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    provider = _provider(model="primary-model", fallback_model="secondary-model")
    result = provider.generate("hi")

    assert result == "fallback worked"
    assert calls[-1] == "secondary-model"


def test_no_fallback_configured_raises_after_retries(monkeypatch):
    def fake_post(self, url, json=None, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    provider = _provider(fallback_model="")
    with pytest.raises(LLMUnavailableError):
        provider.generate("hi")


def test_is_available_true_when_reachable(monkeypatch):
    def fake_get(self, url, **kwargs):
        return FakeResponse(200, {})

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    assert _provider().is_available() is True


def test_is_available_false_when_unreachable(monkeypatch):
    def fake_get(self, url, **kwargs):
        raise httpx.ConnectError("nope")

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    assert _provider().is_available() is False


def _fake_404_response():
    request = httpx.Request("POST", "http://fake")
    return httpx.Response(404, request=request, json={"error": "model not found"})


def test_model_not_found_raises_actionable_error_listing_available_models(monkeypatch):
    def fake_post(self, url, json=None, **kwargs):
        return _fake_404_response()

    def fake_get(self, url, **kwargs):
        return FakeResponse(200, {"models": [{"name": "qwen2.5:3b-instruct"}, {"name": "nemotron-mini:latest"}]})

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    provider = _provider(model="qwen2.5")
    with pytest.raises(LLMModelNotFoundError) as exc_info:
        provider.generate("hi")
    message = str(exc_info.value)
    assert "qwen2.5" in message
    assert "qwen2.5:3b-instruct" in message
    assert "nemotron-mini:latest" in message


def test_model_not_found_degrades_gracefully_when_tags_endpoint_also_unreachable(monkeypatch):
    def fake_post(self, url, json=None, **kwargs):
        return _fake_404_response()

    def fake_get(self, url, **kwargs):
        raise httpx.ConnectError("also down")

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    provider = _provider(model="qwen2.5")
    with pytest.raises(LLMModelNotFoundError) as exc_info:
        provider.generate("hi")
    assert "Could not list available models" in str(exc_info.value)


def test_model_not_found_triggers_explicitly_configured_fallback(monkeypatch):
    calls = []

    def fake_post(self, url, json=None, **kwargs):
        calls.append(json["model"])
        if json["model"] == "primary-model":
            return _fake_404_response()
        return FakeResponse(200, {"response": "fallback worked"})

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    provider = _provider(model="primary-model", fallback_model="secondary-model")
    result = provider.generate("hi")

    assert result == "fallback worked"
    assert calls == ["primary-model", "secondary-model"]


def test_model_not_found_without_fallback_configured_never_guesses_a_substitute(monkeypatch):
    def fake_post(self, url, json=None, **kwargs):
        return _fake_404_response()

    def fake_get(self, url, **kwargs):
        return FakeResponse(200, {"models": []})

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    provider = _provider(fallback_model="")
    with pytest.raises(LLMModelNotFoundError):
        provider.generate("hi")


def test_model_not_found_is_a_generation_error_subclass_not_retried_by_connectivity_logic(monkeypatch):
    """A 404 is reachable-but-wrong-model, not a connectivity problem - it must not be
    retried three times the way ConnectError is (that would just be three identical 404s)."""
    call_count = {"n": 0}

    def fake_post(self, url, json=None, **kwargs):
        call_count["n"] += 1
        return _fake_404_response()

    def fake_get(self, url, **kwargs):
        return FakeResponse(200, {"models": []})

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    provider = _provider(fallback_model="")
    with pytest.raises(LLMGenerationError):
        provider.generate("hi")
    assert call_count["n"] == 1
