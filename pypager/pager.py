"""
Pager implementation in Python.
"""
from typing import List, Optional, Sequence, Union, Callable
import asyncio
import sys
import threading
import weakref

import prompt_toolkit
from prompt_toolkit.application.current import get_app
import prompt_toolkit.keys
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
from prompt_toolkit.key_binding.bindings.scroll import (
    scroll_half_page_down,
    scroll_half_page_up,
    scroll_one_line_down,
    scroll_one_line_up,
    scroll_page_down,
    scroll_page_up,
)


from .help import HELP
from .source import DummySource, FormattedTextSource, Source
from .source.pipe_source import FileSource, PipeSource
from .source.source_info import SourceInfo
from .style import ui_style
from .event_property import EventProperty
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
        self.sources: List[Source] = []
        # Index in `self.sources`.
        self.current_source_index = EventProperty[int](0)
        self.highlight_search = True
        self._in_colon_mode = EventProperty[bool](False)
        self._message = EventProperty[str]('')
        self.displaying_help = False

        self._dummy_source = DummySource()

        # When this is True, always make sure that the cursor goes to the
        # bottom of the visible content. This is similar to 'tail -f'.
        self.forward_forever = False

        # Status information for all sources. Source -> SourceInfo.
        # (Remember this info as long as the Source object exists.)
        self.source_info: weakref.WeakKeyDictionary[
            Source, SourceInfo
        ] = weakref.WeakKeyDictionary()

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
            return app.layout.current_window == self.current_source_info.window

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

        waiting = prompt_toolkit.filters.Condition(
            lambda: self.current_source_info.waiting_for_input_stream
        )

        self.layout = PagerLayout(self.open_file, has_colon, waiting,
                                  self._get_statusbar_left_tokens, self._get_statusbar_right_tokens, lambda: self.current_source_info.window)

        self.application = prompt_toolkit.Application(
            input=input,
            layout=prompt_toolkit.layout.Layout(container=self.layout.root),
            enable_page_navigation_bindings=True,
            key_bindings=self.key_bindings,
            style=prompt_toolkit.styles.Style.from_dict(ui_style),
            mouse_support=True,
            after_render=self._after_render,
            full_screen=True,
            editing_mode=prompt_toolkit.enums.EditingMode.VI,
        )

        # Hide message when a key is pressed.
        def key_pressed(_) -> None:
            self._message.set('')

        self.application.key_processor.before_key_press += key_pressed

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
        source_info = self.source_info[self.current_source]
        buffer = source_info.buffer
        document = buffer.document
        row = document.cursor_position_row + 1
        col = document.cursor_position_col + 1

        if source_info.wrap_lines:
            col = "WRAP"

        if self.current_source.eof():
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
        self._message.set(" {} ".format(self.current_source.get_name()))

    def _help(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Display Help. "
        self.display_help()

    def _toggle_highlighting(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Toggle search highlighting. "
        self.highlight_search = not self.highlight_search

    # @handle("m", prompt_toolkit.keys.Keys.Any, filter=default_focus)
    # def _mark(event: E) -> None:
    #     " Mark current position. "
    #     source_info = pager.current_source_info

    #     source_info.marks[event.data] = (
    #         event.current_buffer.cursor_position,
    #         source_info.window.vertical_scroll,
    #     )

    # @handle("'", prompt_toolkit.keys.Keys.Any, filter=default_focus)
    # def _goto_mark(event: E) -> None:
    #     " Go to a previously marked position. "
    #     go_to_mark(event, event.data)

    # @handle("c-x", prompt_toolkit.keys.Keys.ControlX, filter=default_focus)
    # def _gotomark_dot(event: E) -> None:
    #     " Same as '. "
    #     go_to_mark(event, ".")

    # def go_to_mark(event: E, mark: str) -> None:
    #     b = event.current_buffer
    #     source_info = pager.current_source_info
    #     try:
    #         if mark == "^":  # Start of file.
    #             cursor_pos, vertical_scroll = 0, 0
    #         elif mark == "$":  # End of file - mark.
    #             cursor_pos, vertical_scroll = len(b.text), 0
    #         else:  # Custom mark.
    #             cursor_pos, vertical_scroll = source_info.marks[mark]
    #     except KeyError:
    #         pass  # TODO: show warning.
    #     else:
    #         b.cursor_position = cursor_pos
    #         source_info.window.vertical_scroll = vertical_scroll

    # @handle("F", filter=default_focus)
    # def _follow(event: E) -> None:
    #     " Forward forever, like 'tail -f'. "
    #     pager.forward_forever = True

    # @handle("r", filter=default_focus)
    # @handle("R", filter=default_focus)
    # def _repaint(event: E) -> None:
    #     event.app.renderer.clear()

    # @prompt_toolkit.filters.Condition
    # def search_buffer_is_empty() -> bool:
    #     " Returns True when the search buffer is empty. "
    #     return pager.search_buffer.text == ""

    # @handle(
    #     "backspace",
    #     filter=prompt_toolkit.filters.has_focus(
    #         pager.search_buffer) & search_buffer_is_empty,
    # )
    # def _cancel_search(event: E) -> None:
    #     " Cancel search when backspace is pressed. "
    #     prompt_toolkit.search.stop_search()

    # @prompt_toolkit.filters.Condition
    # def line_wrapping_enable() -> bool:
    #     return pager.current_source_info.wrap_lines

    # @handle("left", filter=default_focus & ~line_wrapping_enable)
    # @handle("escape", "(", filter=default_focus & ~line_wrapping_enable)
    # def _left(event: E) -> None:
    #     " Scroll half page to the left. "
    #     w = event.app.layout.current_window
    #     b = event.app.current_buffer

    #     if w and w.render_info:
    #         info = w.render_info
    #         amount = info.window_width // 2

    #         # Move cursor horizontally.
    #         value = b.cursor_position - min(
    #             amount, len(b.document.current_line_before_cursor)
    #         )
    #         b.cursor_position = value

    #         # Scroll.
    #         w.horizontal_scroll = max(0, w.horizontal_scroll - amount)

    # @handle("right", filter=default_focus & ~line_wrapping_enable)
    # @handle("escape", ")", filter=default_focus & ~line_wrapping_enable)
    # def _right(event: E) -> None:
    #     " Scroll half page to the right. "
    #     w = event.app.layout.current_window
    #     b = event.app.current_buffer

    #     if w and w.render_info:
    #         info = w.render_info
    #         amount = info.window_width // 2

    #         # Move the cursor first to a visible line that is long enough to
    #         # have the cursor visible after scrolling. (Otherwise, the Window
    #         # will scroll back.)
    #         xpos = w.horizontal_scroll + amount

    #         for line in info.displayed_lines:
    #             if len(b.document.lines[line]) >= xpos:
    #                 b.cursor_position = b.document.translate_row_col_to_index(
    #                     line, xpos
    #                 )
    #                 break

    #         # Scroll.
    #         w.horizontal_scroll = max(0, w.horizontal_scroll + amount)

    # @handle(":", filter=default_focus & ~displaying_help)
    # def _colon(event: E) -> None:
    #     pager.in_colon_mode = True

    # @handle("n", filter=has_colon)
    # def _next_file(event: E) -> None:
    #     " Go to next file. "
    #     pager.focus_next_source()

    # @handle("p", filter=has_colon)
    # def _previous_file(event: E) -> None:
    #     " Go to previous file. "
    #     pager.focus_previous_source()

    # @handle("e", filter=has_colon)
    # @handle(prompt_toolkit.keys.Keys.ControlX, prompt_toolkit.keys.Keys.ControlV, filter=default_focus)
    # def _examine(event: E) -> None:
    #     event.app.layout.focus(pager.layout.examine_control)
    #     pager.in_colon_mode = False

    # @handle("d", filter=has_colon)
    # def _remove_source(event: E) -> None:
    #     pager.remove_current_source()

    # @handle("backspace", filter=has_colon)
    # @handle("q", filter=has_colon, eager=True)
    # def _cancel_colon(event: E) -> None:
    #     pager.in_colon_mode = False

    # @handle(prompt_toolkit.keys.Keys.Any, filter=has_colon)
    # def _any(event: E) -> None:
    #     pager.in_colon_mode = False
    #     pager.message = "No command."

    # @handle("c-c", filter=prompt_toolkit.filters.has_focus("EXAMINE"))
    # @handle("c-g", filter=prompt_toolkit.filters.has_focus("EXAMINE"))
    # def _cancel_examine(event: E) -> None:
    #     " Cancel 'Examine' input. "
    #     event.app.layout.focus(pager.current_source_info.window)

    # @handle("c-z", filter=prompt_toolkit.filters.Condition(lambda: prompt_toolkit.utils.suspend_to_background_supported()))
    # def _suspend(event: E) -> None:
    #     " Suspend to bakground. "
    #     event.app.suspend_to_background()

    # @handle("w")
    # def _suspend(event: E) -> None:
    #     " Enable/disable line wrapping. "
    #     source_info = pager.current_source_info
    #     source_info.wrap_lines = not source_info.wrap_lines

    @property
    def in_colon_mode(self) -> bool:
        return self._in_colon_mode.value

    @in_colon_mode.setter
    def in_colon_mode(self, value: bool):
        self._in_colon_mode.set(value)

    @classmethod
    def from_pipe(cls, lexer: Optional[prompt_toolkit.lexers.Lexer] = None) -> "Pager":
        """
        Create a pager from another process that pipes in our stdin.
        """
        assert not sys.stdin.isatty()
        self = cls()
        self.add_source(
            PipeSource(
                fileno=sys.stdin.fileno(), lexer=lexer, encoding=sys.stdin.encoding
            )
        )
        return self

    @property
    def current_source(self) -> Source:
        " The current `Source`. "
        try:
            return self.sources[self.current_source_index.value]
        except IndexError:
            return self._dummy_source

    @property
    def current_source_info(self) -> SourceInfo:
        try:
            return self.source_info[self.current_source]
        except KeyError:
            return SourceInfo(self.current_source, self.highlight_search, self.layout.search_toolbar.control)

    def open_file(self, filename: str) -> None:
        """
        Open this file.
        """
        lexer = prompt_toolkit.lexers.PygmentsLexer.from_filename(
            filename, sync_from_start=False)

        try:
            source = FileSource(filename, lexer=lexer)
        except IOError as e:
            self._message.set("{}".format(e))
        else:
            self.add_source(source)

    def add_source(self, source: Source) -> SourceInfo:
        """
        Add a new :class:`.Source` instance.
        """
        source_info = SourceInfo(
            source, self.highlight_search, self.layout.search_toolbar.control)
        self.source_info[source] = source_info

        self.sources.append(source)

        # Focus
        self.current_source_index.set(len(self.sources) - 1)
        self.application.layout.focus(source_info.window)

        return source_info

    def remove_current_source(self) -> None:
        """
        Remove the current source from the self.
        (If >1 source is left.)
        """
        if len(self.sources) > 1:
            current_source = self.current_source

            # Focus the previous source.
            self.focus_previous_source()

            # Remove the last source.
            self.sources.remove(current_source)
        else:
            self._message.set("Can't remove the last buffer.")

    def focus_previous_source(self) -> None:
        self.current_source_index.set((
            self.current_source_index.value - 1) % len(self.sources))
        self.application.layout.focus(self.current_source_info.window)
        self._in_colon_mode.set(False)

    def focus_next_source(self) -> None:
        self.current_source_index.set((
            self.current_source_index.value + 1) % len(self.sources))
        self.application.layout.focus(self.current_source_info.window)
        self._in_colon_mode.set(False)

    def display_help(self) -> None:
        """
        Display help text.
        """
        if not self.displaying_help:
            source = FormattedTextSource(HELP, name="<help>")
            self.add_source(source)
            self.displaying_help = True

    def quit_help(self) -> None:
        """
        Hide the help text.
        """
        if self.displaying_help:
            self.remove_current_source()
            self.displaying_help = False

    def _after_render(self, app: prompt_toolkit.Application) -> None:
        """
        Each time when the rendering is done, we should see whether we need to
        read more data from the input pipe.
        """
        # When the bottom is visible, read more input.
        # Try at least `info.window_height`, if this amount of data is
        # available.
        info = self.layout.dynamic_body.get_render_info()
        source = self.current_source
        source_info = self.source_info[source]
        b = source_info.buffer
        line_tokens = source_info.line_tokens
        loop = asyncio.get_event_loop()

        if not source_info.waiting_for_input_stream and not source.eof() and info:
            lines_below_bottom = info.ui_content.line_count - info.last_visible_line()

            # Make sure to preload at least 2x the amount of lines on a page.
            if lines_below_bottom < info.window_height * 2 or self.forward_forever:
                # Lines to be loaded.
                lines = [info.window_height * 2 -
                         lines_below_bottom]  # nonlocal

                def handle_content(tokens: prompt_toolkit.formatted_text.StyleAndTextTuples) -> List[str]:
                    """Handle tokens, update `line_tokens`, decrease
                    line count and return list of characters."""
                    data = []
                    for token_char in tokens:
                        char = token_char[1]
                        if char == "\n":
                            line_tokens.append([])

                            # Decrease line count.
                            lines[0] -= 1
                        else:
                            line_tokens[-1].append(token_char)
                        data.append(char)
                    return data

                def insert_text(list_of_fragments: Sequence[str]) -> None:
                    document = prompt_toolkit.document.Document(
                        b.text + "".join(list_of_fragments), b.cursor_position
                    )
                    b.set_document(document, bypass_readonly=True)

                    if self.forward_forever:
                        b.cursor_position = len(b.text)

                    # Schedule redraw.
                    self.application.invalidate()

                    source_info.waiting_for_input_stream = False

                def receive_content_from_generator() -> None:
                    " (in executor) Read data from generator. "
                    # Call `read_chunk` as long as we need more lines.
                    while lines[0] > 0 and not source.eof():
                        tokens = source.read_chunk()
                        data = handle_content(tokens)
                        loop.call_soon(insert_text, data)

                # Set 'waiting_for_input_stream' and render.
                source_info.waiting_for_input_stream = True
                self.application.invalidate()

                # Execute receive_content_from_generator in thread.
                # (Don't use 'run_in_executor', because we need a daemon.
                t = threading.Thread(target=receive_content_from_generator)
                t.daemon = True
                t.start()
