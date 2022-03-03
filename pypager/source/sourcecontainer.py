from typing import Callable, List, Sequence
import weakref
import asyncio
import threading

import prompt_toolkit
import prompt_toolkit.document
from prompt_toolkit.application.current import get_app
import prompt_toolkit.layout.containers
import prompt_toolkit.lexers
import prompt_toolkit.buffer
import prompt_toolkit.widgets.toolbars

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

        # When this is True, always make sure that the cursor goes to the
        # bottom of the visible content. This is similar to 'tail -f'.
        self.forward_forever = False

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
