"""Rich-powered terminal interface for the initial XD AI experience."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

from xd_ai import __version__
from xd_ai.ai.gemini import GeminiConfigurationError, GeminiService, GeminiServiceError
from xd_ai.core.config import Settings

EXIT_COMMANDS = {"exit", "quit", "/exit"}


class TerminalApp:
    """Interactive text conversation loop with no desktop automation capabilities."""

    def __init__(self, settings: Settings, service: GeminiService, console: Console | None = None) -> None:
        self._settings = settings
        self._service = service
        self._console = console or Console()

    def run(self) -> None:
        self._show_banner()
        self._show_status()
        while True:
            try:
                user_text = Prompt.ask("[bold cyan]You[/bold cyan]").strip()
            except (EOFError, KeyboardInterrupt):
                self._console.print("\n[dim]XD AI session closed.[/dim]")
                return

            if not user_text:
                continue
            if user_text.lower() in EXIT_COMMANDS:
                self._console.print("[dim]Goodbye.[/dim]")
                return
            if user_text.lower() == "/clear":
                self._service.clear_conversation()
                self._console.print("[green]Conversation context cleared.[/green]")
                continue
            if user_text.lower() == "/models":
                self._show_available_models()
                continue

            with self._console.status("[cyan]XD is thinking...[/cyan]"):
                try:
                    answer = self._service.ask(user_text)
                except GeminiConfigurationError as error:
                    self._console.print(f"[yellow]Configuration:[/yellow] {error}")
                    continue
                except GeminiServiceError as error:
                    self._console.print(f"[red]Gemini error:[/red] {error}")
                    continue

            self._console.print(Panel(answer, title="[bold magenta]XD AI[/bold magenta]", border_style="magenta"))

    def _show_available_models(self) -> None:
        with self._console.status("[cyan]Checking available Gemini models...[/cyan]"):
            try:
                models = self._service.list_available_models()
            except GeminiConfigurationError as error:
                self._console.print(f"[yellow]Configuration:[/yellow] {error}")
                return
            except GeminiServiceError as error:
                self._console.print(f"[red]Gemini error:[/red] {error}")
                return

        if not models:
            self._console.print("[yellow]No text-generation models were returned.[/yellow]")
            return

        model_list = Text("\n".join(models))
        self._console.print(
            Panel(
                model_list,
                title="[bold cyan]Available text models[/bold cyan]",
                subtitle="Set GEMINI_MODEL in .env",
                border_style="cyan",
            )
        )

    def _show_banner(self) -> None:
        title = Text("XD AI", style="bold bright_cyan")
        subtitle = Text(f"INTELLIGENT PERSONAL ASSISTANT  •  v{__version__}", style="dim")
        self._console.print(Panel.fit(Text.assemble(title, "\n", subtitle), border_style="cyan"))
        self._console.print(
            "[dim]Type /models to list compatible models, /clear to reset context, "
            "or exit to close.[/dim]"
        )

    def _show_status(self) -> None:
        if self._settings.has_gemini_credentials:
            self._console.print(
                f"[green]● Gemini configured[/green] [dim]model: {self._settings.gemini_model}[/dim]"
            )
        else:
            self._console.print(
                "[yellow]● Gemini not configured[/yellow] "
                "[dim]Add GEMINI_API_KEY to .env to enable live responses.[/dim]"
            )

