from xd_ai.core.config import DEFAULT_HISTORY_TURNS, load_settings


def test_load_settings_reads_environment(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "custom-model")
    monkeypatch.setenv("XD_AI_MAX_HISTORY_TURNS", "3")

    settings = load_settings()

    assert settings.gemini_api_key == "test-key"
    assert settings.gemini_model == "custom-model"
    assert settings.max_history_turns == 3


def test_load_settings_trims_selected_model(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_MODEL", "  gemini-selected  ")

    assert load_settings().gemini_model == "gemini-selected"


def test_load_settings_uses_default_for_invalid_history_limit(monkeypatch) -> None:
    monkeypatch.setenv("XD_AI_MAX_HISTORY_TURNS", "zero")

    assert load_settings().max_history_turns == DEFAULT_HISTORY_TURNS

