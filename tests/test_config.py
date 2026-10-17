from xd_ai.core.config import (
    DEFAULT_HISTORY_TURNS,
    DEFAULT_TTS_RATE,
    DEFAULT_WHISPER_MODEL,
    load_settings,
)


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


def test_load_settings_reads_voice_configuration(monkeypatch) -> None:
    monkeypatch.setenv("XD_AI_MICROPHONE", "2")
    monkeypatch.setenv("XD_AI_SAMPLE_RATE", "16000")
    monkeypatch.setenv("XD_AI_WHISPER_MODEL", "small.en")
    monkeypatch.setenv("XD_AI_WHISPER_DEVICE", "cpu")
    monkeypatch.setenv("XD_AI_WHISPER_COMPUTE_TYPE", "int8")
    monkeypatch.setenv("XD_AI_TTS_RATE", "165")
    monkeypatch.setenv("XD_AI_TTS_VOICE", "Calm Voice")

    settings = load_settings()

    assert settings.microphone_device == 2
    assert settings.audio_sample_rate == 16_000
    assert settings.whisper_model == "small.en"
    assert settings.whisper_device == "cpu"
    assert settings.whisper_compute_type == "int8"
    assert settings.tts_rate == 165
    assert settings.tts_voice == "Calm Voice"


def test_load_settings_uses_safe_voice_defaults(monkeypatch) -> None:
    for name in (
        "XD_AI_MICROPHONE",
        "XD_AI_SAMPLE_RATE",
        "XD_AI_WHISPER_MODEL",
        "XD_AI_TTS_VOICE",
    ):
        monkeypatch.setenv(name, "")
    monkeypatch.setenv("XD_AI_TTS_RATE", "invalid")

    settings = load_settings()

    assert settings.microphone_device is None
    assert settings.audio_sample_rate is None
    assert settings.whisper_model == DEFAULT_WHISPER_MODEL
    assert settings.tts_rate == DEFAULT_TTS_RATE
    assert settings.tts_voice is None

