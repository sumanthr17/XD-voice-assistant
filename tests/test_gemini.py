from types import SimpleNamespace
from unittest.mock import patch

import pytest

from xd_ai.ai.gemini import (
    GeminiConfigurationError,
    GeminiService,
    GeminiServiceError,
)
from xd_ai.core.config import Settings


class FakeModels:
    def __init__(
        self,
        *,
        error: Exception | None = None,
        available_models: list[SimpleNamespace] | None = None,
    ) -> None:
        self.calls: list[dict[str, object]] = []
        self.error = error
        self.available_models = available_models or []

    def generate_content(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(text="A real-looking response supplied only by this unit-test double.")

    def list(self) -> list[SimpleNamespace]:
        if self.error:
            raise self.error
        return self.available_models


class FakeApiError(Exception):
    def __init__(self, code: int, message: str = "provider detail") -> None:
        super().__init__(message)
        self.code = code


def test_service_sends_history_and_retains_successful_turns() -> None:
    models = FakeModels()
    client = SimpleNamespace(models=models)
    service = GeminiService(Settings("test-key", max_history_turns=2), client=client)

    assert "unit-test double" in service.ask("First question")
    service.ask("Second question")

    latest_contents = models.calls[-1]["contents"]
    assert [item["role"] for item in latest_contents] == ["user", "model", "user"]


def test_service_uses_configured_model() -> None:
    models = FakeModels()
    service = GeminiService(
        Settings("test-key", gemini_model="gemini-selected"),
        client=SimpleNamespace(models=models),
    )

    service.ask("Which model is selected?")

    assert models.calls[0]["model"] == "gemini-selected"


def test_service_refuses_to_make_request_without_api_key() -> None:
    service = GeminiService(Settings(None))

    with pytest.raises(GeminiConfigurationError, match="GEMINI_API_KEY"):
        service.ask("Hello")


def test_clear_conversation_removes_prior_context() -> None:
    models = FakeModels()
    service = GeminiService(Settings("test-key"), client=SimpleNamespace(models=models))
    service.ask("Remember this")
    service.clear_conversation()
    service.ask("Start again")

    contents = models.calls[-1]["contents"]
    assert contents == [{"role": "user", "parts": [{"text": "Start again"}]}]


@pytest.mark.parametrize(
    ("status_code", "expected_text"),
    [
        (503, "temporarily unavailable after automatic retries"),
        (429, "rate limit was reached after automatic retries"),
        (404, "configured model 'missing-model' is unavailable"),
        (401, "authentication failed"),
        (403, "denied this request"),
    ],
)
def test_service_translates_api_errors(status_code: int, expected_text: str) -> None:
    models = FakeModels(error=FakeApiError(status_code, "secret provider detail"))
    service = GeminiService(
        Settings("test-key", gemini_model="missing-model"),
        client=SimpleNamespace(models=models),
    )

    with pytest.raises(GeminiServiceError) as raised:
        service.ask("Hello")

    assert raised.value.status_code == status_code
    assert expected_text in str(raised.value)
    assert "secret provider detail" not in str(raised.value)


def test_list_available_models_returns_only_generate_content_models() -> None:
    models = FakeModels(
        available_models=[
            SimpleNamespace(
                name="models/gemini-text", supported_actions=["generateContent"]
            ),
            SimpleNamespace(name="models/gemini-embed", supported_actions=["embedContent"]),
            SimpleNamespace(
                name="models/gemini-other-text", supported_actions=["generateContent"]
            ),
        ]
    )
    service = GeminiService(
        Settings("test-key"), client=SimpleNamespace(models=models)
    )

    assert service.list_available_models() == ["gemini-other-text", "gemini-text"]


def test_client_enables_sdk_native_retries() -> None:
    service = GeminiService(Settings("test-key"))

    with patch("google.genai.Client") as client_class:
        service._create_client()

    http_options = client_class.call_args.kwargs["http_options"]
    assert http_options.retry_options is not None
    assert http_options.retry_options.attempts is None

