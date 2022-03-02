"""
Pager implementation in Python.


class Pager:
    sources: List[Source]
    source_info: Dict[Source, SourceInfo]

SourceInfo 
    => Source
    => Window
"""

import asyncio
import sys
import threading
import weakref
from typing import List, Optional, Sequence

import prompt_toolkit.formatted_text
import prompt_toolkit.widgets.toolbars
import prompt_toolkit.layout.controls
from prompt_toolkit.application.current import get_app
from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import PathCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.enums import EditingMode
from prompt_toolkit.formatted_text import StyleAndTextTuples, HTML
from prompt_toolkit.input.defaults import create_input
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.lexers import Lexer, PygmentsLexer
from prompt_toolkit.styles import Style
from prompt_toolkit.input import Input
from prompt_toolkit.output import Output
from prompt_toolkit.lexers import SimpleLexer
from prompt_toolkit.layout.processors import (
    BeforeInput,
)
from prompt_toolkit.layout.menus import MultiColumnCompletionsMenu
from prompt_toolkit.widgets.toolbars import (
    FormattedTextToolbar,
    SearchToolbar,
    SystemToolbar,
)
from prompt_toolkit.layout.containers import (
    ConditionalContainer,
    Container,
    Float,
    FloatContainer,
    HSplit,
    VSplit,
    Window,
    WindowAlign,
)
import prompt_toolkit.filters
from prompt_toolkit.filters import Condition, HasArg, HasSearch, has_focus
from prompt_toolkit.enums import SYSTEM_BUFFER

from .filters import HasColon
from .help import HELP
from .key_bindings import create_key_bindings
from .source import DummySource, FormattedTextSource, Source
from .source.pipe_source import FileSource, PipeSource
from .source.source_info import SourceInfo
from .style import ui_style

__all__ = [
    "Pager",
]


class _Arg(ConditionalContainer):
    def __init__(self) -> None:
        def get_text() -> str:
            app = get_app()
            if app.key_processor.arg is not None:
                return " %s " % app.key_processor.arg
            else:
                return ""

        super().__init__(
            Window(
                prompt_toolkit.layout.controls.FormattedTextControl(get_text),
                style="class:arg",
                align=WindowAlign.RIGHT,
            ),
            filter=HasArg(),
        )


class _DynamicBody(Container):
    def __init__(self, pager: "Pager") -> None:
        self.pager = pager
        self._bodies: weakref.WeakKeyDictionary[
            str, Window
        ] = weakref.WeakKeyDictionary()  # Map buffer_name to Window.

    def get_buffer_window(self) -> Window:
        " Return the Container object according to which Buffer/Source is visible. "
        return self.pager.current_source_info.window

    def reset(self) -> None:
        for body in self._bodies.values():
            body.reset()

    def get_render_info(self):
        return self.get_buffer_window().render_info

    def preferred_width(self, *a, **kw):
        return self.get_buffer_window().preferred_width(*a, **kw)

    def preferred_height(self, *a, **kw):
        return self.get_buffer_window().preferred_height(*a, **kw)

    def write_to_screen(self, *a, **kw):
        return self.get_buffer_window().write_to_screen(*a, **kw)

    def get_children(self):
        return [self.get_buffer_window()]

    def walk(self, *a, **kw):
        # Required for prompt_toolkit.layout.utils.find_window_for_buffer_name.
        return self.get_buffer_window().walk(*a, **kw)


