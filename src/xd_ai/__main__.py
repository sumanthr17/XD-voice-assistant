"""Command-line entry point for XD AI."""

from xd_ai.ai.gemini import GeminiService
from xd_ai.core.config import load_settings
from xd_ai.interface.terminal import TerminalApp


def main() -> None:
    """Launch the terminal assistant."""
    settings = load_settings()
    TerminalApp(settings=settings, service=GeminiService(settings)).run()


if __name__ == "__main__":
    main()

