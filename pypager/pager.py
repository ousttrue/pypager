"""
Pager implementation in Python.


class Pager:
    sources: List[Source]
    source_info: Dict[Source, SourceInfo]

SourceInfo 
    => Source
    => Window
"""
from typing import List, Optional, Sequence
import asyncio
import sys
import threading
import weakref

import prompt_toolkit
import prompt_toolkit.formatted_text
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
from prompt_toolkit.input.defaults import create_input
import prompt_toolkit.filters


from .help import HELP
from .key_bindings import create_key_bindings
from .source import DummySource, FormattedTextSource, Source
from .source.pipe_source import FileSource, PipeSource
from .source.source_info import SourceInfo
from .style import ui_style
from .event_property import EventProperty

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

        # Create prompt_toolkit stuff.

        # Search buffer.
        self.search_buffer = prompt_toolkit.buffer.Buffer(multiline=False)

        # self = PagerLayout(self)
        from .layout.dynamicbody import DynamicBody
        self.dynamic_body = DynamicBody(self)

        # Build an interface.

        self.search_toolbar = prompt_toolkit.widgets.toolbars.SearchToolbar(
            vi_mode=True, search_buffer=self.search_buffer
        )

        # Input/output.
        # By default, use the stdout device for input.
        # (This makes it possible to pipe data to stdin, but still read key
        # strokes from the TTY).
        input = create_input(sys.stdout)

        bindings = create_key_bindings(self)
        self.application = prompt_toolkit.Application(
            input=input,
            layout=prompt_toolkit.layout.Layout(container=self._layout()),
            enable_page_navigation_bindings=True,
            key_bindings=bindings,
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

    @property
    def in_colon_mode(self) -> bool:
        return self._in_colon_mode.value

    @in_colon_mode.setter
    def in_colon_mode(self, value: bool):
        self._in_colon_mode.set(value)

    def _layout(self) -> prompt_toolkit.layout.containers.Container:
        # has_colon = HasColon(self)

        from .layout.statusbar import StatusBar
        from .layout.commandbar import CommandBar
        from .layout.examinebar import ExamineBar
        from .layout.message import MessageContainer
        from .layout.arg import Arg
        statusbar = StatusBar(self.source_info)
        commandbar = CommandBar()

        def on_source_updated(index: int):
            current_source = self.sources[index]
            statusbar.current_source = current_source
        self.current_source_index.callbacks.append(on_source_updated)

        def on_has_colon(has: bool):
            statusbar.in_colon_mode.value = has
            commandbar.in_colon_mode.value = has
        self._in_colon_mode.callbacks.append(on_has_colon)

        message = MessageContainer()

        def on_message_updated(text: str):
            self._message.set(text)
        self._message.callbacks.append(on_message_updated)

        return prompt_toolkit.layout.containers.FloatContainer(
            content=prompt_toolkit.layout.containers.HSplit(
                [
                    self.dynamic_body,
                    self.search_toolbar,
                    prompt_toolkit.widgets.toolbars.SystemToolbar(),
                    statusbar,
                    commandbar,
                    ExamineBar(self.open_file),
                ]
            ),
            floats=[
                prompt_toolkit.layout.containers.Float(
                    right=0, height=1, bottom=1, content=Arg()),
                prompt_toolkit.layout.containers.Float(
                    bottom=1,
                    left=0,
                    right=0,
                    height=1,
                    content=message,
                ),
                prompt_toolkit.layout.containers.Float(
                    right=0,
                    height=1,
                    bottom=1,
                    content=prompt_toolkit.layout.containers.ConditionalContainer(
                        content=prompt_toolkit.widgets.toolbars.FormattedTextToolbar(
                            lambda: [("class:loading", " Loading... ")],
                        ),
                        filter=prompt_toolkit.filters.Condition(
                            lambda: self.current_source_info.waiting_for_input_stream
                        ),
                    ),
                ),
                prompt_toolkit.layout.containers.Float(xcursor=True, ycursor=True,
                                                       content=prompt_toolkit.layout.menus.MultiColumnCompletionsMenu()),
            ],
        )

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
            self._message.set("{}".format(e))
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
        info = self.dynamic_body.get_render_info()
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