class Pager:
    """
    The Pager main application.

    Usage::
        p = Pager()
        p.add_source(...)
        p.run()

    :param source: :class:`.Source` instance.
    :param lexer: Prompt_toolkit `lexer` instance.
    :param style: Prompt_toolkit `Style` instance.
    :param search_text: `None` or the search string that is highlighted.
    """

    def __init__(
        self,
        *,
        style: Optional[Style] = None,
        search_text: Optional[str] = None,
        titlebar_tokens=None,
        input: Optional[Input] = None,
        output: Optional[Output] = None,
    ) -> None:
        self.sources: List[Source] = []
        self.current_source_index = 0  # Index in `self.sources`.
        self.highlight_search = True
        self.in_colon_mode = False
        self.message: Optional[str] = None
        self.displaying_help = False
        self.search_text = search_text
        self.display_titlebar = bool(titlebar_tokens)
        self.titlebar_tokens = titlebar_tokens or []

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

        def open_file(buff: Buffer) -> bool:
            # Open file.
            self.open_file(buff.text)
            return False

        # Buffer for the 'Examine:' input.
        self.examine_buffer = Buffer(
            name="EXAMINE",
            completer=PathCompleter(expanduser=True),
            accept_handler=open_file,
            multiline=False,
        )

        # Search buffer.
        self.search_buffer = Buffer(multiline=False)

        # self = PagerLayout(self)
        self.dynamic_body = _DynamicBody(self)

        # Build an interface.
        has_colon = HasColon(self)

        self.examine_control = prompt_toolkit.layout.controls.BufferControl(
            buffer=self.examine_buffer,
            lexer=SimpleLexer(style="class:examine,examine-text"),
            input_processors=[BeforeInput(
                lambda: [("class:examine", " Examine: ")])],
        )

        self.search_toolbar = SearchToolbar(
            vi_mode=True, search_buffer=self.search_buffer
        )

        def get_titlebar_tokens() -> prompt_toolkit.formatted_text.AnyFormattedText:
            return self.titlebar_tokens

        def get_message_tokens() -> prompt_toolkit.formatted_text.AnyFormattedText:
            return [("class:message", self.message)] if self.message else []

        self.container = FloatContainer(
            content=HSplit(
                [
                    ConditionalContainer(
                        content=prompt_toolkit.widgets.toolbars.FormattedTextToolbar(
                            get_titlebar_tokens),
                        filter=prompt_toolkit.filters.Condition(
                            lambda: self.display_titlebar),
                    ),
                    self.dynamic_body,
                    self.search_toolbar,
                    SystemToolbar(),
                    ConditionalContainer(
                        content=VSplit(
                            [
                                Window(
                                    height=1,
                                    content=prompt_toolkit.layout.controls.FormattedTextControl(
                                        self._get_statusbar_left_tokens
                                    ),
                                    style="class:statusbar",
                                ),
                                Window(
                                    height=1,
                                    content=prompt_toolkit.layout.controls.FormattedTextControl(
                                        self._get_statusbar_right_tokens
                                    ),
                                    style="class:statusbar.cursorposition",
                                    align=WindowAlign.RIGHT,
                                ),
                            ]
                        ),
                        filter=~HasSearch()
                        & ~has_focus(SYSTEM_BUFFER)
                        & ~has_colon
                        & ~has_focus("EXAMINE"),
                    ),
                    ConditionalContainer(
                        content=Window(
                            prompt_toolkit.layout.controls.FormattedTextControl(" :"), height=1, style="class:examine"
                        ),
                        filter=has_colon,
                    ),
                    ConditionalContainer(
                        content=Window(
                            self.examine_control, height=1, style="class:examine"
                        ),
                        filter=has_focus(self.examine_buffer),
                    ),
                ]
            ),
            floats=[
                Float(right=0, height=1, bottom=1, content=_Arg()),
                Float(
                    bottom=1,
                    left=0,
                    right=0,
                    height=1,
                    content=ConditionalContainer(
                        content=prompt_toolkit.widgets.toolbars.FormattedTextToolbar(
                            get_message_tokens),
                        filter=Condition(lambda: bool(self.message)),
                    ),
                ),
                Float(
                    right=0,
                    height=1,
                    bottom=1,
                    content=ConditionalContainer(
                        content=FormattedTextToolbar(
                            lambda: [("class:loading", " Loading... ")],
                        ),
                        filter=Condition(
                            lambda: self.current_source_info.waiting_for_input_stream
                        ),
                    ),
                ),
                Float(xcursor=True, ycursor=True,
                      content=MultiColumnCompletionsMenu()),
            ],
        )

        # Input/output.
        if input is None:
            # By default, use the stdout device for input.
            # (This makes it possible to pipe data to stdin, but still read key
            # strokes from the TTY).
            input = create_input(sys.stdout)

        bindings = create_key_bindings(self)
        self.application: Application[None] = Application(
            input=input,
            output=output,
            layout=Layout(container=self.container),
            enable_page_navigation_bindings=True,
            key_bindings=bindings,
            style=style or Style.from_dict(ui_style),
            mouse_support=True,
            after_render=self._after_render,
            full_screen=True,
            editing_mode=EditingMode.VI,
        )

        # Hide message when a key is pressed.
        def key_pressed(_) -> None:
            self.message = None

        self.application.key_processor.before_key_press += key_pressed

    def _get_statusbar_left_tokens(self) -> HTML:
        """
        Displayed at the bottom left.
        """
        if self.displaying_help:
            return HTML(" HELP -- Press <key>[q]</key> when done")
        else:
            return HTML(" (press <key>[h]</key> for help or <key>[q]</key> to quit)")

    def _get_statusbar_right_tokens(self) -> StyleAndTextTuples:
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

    @classmethod
    def from_pipe(cls, lexer: Optional[Lexer] = None) -> "Pager":
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
        lexer = PygmentsLexer.from_filename(filename, sync_from_start=False)

        try:
            source = FileSource(filename, lexer=lexer)
        except IOError as e:
            self.message = "{}".format(e)
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
        self.application.layout.focus(source_info.window)

        return source_info

    def remove_current_source(self) -> None:
        """
        Remove the current source from the self.
        (If >1 source is left.)
        """
        if len(self.sources) > 1:
            current_source_index = self.current_source

            # Focus the previous source.
            self.focus_previous_source()

            # Remove the last source.
            self.sources.remove(current_source_index)
        else:
            self.message = "Can't remove the last buffer."

    def focus_previous_source(self) -> None:
        self.current_source_index = (
            self.current_source_index - 1) % len(self.sources)
        self.application.layout.focus(self.current_source_info.window)
        self.in_colon_mode = False

    def focus_next_source(self) -> None:
        self.current_source_index = (
            self.current_source_index + 1) % len(self.sources)
        self.application.layout.focus(self.current_source_info.window)
        self.in_colon_mode = False

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

    def _after_render(self, app: Application) -> None:
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

                def handle_content(tokens: StyleAndTextTuples) -> List[str]:
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
                    document = Document(
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

    def _before_run(self) -> None:
        # Set search highlighting.
        if self.search_text:
            self.application.current_search_state.text = self.search_text

    def run(self) -> None:
        """
        Create an event loop for the application and run it.
        """
        try:
            self._before_run()
            return self.application.run()
        finally:
            # XXX: Close all sources which are opened by the pager itself.
            pass

    async def run_async(self) -> None:
        """
        Create an event loop for the application and run it.
        """
        try:
            self._before_run()
            return await self.application.run_async()
        finally:
            # XXX: Close all sources which are opened by the pager itself.
            pass
