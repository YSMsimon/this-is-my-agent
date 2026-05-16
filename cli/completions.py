import shutil

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.layout.processors import Processor, Transformation
from prompt_toolkit.styles import Style

from cli.commands import COMMANDS


PROMPT = '  ❯  '
_PROMPT_WIDTH = len(PROMPT)  # 5 visible chars

STYLE = Style.from_dict({
    '':       'bg:#262626 bold white',
    'fill':   'bg:#262626',
    # completion dropdown
    'completion-menu':                         'bg:#1c1c1c fg:#aaaaaa',
    'completion-menu.completion.current':      'bg:#3a3a3a bold white',
    'completion-menu.meta.completion':         'bg:#1c1c1c fg:#555555',
    'completion-menu.meta.completion.current': 'bg:#3a3a3a fg:#888888',
    'scrollbar.background':                    'bg:#1c1c1c',
    'scrollbar.button':                        'bg:#444444',
})


class FillBgProcessor(Processor):
    """Appends bg-coloured spaces to fill the rest of the input line.

    ti.width is the full terminal width, not the content area, so we must
    subtract the prompt prefix width to avoid overflowing onto the next line
    (which would shift the cursor down and break the \033[A line-clearing).
    """
    def apply_transformation(self, ti):
        content_width = sum(len(text) for _, text, *_ in ti.fragments)
        terminal_cols = shutil.get_terminal_size().columns
        # Stop 1 col short of terminal width: filling to exactly terminal_cols
        # triggers an end-of-line cursor wrap on many terminals, which shifts
        # the cursor an extra line down and breaks the \033[A line-clear.
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
