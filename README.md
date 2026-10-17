# XD AI

XD AI is a modular personal assistant for Windows. Version 0.2.0 adds explicit push-to-talk voice conversations to the existing Gemini-powered terminal while keeping speech recognition and speech output local.

## Status

**Version:** 0.2.0 — Voice Awakening

Current features:

- Futuristic Rich terminal interface
- Secure environment-based configuration
- Gemini integration through Google's official `google-genai` SDK
- SDK-native retries for rate limits and temporary service failures
- Per-session conversation context
- Friendly, credential-safe API error messages
- Safe discovery of compatible models with `/models`
- Terminal-controlled push-to-talk recording
- Selectable Windows microphone input
- Local English transcription through Faster-Whisper
- Local Windows speech through pyttsx3 and SAPI5
- Configurable speech rate and installed voice
- Shared conversation history across text and voice modes
- Unit tests that mock external APIs and audio hardware

## Vision

XD AI will grow incrementally into a permission-aware assistant for Windows and Android. Future work includes wake-word activation, approved application and browser actions, screen understanding with permission, and a secure Windows/Android connection. These capabilities are intentionally outside v0.2.0.

## Architecture

```text
src/xd_ai/
├── ai/           # Gemini client boundary and conversation history
├── core/         # Environment-based configuration
├── interface/    # Rich text and voice interaction loop
├── voice/        # Microphone, Faster-Whisper, and TTS adapters
└── __main__.py   # `python -m xd_ai` entry point
```

Keeping the provider and terminal interface behind separate modules lets future voice and automation features use the same controller without coupling them to Gemini or Rich.

## Requirements

- Python 3.11 or newer
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/)
- A Windows microphone and audio output device for voice mode
- Internet access on first transcription to download the selected Whisper model

## Installation

In PowerShell, from the project directory:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
Copy-Item .env.example .env
```

Open `.env` locally and set `GEMINI_API_KEY` to your key. `.env` is ignored by Git; never paste a key into source code, chat, issues, or commits.

## Usage

```powershell
python -m xd_ai
# or, after installation:
xd-ai
```

Text mode is active at startup. Type a question and press Enter.

Voice mode is always user initiated:

1. Type `/voice` to validate and activate the selected microphone.
2. Press Enter to start recording.
3. Speak, then press Enter to stop recording.
4. XD transcribes locally, asks Gemini, displays the answer, and speaks it locally.

Press `Ctrl+C` while recording to cancel or while XD is speaking to stop playback. Type `/text` to return to typed input.

Available commands:

- `/voice` — switch to push-to-talk mode
- `/text` — switch to typed input
- `/devices` — list input-capable audio devices
- `/mic <number or name>` — select a microphone for the current session
- `/mic default` — restore the Windows default microphone
- `/mic-test` — after confirmation, record for three seconds and show safe diagnostics
- `/voices` — list installed Windows speech voices
- `/models` — list Gemini text-generation models available to the API key
- `/clear` — clear shared text/voice conversation context
- `exit`, `quit`, or `/exit` — close XD and release audio resources

`GEMINI_MODEL` is optional and defaults to `gemini-3.1-flash-lite`. Set it in `.env` to change the model without editing source. Model availability and free-tier quotas are controlled by Google and may change.

```env
GEMINI_MODEL=gemini-3.5-flash-lite
```

The installed Google Gen AI SDK owns retry behavior. XD AI enables its native exponential-backoff policy for temporary failures such as HTTP 429 and 503; the application does not add a second retry loop. If those retries are exhausted, XD AI shows a friendly message. It also explains model, authentication, and permission errors without printing provider details or credentials.

## Voice configuration

All settings are optional and belong in the local `.env` file:

| Setting | Default | Purpose |
|---|---:|---|
| `XD_AI_MICROPHONE` | Windows default | Device number or name substring |
| `XD_AI_SAMPLE_RATE` | Device native rate | Optional capture sample rate |
| `XD_AI_WHISPER_MODEL` | `base.en` | Local English transcription model |
| `XD_AI_WHISPER_DEVICE` | `cpu` | Faster-Whisper compute device |
| `XD_AI_WHISPER_COMPUTE_TYPE` | `int8` | CPU-friendly inference mode |
| `XD_AI_TTS_RATE` | `175` | Speech rate in words per minute |
| `XD_AI_TTS_VOICE` | Windows default | Installed voice name or ID from `/voices` |

Windows can expose the same physical microphone through several audio endpoints. If
recording fails, run `/devices`, select the intended endpoint with `/mic <number>`,
and run `/mic-test`. The diagnostic reports the selected microphone, elapsed and
captured duration, audio-frame count, and callback count. It does not save, print,
transcribe, or upload the captured audio. To make the selection persistent, put the
working device number in `XD_AI_MICROPHONE` in `.env`.

`base.en` is intentionally modest for the first voice milestone. A larger `.en` model can improve recognition at the cost of download size, memory, and response time.

XD AI currently constrains PyAV to versions below 19 because Faster-Whisper 1.2.1 uses an audio-decoder argument removed in PyAV 19. Remove this compatibility constraint only after upgrading to a Faster-Whisper release that supports PyAV 19.

## Security

- Credentials are read only from environment variables or a local `.env` file.
- XD AI does not fabricate an AI response when no key is configured.
- Microphone recording begins only after `/voice` and an explicit Enter press.
- Recordings remain in memory, are not saved, and are never sent to a speech service.
- Faster-Whisper performs recognition locally; only transcribed text is sent to Gemini.
- Version 0.2.0 does not use wake words, global keyboard hooks, shell execution, desktop control, or screen capture.
- Future automation must use explicit approvals and validation before it is enabled.

## Development

Run the test suite:

```powershell
pytest
```

## Roadmap

1. v0.1.0 — terminal chat and Gemini integration
2. v0.2.0 — explicit push-to-talk, local speech recognition, and local speech output
3. Wake-word evaluation with clear privacy controls
4. Approved Windows application and browser actions
5. Context persistence and permission-aware screen assistance
6. Secure Windows-to-Android communication and Termux support

## License

This repository is released under the MIT License. Update the copyright holder in `LICENSE` before publishing if needed.

