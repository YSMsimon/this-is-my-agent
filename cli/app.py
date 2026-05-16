import io
import itertools
import os
import re
import sys

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import RichLog, Input, Button, Label, Static, OptionList
from textual.widgets.option_list import Option
from textual.screen import ModalScreen
from textual.containers import Vertical, Horizontal
from rich.markdown import Markdown
from rich.text import Text

from cli.completions import SLASH_COMMANDS

_ANSI = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
_FRAMES = '⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
_BRAILLE = set('⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏')


# ── live stdout bridge ────────────────────────────────────────────────────────

class _LiveWriter:
    """
    Replaces sys.stdout during agent runs. Each complete line is stripped of
    ANSI codes and written to the RichLog immediately, so deep-mode progress
    and token summaries appear in real-time. Spinner overwrite sequences
    (\\r-prefixed) are silently dropped.
    """

    def __init__(self, log: RichLog) -> None:
        self._log = log
        self._buf = ""

    def write(self, text: str) -> None:
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            self._emit(line)

    def _emit(self, line: str) -> None:
        # carriage-return overwrite (spinner / clear-line sequences)
        if "\r" in line:
            line = line.rsplit("\r", 1)[-1]
        clean = _ANSI.sub("", line).rstrip()
        if not clean or any(c in clean for c in _BRAILLE):
            return
        self._log.write(Text(clean, style="dim"))

    def flush(self) -> None:
        if self._buf.strip():
            self._emit(self._buf)
        self._buf = ""


# ── confirm modal ─────────────────────────────────────────────────────────────

