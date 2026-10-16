# XD AI

XD AI is a modular, text-first personal assistant for Windows. Version 0.1.0 provides a safe terminal conversation interface backed by the Gemini API. It is the foundation for later voice, approved desktop automation, screen-aware assistance, and Android work.

## Status

**Version:** 0.1.0 — initial text assistant

Current features:

- Futuristic Rich terminal interface
- Secure environment-based configuration
- Gemini integration through Google's official `google-genai` SDK
- SDK-native retries for rate limits and temporary service failures
- Per-session conversation context
- Friendly, credential-safe API error messages
- Safe discovery of compatible models with `/models`
- Unit tests that mock the external client

## Vision

XD AI will grow incrementally into a voice-enabled, permission-aware assistant for Windows and Android. Future work includes push-to-talk, a wake word, text-to-speech, approved application and browser actions, screen understanding with permission, and a secure Windows/Android connection. These capabilities are intentionally not part of v0.1.0.

## Architecture

```text
src/xd_ai/
├── ai/           # Gemini client boundary and conversation history
├── core/         # Configuration and application controller
├── interface/    # Terminal presentation and input loop
└── __main__.py   # `python -m xd_ai` entry point
```

Keeping the provider and terminal interface behind separate modules lets future voice and automation features use the same controller without coupling them to Gemini or Rich.

## Requirements

- Python 3.11 or newer
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/)

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

Type a question and press Enter. Use `/models` to list models available to your API key, `/clear` to remove local conversation context, and `exit`, `quit`, or `/exit` to close the program.

`GEMINI_MODEL` is optional and defaults to `gemini-3.1-flash-lite`. Set it in `.env` to change the model without editing source. Model availability and free-tier quotas are controlled by Google and may change.

```env
GEMINI_MODEL=gemini-3.5-flash-lite
```

The installed Google Gen AI SDK owns retry behavior. XD AI enables its native exponential-backoff policy for temporary failures such as HTTP 429 and 503; the application does not add a second retry loop. If those retries are exhausted, XD AI shows a friendly message. It also explains model, authentication, and permission errors without printing provider details or credentials.

## Security

- Credentials are read only from environment variables or a local `.env` file.
- XD AI does not fabricate an AI response when no key is configured.
- Version 0.1.0 does not execute shell commands, control applications, or collect screen/audio data.
- Future automation must use explicit approvals and validation before it is enabled.

## Development

Run the test suite:

```powershell
pytest
```

## Roadmap

1. v0.1.0 — terminal chat and Gemini integration
2. Voice input/output behind clear permissions
3. Approved Windows application and browser actions
4. Context persistence and permission-aware screen assistance
5. Secure Windows-to-Android communication and Termux support

## License

This repository is released under the MIT License. Update the copyright holder in `LICENSE` before publishing if needed.

