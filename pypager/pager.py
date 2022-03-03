"""
Pager implementation in Python.
"""
from typing import Optional, Union, Callable
import sys

import prompt_toolkit
from prompt_toolkit.application.current import get_app
import prompt_toolkit.keys
import prompt_toolkit.search
import prompt_toolkit.formatted_text
import prompt_toolkit.key_binding
import prompt_toolkit.widgets.toolbars
import prompt_toolkit.layout.containers
import prompt_toolkit.layout.controls
import prompt_toolkit.layout.processors
import prompt_toolkit.layout.menus
import prompt_toolkit.layout
import prompt_toolkit.buffer
import prompt_toolkit.completion
import prompt_toolkit.document
import prompt_toolkit.enums
import prompt_toolkit.lexers
import prompt_toolkit.styles
import prompt_toolkit.filters
import prompt_toolkit.utils
from prompt_toolkit.key_binding.bindings.scroll import (
    scroll_half_page_down,
    scroll_half_page_up,
    scroll_one_line_down,
    scroll_one_line_up,
    scroll_page_down,
    scroll_page_up,
)


from .help import HELP
from .source import FormattedTextSource
from .source.pipe_source import PipeSource
from .source.sourcecontainer import SourceContainer
from .style import ui_style
from .layout import PagerLayout

__all__ = [
    "Pager",
]