class ConfirmScreen(ModalScreen):
    DEFAULT_CSS = """
    ConfirmScreen { align: center middle; }
    #dialog {
        background: #262626;
        border: round #555555;
        padding: 1 3;
        width: auto;
        min-width: 44;
        max-width: 70;
        height: auto;
    }
    #question { color: white; margin-bottom: 1; width: auto; }
    #btn-row  { height: auto; align-horizontal: center; }
    Button    { margin: 0 1; }
    """

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(self._message, id="question")
            with Horizontal(id="btn-row"):
                yield Button("Yes (Y)", id="yes", variant="error")
                yield Button("No (N)",  id="no",  variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")

    def on_key(self, event) -> None:
        if event.key == "y":
            self.dismiss(True)
        elif event.key in ("n", "escape"):
            self.dismiss(False)


# ── main app ──────────────────────────────────────────────────────────────────

class AgentApp(App):
    """
    Architecture follows Oterm / Elia patterns:
      - native Textual async workers (no redirect_stdout buffering)
      - real-time _LiveWriter pipes prints to RichLog line by line
      - clipboard keybinding (Ctrl+Y) instead of ENABLE_MOUSE=False
      - OptionList autocomplete with keyboard nav (Up/Down/Tab/Escape)
    """

    BINDINGS = [
        Binding("ctrl+y", "copy_response", "Copy last response", show=False),
    ]

    CSS = """
    Screen  { background: #1c1c1c; layout: vertical; }

    RichLog {
        height: 1fr;
        background: #1c1c1c;
        padding: 0 2;
        scrollbar-background: #262626;
        scrollbar-color: #444444;
    }

    #footer  { height: auto; background: #1c1c1c; }

    #status  {
        height: 1;
        background: #1c1c1c;
        color: cyan;
        padding: 0 2;
        display: none;
    }

    #autocomplete {
        background: #1c1c1c;
        border: none;
        border-top: tall #3a3a3a;
        max-height: 10;
        display: none;
    }
    #autocomplete > .option-list--option             { padding: 0 2; color: #aaaaaa; }
    #autocomplete > .option-list--option-highlighted { background: #3a3a3a; color: white; }

    Input {
        background: #262626;
        border: none;
        border-top: tall #3a3a3a;
        padding: 0 2;
        color: white;
        text-style: bold;
    }
    Input:focus        { border: none; border-top: tall #555555; }
    Input.-disabled    { opacity: 0.6; }
    """

    def __init__(self, cfg, agent, db) -> None:
        super().__init__()
        self._cfg = cfg
        self._agent = agent
        self._db = db
        self._commands = None
        self._spin_iter = itertools.cycle(_FRAMES)
        self._spin_timer = None
        self._ac_options: list[str] = []
        self._last_result: str = ""

    # ── layout ────────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield RichLog(highlight=False, markup=False, wrap=True, id="log")
        with Vertical(id="footer"):
            yield Static("", id="status")
            yield OptionList(id="autocomplete")
            yield Input(placeholder="Write a task or use /.", id="prompt")

    async def on_mount(self) -> None:
        from cli.commands import CommandManager

        async def confirm_fn(message: str) -> str:
            result = await self.push_screen_wait(ConfirmScreen(message))
            return "y" if result else "n"

        self._commands = CommandManager(
            self._db, self._agent.user_id, self._cfg, self._agent,
            confirm_fn=confirm_fn,
        )
        self._write_banner(self.query_one("#log", RichLog))
        self.query_one("#prompt", Input).focus()

    def _write_banner(self, log: RichLog) -> None:
        cfg = self._cfg
        username = os.getenv("USER") or os.getenv("USERNAME") or "there"
        log.write(Text("── This Is My Agent  github.com/YSMsimon/this-is-my-agent", style="green"))
        log.write(Text(""))
        log.write(Text(f"Welcome back, {username}!", style="bold yellow"))
        log.write(Text("/help for commands  ·  /deep for multi-agent mode  ·  Ctrl+Y copies last response", style="dim"))
        log.write(Text(""))
        log.write(Text(f"MODEL:           {cfg.model}", style="dim"))
        log.write(Text(f"COMPACT_MODEL:   {cfg.compact_model}", style="dim"))
        log.write(Text(f"PLANNER_MODEL:   {cfg.planner_model}", style="dim"))
        log.write(Text(""))

    # ── clipboard ─────────────────────────────────────────────────────────────

    def action_copy_response(self) -> None:
        if self._last_result:
            self.copy_to_clipboard(self._last_result)
            self.notify("Response copied to clipboard", timeout=2)

    # ── autocomplete ──────────────────────────────────────────────────────────

    def _ac_show(self, matches: list[str]) -> None:
        ac = self.query_one("#autocomplete", OptionList)
        ac.clear_options()
        for cmd in matches:
            ac.add_option(Option(cmd, id=cmd))
        self._ac_options = matches
        ac.display = True

    def _ac_hide(self) -> None:
        self.query_one("#autocomplete", OptionList).display = False
        self._ac_options = []

    def _ac_accept(self) -> None:
        ac = self.query_one("#autocomplete", OptionList)
        if not ac.display or not self._ac_options:
            return
        idx = ac.highlighted if ac.highlighted is not None else 0
        cmd = self._ac_options[idx]
        inp = self.query_one("#prompt", Input)
        inp.value = cmd + " "
        inp.cursor_position = len(inp.value)
        self._ac_hide()

    def on_input_changed(self, event: Input.Changed) -> None:
        text = event.value
        if text.startswith("/"):
            stripped = text.rstrip()
            matches = [c for c in SLASH_COMMANDS if c.startswith(stripped)]
            if matches and stripped not in SLASH_COMMANDS:
                self._ac_show(matches)
                return
        self._ac_hide()

    def on_key(self, event) -> None:
        ac = self.query_one("#autocomplete", OptionList)
        if not ac.display:
            return
        if event.key == "down":
            ac.action_cursor_down(); event.stop()
        elif event.key == "up":
            ac.action_cursor_up();   event.stop()
        elif event.key == "tab":
            self._ac_accept();       event.stop()
        elif event.key == "escape":
            self._ac_hide();         event.stop()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        cmd = self._ac_options[event.option_index]
        inp = self.query_one("#prompt", Input)
        inp.value = cmd + " "
        inp.cursor_position = len(inp.value)
        self._ac_hide()
        inp.focus()

    # ── spinner ───────────────────────────────────────────────────────────────

    def _start_spinner(self) -> None:
        s = self.query_one("#status", Static)
        s.update("  ⠇ Thinking…")
        s.display = True
        self._spin_timer = self.set_interval(0.08, self._tick_spinner)

    def _stop_spinner(self) -> None:
        if self._spin_timer:
            self._spin_timer.stop()
            self._spin_timer = None
        self.query_one("#status", Static).display = False

    def _tick_spinner(self) -> None:
        self.query_one("#status", Static).update(f"  {next(self._spin_iter)} Thinking…")

    # ── input handling ────────────────────────────────────────────────────────

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        self._ac_hide()
        self.query_one("#prompt", Input).value = ""
        self._process_input(text)

    @work
    async def _process_input(self, text: str) -> None:
        input_w = self.query_one("#prompt", Input)
        log     = self.query_one("#log",    RichLog)

        log.write(Text(f"  ❯  {text}", style="bold white on #262626"))
        log.write(Text(""))

        # ── commands ──
        if self._commands.is_command(text):
            writer = _LiveWriter(log)
            prev   = sys.stdout
            sys.stdout = writer
            try:
                await self._commands.handle(text)
            except SystemExit:
                sys.stdout = prev
                await self._db.close()
                self.exit()
                return
            finally:
                writer.flush()
                sys.stdout = prev
            log.write(Text(""))
            return

        # ── agent run ──
        input_w.disabled = True
        self._start_spinner()

        def _on_tool(name: str) -> None:
            log.write(Text(f"  [tool: {name}]", style="yellow dim"))

        self._agent._tool_event_fn = _on_tool
        self._agent._silent        = True

        writer = _LiveWriter(log)
        prev   = sys.stdout
        sys.stdout = writer
        result = ""
        try:
            result = await self._agent.run(text)
            writer.flush()

            if result:
                log.write(Text(""))
                log.write(Markdown(result))
                self._last_result = result
        except Exception as e:
            log.write(Text(f"Error: {e}", style="bold red"))
        finally:
            sys.stdout = prev
            self._agent._tool_event_fn = None
            self._stop_spinner()
            log.write(Text(""))
            input_w.disabled = False
            input_w.focus()
