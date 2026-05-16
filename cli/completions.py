import shutil

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.layout.processors import Processor, Transformation
from prompt_toolkit.styles import Style

from cli.commands import COMMANDS

PROMPT = '  ❯  '
_PROMPT_WIDTH = len(PROMPT)   # 5 visible chars — must be subtracted from fill width

STYLE = Style.from_dict({
    # input area: dark grey background, bold white text
    '':            'bg:#262626 bold white',
    'fill':        'bg:#262626',
    # placeholder shown when input is empty — must share the same bg
    'placeholder': 'bg:#262626 fg:#555555',
    # autocomplete dropdown
    'completion-menu':                         'bg:#1c1c1c fg:#aaaaaa',
    'completion-menu.completion.current':      'bg:#3a3a3a bold white',
    'completion-menu.meta.completion':         'bg:#1c1c1c fg:#555555',
    'completion-menu.meta.completion.current': 'bg:#3a3a3a fg:#888888',
    'scrollbar.background':                    'bg:#1c1c1c',
    'scrollbar.button':                        'bg:#444444',
})


class FillBgProcessor(Processor):
    """
    Pads the input line to full width with the bg colour so the dark bar
    extends past the cursor.

    Two pitfalls avoided:
      1. ti.width is the full terminal width — we must subtract _PROMPT_WIDTH
         so prompt + content + fill never exceeds terminal_cols (which wraps
         the cursor to the next line and breaks the \\033[A clear trick).
      2. We stop 1 col short of the content area to avoid the end-of-line
         auto-wrap that some terminals trigger when the last column is filled.
    """
    def apply_transformation(self, ti):
        content_width = sum(len(text) for _, text, *_ in ti.fragments)
        if content_width == 0:
            return Transformation(ti.fragments)
        terminal_cols = shutil.get_terminal_size().columns
        available = terminal_cols - _PROMPT_WIDTH - 1
        remaining = max(0, available - content_width)
        if not remaining:
            return Transformation(ti.fragments)
        return Transformation(
            list(ti.fragments) + [('class:fill', ' ' * remaining)]
        )


_BASE_COMMANDS = sorted({k.split()[0] for k in COMMANDS.keys()})

_META: dict[str, str] = {}
for _k, _v in COMMANDS.items():
    _base = _k.split()[0]
    if _base not in _META:
        _META[_base] = _v


class SlashCompleter(Completer):
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if not text.startswith('/'):
            return
        for cmd in _BASE_COMMANDS:
            if cmd.startswith(text):
                yield Completion(
                    cmd,
                    start_position=-len(text),
                    display=cmd,
                    display_meta=_META.get(cmd, ''),
                )