class Pager:
    """
    The Pager main application.

    Usage::
        p = Pager()
        p.add_source(...)
        p.run()
    """

    def __init__(self) -> None:
        self.source_container = SourceContainer(self.on_message)
        self.in_colon_mode = False
        self.message = ''
        self.displaying_help = False

        # Input/output.
        # By default, use the stdout device for input.
        # (This makes it possible to pipe data to stdin, but still read key
        # strokes from the TTY).
        from prompt_toolkit.input.defaults import create_input
        input = create_input(sys.stdout)

        #
        # key bind
        #
        self.key_bindings = prompt_toolkit.key_binding.KeyBindings()

        @prompt_toolkit.filters.Condition
        def default_focus() -> bool:
            app = get_app()
            return app.layout.current_window == self.source_container.current_source_info.window

        @prompt_toolkit.filters.Condition
        def has_colon() -> bool:
            return self.in_colon_mode

        @prompt_toolkit.filters.Condition
        def displaying_help() -> bool:
            return self.displaying_help

        for c in "01234556789":
            def _handle_arg(event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
                event.append_to_arg_count(c)
            self.bind(_handle_arg, c, filter=default_focus)

        self.bind(self._quit, "q", filter=default_focus, eager=True)
        self.bind(self._quit, "Q", filter=default_focus | has_colon)
        self.bind(self._quit, "Z", "Z", filter=default_focus)
        self.bind(self._pagedown, " ", filter=default_focus)
        self.bind(self._pagedown, "f", filter=default_focus)
        self.bind(self._pagedown, "c-f", filter=default_focus)
        self.bind(self._pagedown, "c-v", filter=default_focus)
        self.bind(self._pageup, "b", filter=default_focus)
        self.bind(self._pageup, "c-b", filter=default_focus)
        self.bind(self._pageup, "escape", "v", filter=default_focus)
        self.bind(self._halfdown, "d", filter=default_focus)
        self.bind(self._halfdown, "c-d", filter=default_focus)
        self.bind(self._halfup, "u", filter=default_focus)
        self.bind(self._halfup, "c-u", filter=default_focus)
        self.bind(self._down, "e", filter=default_focus)
        self.bind(self._down, "j", filter=default_focus)
        self.bind(self._down, "c-e", filter=default_focus)
        self.bind(self._down, "c-n", filter=default_focus)
        self.bind(self._down, "c-j", filter=default_focus)
        self.bind(self._down, "c-m", filter=default_focus)
        self.bind(self._down, "down", filter=default_focus)
        self.bind(self._up, "y", filter=default_focus)
        self.bind(self._up, "k", filter=default_focus)
        self.bind(self._up, "c-y", filter=default_focus)
        self.bind(self._up, "c-k", filter=default_focus)
        self.bind(self._up, "c-p", filter=default_focus)
        self.bind(self._up, "up", filter=default_focus)
        self.bind(self._firstline, "g", filter=default_focus, eager=True)
        self.bind(self._firstline, "<", filter=default_focus)
        self.bind(self._firstline, "escape", "<", filter=default_focus)
        self.bind(self._lastline, "G", filter=default_focus)
        self.bind(self._lastline, ">", filter=default_focus)
        self.bind(self._lastline, "escape", ">", filter=default_focus)

        self.bind(self._print_filename, "=", filter=default_focus)
        self.bind(self._print_filename,
                  prompt_toolkit.keys.Keys.ControlG, filter=default_focus)
        self.bind(self._print_filename, "f", filter=has_colon)

        self.bind(self._toggle_highlighting,
                  prompt_toolkit.keys.Keys.Escape, "u")
        self.bind(self._help, "h", filter=default_focus & ~displaying_help)
        self.bind(self._help, "H", filter=default_focus & ~displaying_help)

        self.bind(self._mark, "m", prompt_toolkit.keys.Keys.Any,
                  filter=default_focus)
        self.bind(self._goto_mark, "'",
                  prompt_toolkit.keys.Keys.Any, filter=default_focus)
        self.bind(self._gotomark_dot, "c-x",
                  prompt_toolkit.keys.Keys.ControlX, filter=default_focus)

        self.bind(self._follow, "F", filter=default_focus)
        self.bind(self._repaint, "r", filter=default_focus)
        self.bind(self._repaint, "R", filter=default_focus)

        @prompt_toolkit.filters.Condition
        def search_buffer_is_empty() -> bool:
            " Returns True when the search buffer is empty. "
            return self.source_container.search_buffer.text == ""

        self.bind(self._cancel_search,
                  "backspace",
                  filter=prompt_toolkit.filters.has_focus(
                      self.source_container.search_buffer) & search_buffer_is_empty
                  )

        @prompt_toolkit.filters.Condition
        def line_wrapping_enable() -> bool:
            return self.source_container.current_source_info.wrap_lines

        self.bind(self._left, "left", filter=default_focus &
                  ~line_wrapping_enable)
        self.bind(self._left, "escape",
                  "(", filter=default_focus & ~line_wrapping_enable)

        self.bind(self._right, "right", filter=default_focus &
                  ~line_wrapping_enable)
        self.bind(self._right, "escape", ")",
                  filter=default_focus & ~line_wrapping_enable)

        self.bind(self._suspend, "c-z", filter=prompt_toolkit.filters.Condition(
            lambda: prompt_toolkit.utils.suspend_to_background_supported()))
        self.bind(self._wrap, "w")

        #
        # ::: colon :::
        #
        self.bind(self._colon, ":", filter=default_focus & ~displaying_help)
        self.bind(self._next_file, "n", filter=has_colon)
        self.bind(self._previous_file, "p", filter=has_colon)
        self.bind(self._remove_source, "d", filter=has_colon)
        self.bind(self._cancel_colon, "backspace", filter=has_colon)
        self.bind(self._cancel_colon, "q", filter=has_colon, eager=True)
        self.bind(self._any, prompt_toolkit.keys.Keys.Any, filter=has_colon)

        #
        # examine
        #
        self.bind(self._examine, prompt_toolkit.keys.Keys.ControlX,
                  prompt_toolkit.keys.Keys.ControlV, filter=default_focus)
        self.bind(self._examine, "e", filter=has_colon)
        self.bind(self._cancel_examine, "c-c",
                  filter=prompt_toolkit.filters.has_focus("EXAMINE"))
        self.bind(self._cancel_examine, "c-g",
                  filter=prompt_toolkit.filters.has_focus("EXAMINE"))

        waiting = prompt_toolkit.filters.Condition(
            lambda: self.source_container.current_source_info.waiting_for_input_stream
        )

        self.layout = PagerLayout(self.source_container.open_file, has_colon, waiting,
                                  self._get_statusbar_left_tokens, self._get_statusbar_right_tokens, self.source_container, self.source_container.search_toolbar,
                                  lambda: self.message)

        self.application = prompt_toolkit.Application(
            input=input,
            layout=prompt_toolkit.layout.Layout(container=self.layout.root),
            enable_page_navigation_bindings=True,
            key_bindings=self.key_bindings,
            style=prompt_toolkit.styles.Style.from_dict(ui_style),
            mouse_support=True,
            after_render=self.source_container._after_render,
            full_screen=True,
            editing_mode=prompt_toolkit.enums.EditingMode.VI,
        )

        # Hide message when a key is pressed.
        def key_pressed(_) -> None:
            self.message = ''

        self.application.key_processor.before_key_press += key_pressed

    @classmethod
    def from_pipe(cls, lexer: Optional[prompt_toolkit.lexers.Lexer] = None) -> "Pager":
        """
        Create a pager from another process that pipes in our stdin.
        """
        assert not sys.stdin.isatty()
        self = cls()
        self.source_container.add_source(
            PipeSource(
                fileno=sys.stdin.fileno(), lexer=lexer, encoding=sys.stdin.encoding
            )
        )
        return self

    def on_message(self, msg: str):
        self.message = msg

    def _get_statusbar_left_tokens(self) -> prompt_toolkit.formatted_text.HTML:
        """
        Displayed at the bottom left.
        """
        if self.displaying_help:
            return prompt_toolkit.formatted_text.HTML(" HELP -- Press <key>[q]</key> when done")
        else:
            return prompt_toolkit.formatted_text.HTML(" (press <key>[h]</key> for help or <key>[q]</key> to quit)")

    def _get_statusbar_right_tokens(self) -> prompt_toolkit.formatted_text.StyleAndTextTuples:
        """
        Displayed at the bottom right.
        """
        source_info = self.source_container.current_source_info
        buffer = source_info.buffer
        document = buffer.document
        row = document.cursor_position_row + 1
        col = document.cursor_position_col + 1

        if source_info.wrap_lines:
            col = "WRAP"

        if self.source_container.current_source.eof():
            percentage = int(100 * row / document.line_count)
            return [
                (
                    "class:statusbar,cursor-position",
                    " (%s,%s) %s%% " % (row, col, percentage),
                )
            ]
        else:
            return [("class:statusbar,cursor-position", " (%s,%s) " % (row, col))]

    def bind(self, func: prompt_toolkit.key_binding.key_bindings.KeyHandlerCallable, *keys: Union[prompt_toolkit.keys.Keys, str],
             filter: prompt_toolkit.filters.FilterOrBool = True,
             eager: prompt_toolkit.filters.FilterOrBool = False,
             is_global: prompt_toolkit.filters.FilterOrBool = False,
             save_before: Callable[[prompt_toolkit.key_binding.KeyPressEvent], bool] = (
            lambda e: True),
            record_in_macro: prompt_toolkit.filters.FilterOrBool = True):
        assert keys

        keys = tuple(prompt_toolkit.key_binding.key_bindings._parse_key(k)
                     for k in keys)
        self.key_bindings.bindings.append(
            prompt_toolkit.key_binding.key_bindings.Binding(
                keys,
                func,
                filter=filter,
                eager=eager,
                is_global=is_global,
                save_before=save_before,
                record_in_macro=record_in_macro,
            )
        )
        self.key_bindings._clear_cache()

    def _quit(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Quit. "
        if self.displaying_help:
            self.quit_help()
        else:
            event.app.exit()

    def _pagedown(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Page down."
        scroll_page_down(event)

    def _pageup(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Page up."
        scroll_page_up(event)

    def _halfdown(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Half page down."
        scroll_half_page_down(event)

    def _halfup(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Half page up."
        scroll_half_page_up(event)

    def _down(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Scoll one line down."
        if event.arg > 1:
            # When an argument is given, go this amount of lines down.
            event.current_buffer.auto_down(count=event.arg)
        else:
            scroll_one_line_down(event)

    def _up(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Scoll one line up."
        if event.arg > 1:
            event.current_buffer.auto_up(count=event.arg)
        else:
            scroll_one_line_up(event)

    def _firstline(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Go to the first line of the file. "
        event.current_buffer.cursor_position = 0

    def _lastline(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Go to the last line of the file. "
        b = event.current_buffer
        b.cursor_position = len(b.text)

    def _print_filename(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Print the current file name. "
        self.message = " {} ".format(
            self.source_container.current_source.get_name())

    def _help(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Display Help. "
        self.display_help()

    def _toggle_highlighting(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Toggle search highlighting. "
        self.highlight_search = not self.highlight_search

    def _mark(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Mark current position. "
        source_info = self.source_container.current_source_info
        source_info.marks[event.data] = (
            event.current_buffer.cursor_position,
            source_info.window.vertical_scroll,
        )

    def _goto_mark(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Go to a previously marked position. "
        self.go_to_mark(event, event.data)

    def _gotomark_dot(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Same as '. "
        self.go_to_mark(event, ".")

    def go_to_mark(self, event: prompt_toolkit.key_binding.KeyPressEvent, mark: str) -> None:
        b = event.current_buffer
        source_info = self.source_container.current_source_info
        try:
            if mark == "^":  # Start of file.
                cursor_pos, vertical_scroll = 0, 0
            elif mark == "$":  # End of file - mark.
                cursor_pos, vertical_scroll = len(b.text), 0
            else:  # Custom mark.
                cursor_pos, vertical_scroll = source_info.marks[mark]
        except KeyError:
            pass  # TODO: show warning.
        else:
            b.cursor_position = cursor_pos
            source_info.window.vertical_scroll = vertical_scroll

    def _follow(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Forward forever, like 'tail -f'. "
        self.forward_forever = True

    def _repaint(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        event.app.renderer.clear()

    def _cancel_search(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Cancel search when backspace is pressed. "
        prompt_toolkit.search.stop_search()

    def _left(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Scroll half page to the left. "
        w = event.app.layout.current_window
        b = event.app.current_buffer

        if w and w.render_info:
            info = w.render_info
            amount = info.window_width // 2

            # Move cursor horizontally.
            value = b.cursor_position - min(
                amount, len(b.document.current_line_before_cursor)
            )
            b.cursor_position = value

            # Scroll.
            w.horizontal_scroll = max(0, w.horizontal_scroll - amount)

    def _right(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Scroll half page to the right. "
        w = event.app.layout.current_window
        b = event.app.current_buffer

        if w and w.render_info:
            info = w.render_info
            amount = info.window_width // 2

            # Move the cursor first to a visible line that is long enough to
            # have the cursor visible after scrolling. (Otherwise, the Window
            # will scroll back.)
            xpos = w.horizontal_scroll + amount

            for line in info.displayed_lines:
                if len(b.document.lines[line]) >= xpos:
                    b.cursor_position = b.document.translate_row_col_to_index(
                        line, xpos
                    )
                    break

            # Scroll.
            w.horizontal_scroll = max(0, w.horizontal_scroll + amount)

    def _colon(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        self.in_colon_mode = True

    def _next_file(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Go to next file. "
        self.source_container.focus_next_source()

    def _previous_file(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Go to previous file. "
        self.source_container.focus_previous_source()

    def _examine(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        event.app.layout.focus(self.layout.examine.examine_buffer)
        self.in_colon_mode = False

    def _remove_source(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        self.source_container.remove_current_source()

    def _cancel_colon(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        self.in_colon_mode = False

    def _any(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        self.in_colon_mode = False
        self.message = "No command."

    def _cancel_examine(self,  event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Cancel 'Examine' input. "
        event.app.layout.focus(
            self.source_container.current_source_info.window)

    def _suspend(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Suspend to bakground. "
        event.app.suspend_to_background()

    def _wrap(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Enable/disable line wrapping. "
        source_info = self.source_container.current_source_info
        source_info.wrap_lines = not source_info.wrap_lines

    def display_help(self) -> None:
        """
        Display help text.
        """
        if not self.displaying_help:
            source = FormattedTextSource(HELP, name="<help>")
            self.source_container.add_source(source)
            self.displaying_help = True

    def quit_help(self) -> None:
        """
        Hide the help text.
        """
        if self.displaying_help:
            self.source_container.remove_current_source()
            self.displaying_help = False
