"""Rich-powered text and voice terminal interface for XD AI."""

from __future__ import annotations

import time

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.text import Text

from xd_ai import __version__
from xd_ai.ai.gemini import GeminiConfigurationError, GeminiService, GeminiServiceError
from xd_ai.core.config import Settings
from xd_ai.voice import (
    FasterWhisperTranscriber,
    MicrophoneError,
    MicrophoneRecorder,
    Pyttsx3Speaker,
    RecordingDiagnostics,
    SpeechInterruptedError,
    SpeechNotRecognizedError,
    TextToSpeechError,
    TranscriptionError,
)

EXIT_COMMANDS = {"exit", "quit", "/exit"}


class TerminalApp:
    """Interactive text and push-to-talk interface for XD AI."""

    def __init__(
        self,
        settings: Settings,
        service: GeminiService,
        console: Console | None = None,
        recorder: MicrophoneRecorder | None = None,
        transcriber: FasterWhisperTranscriber | None = None,
        speaker: Pyttsx3Speaker | None = None,
    ) -> None:
        self._settings = settings
        self._service = service
        self._console = console or Console()
        self._recorder = recorder
        self._transcriber = transcriber
        self._speaker = speaker
        self._mode = "text"

    def run(self) -> None:
        self._show_banner()
        self._show_status()
        try:
            self._run_loop()
        finally:
            self._close_voice_resources()

    def _run_loop(self) -> None:
        while True:
            try:
                user_text = self._prompt().strip()
            except (EOFError, KeyboardInterrupt):
                self._console.print("\n[dim]XD AI session closed.[/dim]")
                return

            if not user_text:
                if self._mode == "voice":
                    self._run_voice_turn()
                continue
            command = user_text.lower()
            if command in EXIT_COMMANDS:
                self._console.print("[dim]Goodbye.[/dim]")
                return
            if command == "/voice":
                self._switch_to_voice_mode()
                continue
            if command == "/text":
                self._mode = "text"
                self._console.print("[green][MODE][/green] Text mode active.")
                continue
            if command == "/clear":
                self._service.clear_conversation()
                self._console.print("[green]Conversation context cleared.[/green]")
                continue
            if command == "/models":
                self._show_available_models()
                continue
            if command == "/devices":
                self._show_microphones()
                continue
            if command == "/mic-test":
                self._run_microphone_diagnostic()
                continue
            if command == "/voices":
                self._show_tts_voices()
                continue
            if command == "/mic" or command.startswith("/mic "):
                self._select_microphone(user_text)
                continue

            if self._mode == "voice":
                self._console.print(
                    "[yellow]Voice mode is active.[/yellow] Press Enter to record, "
                    "or type /text to return to typing."
                )
                continue

            self._run_text_turn(user_text)

    def _prompt(self) -> str:
        if self._mode == "voice":
            return Prompt.ask(
                "[bold cyan]VOICE[/bold cyan] "
                "[dim]Press Enter to record, or enter a command[/dim]"
            )
        return Prompt.ask("[bold cyan]You[/bold cyan]")

    def _run_text_turn(self, user_text: str) -> None:
        with self._console.status("[cyan][AI] Generating response...[/cyan]"):
            try:
                answer = self._service.ask(user_text)
            except GeminiConfigurationError as error:
                self._console.print(f"[yellow]Configuration:[/yellow] {error}")
                return
            except GeminiServiceError as error:
                self._console.print(f"[red]Gemini error:[/red] {error}")
                return

        self._show_answer(answer)

    def _run_voice_turn(self) -> None:
        if not self._voice_components_available():
            return
        assert self._recorder is not None
        assert self._transcriber is not None
        assert self._speaker is not None

        started = False
        try:
            device = self._recorder.start()
            started = True
            self._console.print(
                "[dim cyan][VOICE] Recording started:[/dim cyan] "
                f"{device.name} [dim](device {device.index}, "
                f"{device.default_sample_rate} Hz capability)[/dim]"
            )
            self._console.print(
                "[bold green][LISTENING][/bold green] Recording... "
                "[dim]Press Enter to stop; Ctrl+C cancels.[/dim]"
            )
            if not self._recorder.wait_for_first_frame(timeout=1.0):
                self._recorder.cancel()
                raise MicrophoneError(
                    "The microphone stream started, but Windows delivered no audio "
                    "callbacks within 1 second. Check the selected input device and "
                    "microphone privacy permissions."
                )
            try:
                Prompt.ask("[dim]Recording[/dim]")
            except (EOFError, KeyboardInterrupt):
                diagnostics = self._recorder.cancel()
                self._show_recording_diagnostics(diagnostics)
                self._console.print("[yellow][VOICE] Recording cancelled.[/yellow]")
                return
            recording = self._recorder.stop()
        except MicrophoneError as error:
            if started and self._recorder.is_recording:
                self._recorder.cancel()
            self._show_recording_diagnostics(self._recorder.last_diagnostics)
            self._console.print(f"[red][VOICE] Microphone error:[/red] {error}")
            return

        self._show_recording_diagnostics(self._recorder.last_diagnostics)
        self._console.print(
            "[dim][VOICE] Recording completed: "
            f"{recording.duration_seconds:.2f}s, {recording.sample_rate} Hz, "
            f"{recording.channels} channel, {recording.sample_width * 8}-bit PCM.[/dim]"
        )
        self._console.print("[cyan][PROCESSING] Transcribing speech...[/cyan]")
        try:
            transcript = self._transcriber.transcribe(
                recording, on_diagnostic=self._show_voice_diagnostic
            )
        except SpeechNotRecognizedError as error:
            self._console.print(f"[yellow][VOICE][/yellow] {error}")
            return
        except TranscriptionError as error:
            self._console.print(f"[red][VOICE] Transcription error:[/red] {error}")
            return

        self._console.print(
            Panel(
                Text(transcript),
                title="[bold cyan]You (voice)[/bold cyan]",
                border_style="cyan",
            )
        )

        with self._console.status("[cyan][AI] Generating response...[/cyan]"):
            try:
                answer = self._service.ask(transcript)
            except GeminiConfigurationError as error:
                self._console.print(f"[yellow]Configuration:[/yellow] {error}")
                return
            except GeminiServiceError as error:
                self._console.print(f"[red]Gemini error:[/red] {error}")
                return

        self._show_answer(answer)
        self._console.print(
            "[bold magenta][SPEAKING][/bold magenta] XD responding... "
            "[dim]Press Ctrl+C to stop speech.[/dim]"
        )
        try:
            self._speaker.speak(answer)
        except SpeechInterruptedError:
            self._console.print("[yellow][SPEAKING] Speech stopped.[/yellow]")
        except TextToSpeechError as error:
            self._console.print(f"[red][VOICE] Speech output error:[/red] {error}")

    def _switch_to_voice_mode(self) -> None:
        if not self._voice_components_available():
            return
        assert self._recorder is not None
        try:
            device = self._recorder.validate_device()
        except MicrophoneError as error:
            self._console.print(f"[red][VOICE] Microphone error:[/red] {error}")
            return
        self._mode = "voice"
        self._console.print(
            Text.assemble(
                ("[VOICE] ", "bold green"),
                "Microphone ready: ",
                (device.name, "cyan"),
            )
        )

    def _show_microphones(self) -> None:
        if self._recorder is None:
            self._console.print("[red][VOICE] Microphone support is unavailable.[/red]")
            return
        try:
            devices = self._recorder.list_input_devices()
        except MicrophoneError as error:
            self._console.print(f"[red][VOICE] Microphone error:[/red] {error}")
            return
        if not devices:
            self._console.print("[yellow][VOICE] No input devices were found.[/yellow]")
            return
        lines = [
            f"{device.index}: {device.name} "
            f"({device.channels} ch, {device.default_sample_rate} Hz)"
            for device in devices
        ]
        self._console.print(
            Panel(
                Text("\n".join(lines)),
                title="[bold cyan]Microphones[/bold cyan]",
                subtitle="Select with /mic <number or name>",
                border_style="cyan",
            )
        )

    def _select_microphone(self, command: str) -> None:
        if self._recorder is None:
            self._console.print("[red][VOICE] Microphone support is unavailable.[/red]")
            return
        selector_text = command.partition(" ")[2].strip()
        if not selector_text:
            self._console.print("[yellow]Usage: /mic <device number or name>[/yellow]")
            return
        if selector_text.casefold() == "default":
            selector: int | str | None = None
        else:
            try:
                selector = int(selector_text)
            except ValueError:
                selector = selector_text
        try:
            device = self._recorder.select_device(selector)
        except MicrophoneError as error:
            self._console.print(f"[red][VOICE] Microphone error:[/red] {error}")
            return
        self._console.print(
            Text.assemble("[VOICE] Selected microphone: ", (device.name, "cyan"))
        )

    def _run_microphone_diagnostic(self) -> None:
        """Capture three seconds once, report counters, then discard the audio."""
        if self._recorder is None:
            self._console.print("[red][VOICE] Microphone support is unavailable.[/red]")
            return
        if not Confirm.ask(
            "Record a private, local 3-second microphone diagnostic?",
            default=False,
        ):
            self._console.print("[dim][VOICE] Microphone diagnostic cancelled.[/dim]")
            return

        started = False
        try:
            device = self._recorder.start()
            started = True
            self._console.print(
                Text.assemble(
                    ("[VOICE] Recording started: ", "bold green"),
                    (device.name, "cyan"),
                )
            )
            self._console.print(
                "[bold green][LISTENING][/bold green] Diagnostic recording for 3 seconds..."
            )
            time.sleep(3.0)
            self._recorder.stop()
        except KeyboardInterrupt:
            diagnostics = self._recorder.cancel()
            self._show_recording_diagnostics(diagnostics)
            self._console.print("[yellow][VOICE] Microphone diagnostic cancelled.[/yellow]")
            return
        except MicrophoneError as error:
            if started and self._recorder.is_recording:
                self._recorder.cancel()
            self._show_recording_diagnostics(self._recorder.last_diagnostics)
            self._console.print(f"[red][VOICE] Microphone error:[/red] {error}")
            return

        self._show_recording_diagnostics(self._recorder.last_diagnostics)
        self._console.print(
            "[green][VOICE] Microphone diagnostic completed.[/green] "
            "[dim]Captured audio was discarded and was not transcribed or uploaded.[/dim]"
        )

    def _show_tts_voices(self) -> None:
        if self._speaker is None:
            self._console.print("[red][VOICE] Speech output support is unavailable.[/red]")
            return
        try:
            voices = self._speaker.list_voices()
        except TextToSpeechError as error:
            self._console.print(f"[red][VOICE] Speech output error:[/red] {error}")
            return
        lines = [f"{voice.name}\n  {voice.id}" for voice in voices]
        self._console.print(
            Panel(
                Text("\n".join(lines)),
                title="[bold magenta]Installed speech voices[/bold magenta]",
                subtitle="Set XD_AI_TTS_VOICE in .env",
                border_style="magenta",
            )
        )

    def _voice_components_available(self) -> bool:
        if self._recorder and self._transcriber and self._speaker:
            return True
        self._console.print(
            "[red][VOICE] Voice components are unavailable. Reinstall project dependencies.[/red]"
        )
        return False

    def _show_voice_diagnostic(self, message: str) -> None:
        self._console.print(Text.assemble(("[VOICE] ", "dim cyan"), (message, "dim")))

    def _show_recording_diagnostics(
        self, diagnostics: RecordingDiagnostics | None
    ) -> None:
        if diagnostics is None:
            return
        self._console.print(
            "[dim cyan][VOICE] Recording stopped:[/dim cyan] "
            f"device={diagnostics.device.name}; "
            f"elapsed={diagnostics.elapsed_seconds:.2f}s; "
            f"audio={diagnostics.audio_duration_seconds:.2f}s; "
            f"frames={diagnostics.audio_frame_count}; "
            f"callbacks={diagnostics.callback_count}."
        )

    def _close_voice_resources(self) -> None:
        if self._recorder is not None:
            self._recorder.close()
        if self._speaker is not None:
            self._speaker.close()

    def _show_answer(self, answer: str) -> None:
        self._console.print(
            Panel(
                answer,
                title="[bold magenta]XD AI[/bold magenta]",
                border_style="magenta",
            )
        )

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
        subtitle = Text(f"INTELLIGENT PERSONAL ASSISTANT  |  v{__version__}", style="dim")
        self._console.print(Panel.fit(Text.assemble(title, "\n", subtitle), border_style="cyan"))
        self._console.print(
            "[dim]Commands: /voice, /text, /devices, /mic, /voices, /models, "
            "/mic-test, /clear, exit[/dim]"
        )

    def _show_status(self) -> None:
        if self._settings.has_gemini_credentials:
            self._console.print(
                f"[green]* Gemini configured[/green] "
                f"[dim]model: {self._settings.gemini_model}[/dim]"
            )
        else:
            self._console.print(
                "[yellow]* Gemini not configured[/yellow] "
                "[dim]Add GEMINI_API_KEY to .env to enable live responses.[/dim]"
            )

