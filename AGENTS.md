# XD AI contributor guidance

- Use Python 3.11+ and keep the `src/xd_ai` package modular.
- Never commit `.env`, API keys, credentials, private logs, or personal data.
- Keep provider SDK calls isolated in `xd_ai.ai`; keep terminal rendering isolated in `xd_ai.interface`.
- Do not add desktop automation, shell execution, audio recording, or screen capture without an explicit feature request and a permission/approval design.
- Add or update tests for behavior changes. Mock external services; do not require a real API key in tests.
- Prefer focused, typed, maintainable changes. Run `pytest` before handing off work.

