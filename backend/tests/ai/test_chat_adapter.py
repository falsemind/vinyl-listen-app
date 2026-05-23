import json
from io import BytesIO
from urllib.error import URLError

import pytest

from app.ai.chat_adapter import (
    DISABLED_AI_CHAT_CONTENT,
    AiChatAdapterError,
    DisabledAiChatAdapter,
    OpenAiCompatibleChatAdapter,
    build_ai_chat_adapter,
)
from app.core.config import Settings


class FakeHttpResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.body = BytesIO(json.dumps(payload).encode("utf-8"))

    def __enter__(self) -> "FakeHttpResponse":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body.read()


@pytest.fixture(autouse=True)
def clear_ai_chat_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "AI_CHAT_ENABLED",
        "AI_CHAT_BASE_URL",
        "AI_CHAT_ENDPOINT_PATH",
        "AI_CHAT_MODEL",
        "AI_CHAT_API_KEY",
        "AI_CHAT_TIMEOUT_SECONDS",
        "AI_CHAT_TEMPERATURE",
    ):
        monkeypatch.delenv(name, raising=False)


def make_settings(**overrides: object) -> Settings:
    values = {
        "database_url": "postgresql://test:test@localhost/testdb",
        "discogs_base_url": "https://api.discogs.com",
        "ai_chat_enabled": False,
        "ai_chat_base_url": None,
        "ai_chat_model": None,
        "ai_chat_api_key": None,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_build_ai_chat_adapter_returns_disabled_when_chat_is_off() -> None:
    adapter = build_ai_chat_adapter(make_settings(ai_chat_enabled=False))

    assert isinstance(adapter, DisabledAiChatAdapter)


def test_build_ai_chat_adapter_returns_disabled_when_required_provider_config_is_missing() -> None:
    adapter = build_ai_chat_adapter(make_settings(ai_chat_enabled=True, ai_chat_base_url="http://localhost:1234"))

    assert isinstance(adapter, DisabledAiChatAdapter)


def test_openai_compatible_adapter_repr_hides_api_key() -> None:
    adapter = OpenAiCompatibleChatAdapter(
        base_url="http://localhost:1234",
        endpoint_path="/api/v1/chat",
        model="local-model",
        api_key="secret-key",
    )

    assert "secret-key" not in repr(adapter)


def test_disabled_adapter_returns_safe_content() -> None:
    adapter = DisabledAiChatAdapter()

    reply = adapter.generate_reply(
        message="What should I listen to?",
        conversation_id="local-single-thread",
    )

    assert reply.content == DISABLED_AI_CHAT_CONTENT
    assert reply.used_tools == []


def test_lm_studio_native_adapter_posts_input_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request: object, timeout: float) -> FakeHttpResponse:
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeHttpResponse(
            {
                "output": [
                    {"type": "reasoning", "content": "Thinking..."},
                    {"type": "message", "content": "Play your highest-rated ambient record."},
                ]
            }
        )

    monkeypatch.setattr("app.ai.chat_adapter.urlopen", fake_urlopen)
    adapter = OpenAiCompatibleChatAdapter(
        base_url="http://localhost:1234",
        endpoint_path="/api/v1/chat",
        model="local-model",
        api_key="test-key",
        timeout_seconds=12.5,
        temperature=0.1,
    )

    reply = adapter.generate_reply(
        message="Recommend a known release",
        conversation_id="local-single-thread",
        client_context={"timezone": "America/Los_Angeles"},
    )

    assert reply.content == "Play your highest-rated ambient record."
    assert captured["url"] == "http://localhost:1234/api/v1/chat"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["timeout"] == 12.5
    assert captured["payload"]["model"] == "local-model"
    assert captured["payload"]["temperature"] == 0.1
    assert "Recommend a known release" in captured["payload"]["input"]
    assert "messages" not in captured["payload"]


def test_openai_compatible_adapter_posts_chat_completion_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request: object, timeout: float) -> FakeHttpResponse:
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        _ = timeout
        return FakeHttpResponse({"choices": [{"message": {"content": "Play your highest-rated ambient record."}}]})

    monkeypatch.setattr("app.ai.chat_adapter.urlopen", fake_urlopen)
    adapter = OpenAiCompatibleChatAdapter(
        base_url="http://localhost:1234/v1",
        endpoint_path="/chat/completions",
        model="local-model",
    )

    reply = adapter.generate_reply(
        message="Recommend a known release",
        conversation_id="local-single-thread",
    )

    assert reply.content == "Play your highest-rated ambient record."
    assert captured["url"] == "http://localhost:1234/v1/chat/completions"
    assert captured["payload"]["messages"][-1] == {"role": "user", "content": "Recommend a known release"}
    assert "input" not in captured["payload"]


def test_openai_compatible_adapter_raises_on_provider_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: object, timeout: float) -> FakeHttpResponse:
        _ = request, timeout
        raise URLError("connection refused")

    monkeypatch.setattr("app.ai.chat_adapter.urlopen", fake_urlopen)
    adapter = OpenAiCompatibleChatAdapter(
        base_url="http://localhost:1234",
        endpoint_path="/api/v1/chat",
        model="local-model",
    )

    with pytest.raises(AiChatAdapterError):
        adapter.generate_reply(message="Hello", conversation_id="local-single-thread")


def test_openai_compatible_adapter_raises_on_missing_response_content(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: object, timeout: float) -> FakeHttpResponse:
        _ = request, timeout
        return FakeHttpResponse({"choices": []})

    monkeypatch.setattr("app.ai.chat_adapter.urlopen", fake_urlopen)
    adapter = OpenAiCompatibleChatAdapter(
        base_url="http://localhost:1234",
        endpoint_path="/api/v1/chat",
        model="local-model",
    )

    with pytest.raises(AiChatAdapterError):
        adapter.generate_reply(message="Hello", conversation_id="local-single-thread")


def test_openai_compatible_adapter_accepts_lm_studio_output_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: object, timeout: float) -> FakeHttpResponse:
        _ = request, timeout
        return FakeHttpResponse(
            {
                "output": [
                    {"type": "reasoning", "content": "Thinking..."},
                    {"type": "message", "content": "Your recent collection notes point to dub techno."},
                ]
            }
        )

    monkeypatch.setattr("app.ai.chat_adapter.urlopen", fake_urlopen)
    adapter = OpenAiCompatibleChatAdapter(
        base_url="http://localhost:1234",
        endpoint_path="/api/v1/chat",
        model="local-model",
    )

    reply = adapter.generate_reply(message="What style is common?", conversation_id="local-single-thread")

    assert reply.content == "Your recent collection notes point to dub techno."
