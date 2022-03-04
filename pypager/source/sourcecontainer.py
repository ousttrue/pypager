from typing import Callable, List, Sequence
import weakref
import asyncio
import threading

import prompt_toolkit
import prompt_toolkit.search
import prompt_toolkit.filters
import prompt_toolkit.document
from prompt_toolkit.application.current import get_app
import prompt_toolkit.layout.containers
import prompt_toolkit.lexers
import prompt_toolkit.buffer
import prompt_toolkit.widgets.toolbars
import prompt_toolkit.key_binding
from prompt_toolkit.key_binding.bindings.scroll import (
    scroll_half_page_down,
    scroll_half_page_up,
    scroll_one_line_down,
    scroll_one_line_up,
    scroll_page_down,
    scroll_page_up,
)

from .source_info import SourceInfo
from .pipe_source import FileSource
from . import Source, DummySource


class SourceContainer(prompt_toolkit.layout.containers.Container):
    def __init__(self, on_message: Callable[[str], None]) -> None:
        self.on_message = on_message
        self.sources: List[Source] = []
        # Index in `self.sources`.
        self.current_source_index = 0
        self.highlight_search = True

        self._dummy_source = DummySource()

        # Status information for all sources. Source -> SourceInfo.
        # (Remember this info as long as the Source object exists.)
        self.source_info: weakref.WeakKeyDictionary[
            Source, SourceInfo
        ] = weakref.WeakKeyDictionary()

        # self.current_source_window = current_source_window
        self._bodies: weakref.WeakKeyDictionary[
            str, prompt_toolkit.layout.containers.Window
        ] = weakref.WeakKeyDictionary()  # Map buffer_name to Window.

        # Search buffer.
        self.search_buffer = prompt_toolkit.buffer.Buffer(multiline=False)

        self.search_toolbar = prompt_toolkit.widgets.toolbars.SearchToolbar(
            vi_mode=True, search_buffer=self.search_buffer
        )

        # Returns True when the search buffer is empty.
        self.search_buffer_is_empty = prompt_toolkit.filters.Condition(
            lambda: self.search_buffer.text == "")

        # When this is True, always make sure that the cursor goes to the
        # bottom of the visible content. This is similar to 'tail -f'.
        self.forward_forever = False

        self.line_wrapping_enable = prompt_toolkit.filters.Condition(
            lambda: self.current_source_info.wrap_lines)

        def default_focus() -> bool:
            app = get_app()
            return app.layout.current_window == self.current_source_info.window
        self.default_focus = prompt_toolkit.filters.Condition(default_focus)

    def _get_buffer_window(self) -> prompt_toolkit.layout.containers.Window:
        " Return the Container object according to which Buffer/Source is visible. "
        # return self.pager.current_source_info.window
        return self.current_source_info.window

    def reset(self) -> None:
        for body in self._bodies.values():
            body.reset()

    def get_render_info(self):
        return self._get_buffer_window().render_info

    def preferred_width(self, *a, **kw):
        return self._get_buffer_window().preferred_width(*a, **kw)

    def preferred_height(self, *a, **kw):
        return self._get_buffer_window().preferred_height(*a, **kw)

    def write_to_screen(self, *a, **kw):
        return self._get_buffer_window().write_to_screen(*a, **kw)

    def get_children(self):
        return [self._get_buffer_window()]

    def walk(self, *a, **kw):
        # Required for prompt_toolkit.layout.utils.find_window_for_buffer_name.
        return self._get_buffer_window().walk(*a, **kw)  # type: ignore

    @property
    def current_source(self) -> Source:
        " The current `Source`. "
        try:
            return self.sources[self.current_source_index]
        except IndexError:
            return self._dummy_source

    @property
    def current_source_info(self) -> SourceInfo:
        try:
            return self.source_info[self.current_source]
        except KeyError:
            return SourceInfo(self.current_source, self.highlight_search, self.search_toolbar.control)

    def open_file(self, filename: str) -> None:
        """
        Open this file.
        """
        lexer = prompt_toolkit.lexers.PygmentsLexer.from_filename(
            filename, sync_from_start=False)

        try:
            source = FileSource(filename, lexer=lexer)
        except IOError as e:
            self.on_message("{}".format(e))
        else:
            self.add_source(source)

    def add_source(self, source: Source) -> SourceInfo:
        """
        Add a new :class:`.Source` instance.
        """
        source_info = SourceInfo(
            source, self.highlight_search, self.search_toolbar.control)
        self.source_info[source] = source_info

        self.sources.append(source)

        # Focus
        self.current_source_index = len(self.sources) - 1
        try:
            get_app().layout.focus(source_info.window)
        except Exception:
            pass

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
            self.on_message("Can't remove the last buffer.")

    def focus_previous_source(self) -> None:
        self.current_source_index = (
            self.current_source_index - 1) % len(self.sources)
        get_app().layout.focus(self.current_source_info.window)
        # self._in_colon_mode.set(False)

    def focus_next_source(self) -> None:
        self.current_source_index = (
            self.current_source_index + 1) % len(self.sources)
        get_app().layout.focus(self.current_source_info.window)
        # self._in_colon_mode.set(False)

    def _after_render(self, app: prompt_toolkit.Application) -> None:
        """
        Each time when the rendering is done, we should see whether we need to
        read more data from the input pipe.
        """
        # When the bottom is visible, read more input.
        # Try at least `info.window_height`, if this amount of data is
        # available.
        info = self.get_render_info()
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
                    get_app().invalidate()

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
                get_app().invalidate()

                # Execute receive_content_from_generator in thread.
                # (Don't use 'run_in_executor', because we need a daemon.
                t = threading.Thread(target=receive_content_from_generator)
                t.daemon = True
                t.start()

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

    def _wrap(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Enable/disable line wrapping. "
        source_info = self.current_source_info
        source_info.wrap_lines = not source_info.wrap_lines

    def _toggle_highlighting(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Toggle search highlighting. "
        self.highlight_search = not self.highlight_search

    def _mark(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Mark current position. "
        source_info = self.current_source_info
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
        source_info = self.current_source_info
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

    def _next_file(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Go to next file. "
        self.focus_next_source()

    def _previous_file(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Go to previous file. "
        self.focus_previous_source()

    def _remove_source(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        self.remove_current_source()

    def _cancel_examine(self,  event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Cancel 'Examine' input. "
        event.app.layout.focus(
            self.current_source_info.window)

    def _get_statusbar_right_tokens(self) -> prompt_toolkit.formatted_text.StyleAndTextTuples:
        """
        Displayed at the bottom right.
        """
        source_info = self.current_source_info
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
