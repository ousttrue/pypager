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

    @prompt_toolkit.filters.Condition
    def default_focus() -> bool:
        app = get_app()
        return app.layout.current_window == pager.source_container.current_source_info.window

    for c in "01234556789":
        def _handle_arg(event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
            event.append_to_arg_count(c)
        pager.bind(_handle_arg, c, filter=default_focus)

    pager.bind(pager._quit, "q", filter=default_focus, eager=True)
    pager.bind(pager._quit, "Q", filter=default_focus | pager.has_colon)
    pager.bind(pager._quit, "Z", "Z", filter=default_focus)
    pager.bind(pager.source_container._pagedown, " ", filter=default_focus)
    pager.bind(pager.source_container._pagedown, "f", filter=default_focus)
    pager.bind(pager.source_container._pagedown, "c-f", filter=default_focus)
    pager.bind(pager.source_container._pagedown, "c-v", filter=default_focus)
    pager.bind(pager.source_container._pageup, "b", filter=default_focus)
    pager.bind(pager.source_container._pageup, "c-b", filter=default_focus)
    pager.bind(pager.source_container._pageup,
               "escape", "v", filter=default_focus)
    pager.bind(pager.source_container._halfdown, "d", filter=default_focus)
    pager.bind(pager.source_container._halfdown, "c-d", filter=default_focus)
    pager.bind(pager.source_container._halfup, "u", filter=default_focus)
    pager.bind(pager.source_container._halfup, "c-u", filter=default_focus)
    pager.bind(pager.source_container._down, "e", filter=default_focus)
    pager.bind(pager.source_container._down, "j", filter=default_focus)
    pager.bind(pager.source_container._down, "c-e", filter=default_focus)
    pager.bind(pager.source_container._down, "c-n", filter=default_focus)
    pager.bind(pager.source_container._down, "c-j", filter=default_focus)
    pager.bind(pager.source_container._down, "c-m", filter=default_focus)
    pager.bind(pager.source_container._down, "down", filter=default_focus)
    pager.bind(pager.source_container._up, "y", filter=default_focus)
    pager.bind(pager.source_container._up, "k", filter=default_focus)
    pager.bind(pager.source_container._up, "c-y", filter=default_focus)
    pager.bind(pager.source_container._up, "c-k", filter=default_focus)
    pager.bind(pager.source_container._up, "c-p", filter=default_focus)
    pager.bind(pager.source_container._up, "up", filter=default_focus)
    pager.bind(pager.source_container._firstline,
               "g", filter=default_focus, eager=True)
    pager.bind(pager.source_container._firstline, "<", filter=default_focus)
    pager.bind(pager.source_container._firstline,
               "escape", "<", filter=default_focus)
    pager.bind(pager.source_container._lastline, "G", filter=default_focus)
    pager.bind(pager.source_container._lastline, ">", filter=default_focus)
    pager.bind(pager.source_container._lastline,
               "escape", ">", filter=default_focus)
    pager.bind(pager.source_container._wrap, "w")

    pager.bind(pager._print_filename, "=", filter=default_focus)
    pager.bind(pager._print_filename,
               prompt_toolkit.keys.Keys.ControlG, filter=default_focus)
    pager.bind(pager._print_filename, "f", filter=pager.has_colon)

    pager.bind(pager._toggle_highlighting,
               prompt_toolkit.keys.Keys.Escape, "u")
    pager.bind(pager._help, "h", filter=default_focus & ~pager.displaying_help)
    pager.bind(pager._help, "H", filter=default_focus & ~pager.displaying_help)

    pager.bind(pager._mark, "m", prompt_toolkit.keys.Keys.Any,
               filter=default_focus)
    pager.bind(pager._goto_mark, "'",
               prompt_toolkit.keys.Keys.Any, filter=default_focus)
    pager.bind(pager._gotomark_dot, "c-x",
               prompt_toolkit.keys.Keys.ControlX, filter=default_focus)

    pager.bind(pager._follow, "F", filter=default_focus)
    pager.bind(pager._repaint, "r", filter=default_focus)
    pager.bind(pager._repaint, "R", filter=default_focus)

    @prompt_toolkit.filters.Condition
    def search_buffer_is_empty() -> bool:
        " Returns True when the search buffer is empty. "
        return pager.source_container.search_buffer.text == ""

    pager.bind(pager._cancel_search,
               "backspace",
               filter=prompt_toolkit.filters.has_focus(
                   pager.source_container.search_buffer) & search_buffer_is_empty
               )

    @prompt_toolkit.filters.Condition
    def line_wrapping_enable() -> bool:
        return pager.source_container.current_source_info.wrap_lines

    pager.bind(pager._left, "left", filter=default_focus &
               ~line_wrapping_enable)
    pager.bind(pager._left, "escape",
               "(", filter=default_focus & ~line_wrapping_enable)

    pager.bind(pager._right, "right", filter=default_focus &
               ~line_wrapping_enable)
    pager.bind(pager._right, "escape", ")",
               filter=default_focus & ~line_wrapping_enable)

    pager.bind(pager._suspend, "c-z", filter=prompt_toolkit.filters.Condition(
        lambda: prompt_toolkit.utils.suspend_to_background_supported()))

    #
    # ::: colon :::
    #
    pager.bind(pager._colon, ":", filter=default_focus & ~pager.displaying_help)
    pager.bind(pager._next_file, "n", filter=pager.has_colon)
    pager.bind(pager._previous_file, "p", filter=pager.has_colon)
    pager.bind(pager._remove_source, "d", filter=pager.has_colon)
    pager.bind(pager._cancel_colon, "backspace", filter=pager.has_colon)
    pager.bind(pager._cancel_colon, "q", filter=pager.has_colon, eager=True)
    pager.bind(pager._any, prompt_toolkit.keys.Keys.Any,
               filter=pager.has_colon)

    #
    # examine
    #
    pager.bind(pager._examine, prompt_toolkit.keys.Keys.ControlX,
               prompt_toolkit.keys.Keys.ControlV, filter=default_focus)
    pager.bind(pager._examine, "e", filter=pager.has_colon)
    pager.bind(pager._cancel_examine, "c-c",
               filter=prompt_toolkit.filters.has_focus("EXAMINE"))
    pager.bind(pager._cancel_examine, "c-g",
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
