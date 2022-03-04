#!/usr/bin/env python
"""
pypager: A pure Python pager application.
"""


__all__ = [
    "run",
]

from pypager.pager import Pager


def keybinding(pager: Pager):
    import prompt_toolkit.filters
    import prompt_toolkit.key_binding
    import prompt_toolkit.keys
    import prompt_toolkit.utils
    from prompt_toolkit.application.current import get_app

    for c in "01234556789":
        def _handle_arg(event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
            event.append_to_arg_count(c)
        pager.bind(_handle_arg, c, filter=pager.source_container.default_focus)

    pager.bind(pager._quit, "q",
               filter=pager.source_container.default_focus, eager=True)
    pager.bind(pager._quit, "Q",
               filter=pager.source_container.default_focus | pager.has_colon)
    pager.bind(pager._quit, "Z", "Z",
               filter=pager.source_container.default_focus)
    pager.bind(pager._print_filename, "=",
               filter=pager.source_container.default_focus)
    pager.bind(pager._print_filename,
               prompt_toolkit.keys.Keys.ControlG, filter=pager.source_container.default_focus)
    pager.bind(pager._print_filename, "f", filter=pager.has_colon)
    pager.bind(pager._help, "h",
               filter=pager.source_container.default_focus)
    pager.bind(pager._help, "H",
               filter=pager.source_container.default_focus)
    pager.bind(pager._repaint, "r",
               filter=pager.source_container.default_focus)
    pager.bind(pager._repaint, "R",
               filter=pager.source_container.default_focus)

    pager.bind(pager.source_container._pagedown, " ",
               filter=pager.source_container.default_focus)
    pager.bind(pager.source_container._pagedown, "f",
               filter=pager.source_container.default_focus)
    pager.bind(pager.source_container._pagedown, "c-f",
               filter=pager.source_container.default_focus)
    pager.bind(pager.source_container._pagedown, "c-v",
               filter=pager.source_container.default_focus)
    pager.bind(pager.source_container._pageup, "b",
               filter=pager.source_container.default_focus)
    pager.bind(pager.source_container._pageup, "c-b",
               filter=pager.source_container.default_focus)
    pager.bind(pager.source_container._pageup,
               "escape", "v", filter=pager.source_container.default_focus)
    pager.bind(pager.source_container._halfdown, "d",
               filter=pager.source_container.default_focus)
    pager.bind(pager.source_container._halfdown, "c-d",
               filter=pager.source_container.default_focus)
    pager.bind(pager.source_container._halfup, "u",
               filter=pager.source_container.default_focus)
    pager.bind(pager.source_container._halfup, "c-u",
               filter=pager.source_container.default_focus)
    pager.bind(pager.source_container._down, "e",
               filter=pager.source_container.default_focus)
    pager.bind(pager.source_container._down, "j",
               filter=pager.source_container.default_focus)
    pager.bind(pager.source_container._down, "c-e",
               filter=pager.source_container.default_focus)
    pager.bind(pager.source_container._down, "c-n",
               filter=pager.source_container.default_focus)
    pager.bind(pager.source_container._down, "c-j",
               filter=pager.source_container.default_focus)
    pager.bind(pager.source_container._down, "c-m",
               filter=pager.source_container.default_focus)
    pager.bind(pager.source_container._down, "down",
               filter=pager.source_container.default_focus)
    pager.bind(pager.source_container._up, "y",
               filter=pager.source_container.default_focus)
    pager.bind(pager.source_container._up, "k",
               filter=pager.source_container.default_focus)
    pager.bind(pager.source_container._up, "c-y",
               filter=pager.source_container.default_focus)
    pager.bind(pager.source_container._up, "c-k",
               filter=pager.source_container.default_focus)
    pager.bind(pager.source_container._up, "c-p",
               filter=pager.source_container.default_focus)
    pager.bind(pager.source_container._up, "up",
               filter=pager.source_container.default_focus)
    pager.bind(pager.source_container._firstline,
               "g", filter=pager.source_container.default_focus, eager=True)
    pager.bind(pager.source_container._firstline, "<",
               filter=pager.source_container.default_focus)
    pager.bind(pager.source_container._firstline,
               "escape", "<", filter=pager.source_container.default_focus)
    pager.bind(pager.source_container._lastline, "G",
               filter=pager.source_container.default_focus)
    pager.bind(pager.source_container._lastline, ">",
               filter=pager.source_container.default_focus)
    pager.bind(pager.source_container._lastline,
               "escape", ">", filter=pager.source_container.default_focus)
    pager.bind(pager.source_container._toggle_highlighting,
               prompt_toolkit.keys.Keys.Escape, "u")

    pager.bind(pager.source_container._mark, "m", prompt_toolkit.keys.Keys.Any,
               filter=pager.source_container.default_focus)
    pager.bind(pager.source_container._goto_mark, "'",
               prompt_toolkit.keys.Keys.Any, filter=pager.source_container.default_focus)
    pager.bind(pager.source_container._gotomark_dot, "c-x",
               prompt_toolkit.keys.Keys.ControlX, filter=pager.source_container.default_focus)

    pager.bind(pager.source_container._follow, "F",
               filter=pager.source_container.default_focus)

    pager.bind(pager.source_container._cancel_search,
               "backspace",
               filter=prompt_toolkit.filters.has_focus(
                   pager.source_container.search_buffer) & pager.source_container.search_buffer_is_empty
               )

    pager.bind(pager.source_container._left, "left", filter=pager.source_container.default_focus &
               ~pager.source_container.line_wrapping_enable)
    pager.bind(pager.source_container._left, "escape",
               "(", filter=pager.source_container.default_focus & ~pager.source_container.line_wrapping_enable)

    pager.bind(pager.source_container._right, "right", filter=pager.source_container.default_focus &
               ~pager.source_container.line_wrapping_enable)
    pager.bind(pager.source_container._right, "escape", ")",
               filter=pager.source_container.default_focus & ~pager.source_container.line_wrapping_enable)

    pager.bind(pager._suspend, "c-z", filter=prompt_toolkit.filters.Condition(
        lambda: prompt_toolkit.utils.suspend_to_background_supported()))

    pager.bind(pager.source_container._next_file, "F",
               filter=pager.source_container.default_focus, eager=True)
    pager.bind(pager.source_container._previous_file, "B",
               filter=pager.source_container.default_focus)

    #
    # ::: colon :::
    #
    pager.bind(pager._colon, ":", filter=pager.source_container.default_focus)
    pager.bind(pager.source_container._next_file, "n", filter=pager.has_colon)
    pager.bind(pager.source_container._previous_file,
               "p", filter=pager.has_colon)
    pager.bind(pager.source_container._remove_source,
               "d", filter=pager.has_colon)
    pager.bind(pager._cancel_colon, "backspace", filter=pager.has_colon)
    pager.bind(pager._cancel_colon, "q", filter=pager.has_colon, eager=True)
    pager.bind(pager._any, prompt_toolkit.keys.Keys.Any,
               filter=pager.has_colon)
    pager.bind(pager.source_container._wrap, "w", filter=pager.has_colon)

    #
    # examine
    #
    pager.bind(pager._examine, prompt_toolkit.keys.Keys.ControlX,
               prompt_toolkit.keys.Keys.ControlV, filter=pager.source_container.default_focus)
    pager.bind(pager._examine, "e", filter=pager.has_colon)
    pager.bind(pager.source_container._cancel_examine, "c-c",
               filter=prompt_toolkit.filters.has_focus("EXAMINE"))
    pager.bind(pager.source_container._cancel_examine, "c-g",
               filter=prompt_toolkit.filters.has_focus("EXAMINE"))


def run():
    import sys
    if not sys.stdin.isatty():
        pager = Pager.from_pipe()
    else:
        import argparse
        parser = argparse.ArgumentParser(
            description="Browse through a text file.")
        parser.add_argument(
            "filename", metavar="filename", nargs="+", help="The file to be displayed."
        )

        args = parser.parse_args()

        pager = Pager()

        # Open files.
        from pypager.source.pipe_source import FileSource
        from prompt_toolkit.lexers import PygmentsLexer
        for filename in args.filename:
            # When a filename is given, take a lexer from that filename.
            lexer = PygmentsLexer.from_filename(
                filename, sync_from_start=False)

            info = pager.source_container.add_source(
                FileSource(filename, lexer=lexer))
            pager.application.layout.focus(info.window)

    keybinding(pager)

    # Run UI.
    pager.application.run()
