from typing import List, Dict, Tuple
import prompt_toolkit.buffer
import prompt_toolkit.formatted_text
import prompt_toolkit.filters
import prompt_toolkit.layout.containers
import prompt_toolkit.layout.controls
import prompt_toolkit.layout.processors
from . import Source


class _EscapeProcessor(prompt_toolkit.layout.processors.Processor):
    """
    Interpret escape sequences like less/more/most do.
    """

    def __init__(self, source_info: "SourceInfo") -> None:
        self.source_info = source_info

    def apply_transformation(self, ti: prompt_toolkit.layout.processors.TransformationInput) -> prompt_toolkit.layout.processors.Transformation:
        tokens = self.source_info.line_tokens[ti.lineno]
        return prompt_toolkit.layout.processors.Transformation(tokens[:])


def create_buffer_window(source_info: "SourceInfo", highlight_search, search_buffer_control) -> prompt_toolkit.layout.containers.Window:
    """
    Window for the main content.
    """
    # pager = source_info.pager

    input_processors = [
        prompt_toolkit.layout.processors.ConditionalProcessor(
            processor=_EscapeProcessor(source_info),
            filter=prompt_toolkit.filters.Condition(
                lambda: not bool(source_info.source.lexer)),
        ),
        prompt_toolkit.layout.processors.TabsProcessor(),
        prompt_toolkit.layout.processors.ConditionalProcessor(
            processor=prompt_toolkit.layout.processors.HighlightSearchProcessor(),
            filter=prompt_toolkit.filters.Condition(lambda: highlight_search),
        ),
        prompt_toolkit.layout.processors.ConditionalProcessor(
            processor=prompt_toolkit.layout.processors.HighlightIncrementalSearchProcessor(),
            filter=prompt_toolkit.filters.Condition(lambda: highlight_search),
        ),
        prompt_toolkit.layout.processors.HighlightSelectionProcessor(),
        prompt_toolkit.layout.processors.HighlightMatchingBracketProcessor(),
    ]

    @prompt_toolkit.filters.Condition
    def wrap_lines() -> bool:
        return source_info.wrap_lines

    return prompt_toolkit.layout.containers.Window(
        always_hide_cursor=True,
        wrap_lines=wrap_lines,
        content=prompt_toolkit.layout.controls.BufferControl(
            buffer=source_info.buffer,
            lexer=source_info.source.lexer,
            input_processors=input_processors,
            include_default_input_processors=False,
            preview_search=True,
            search_buffer_control=search_buffer_control
        ),
    )


class SourceInfo:
    """
    For each opened source, we keep this list of pager data.
    """

    _buffer_counter = 0  # Counter to generate unique buffer names.

    def __init__(self, source: Source, highlight_search, search_buffer_control) -> None:
        self.source = source

        self.buffer = prompt_toolkit.buffer.Buffer(read_only=True)

        # List of lines. (Each line is a list of (token, text) tuples itself.)
        self.line_tokens: List[prompt_toolkit.formatted_text.StyleAndTextTuples] = [
            []]

        # Marks. (Mapping from mark name to (cursor position, scroll_offset).)
        self.marks: Dict[str, Tuple[int, int]] = {}

        # `Pager` sets this flag when he starts reading the generator of this
        # source in a coroutine.
        self.waiting_for_input_stream = False

        # Enable/disable line wrapping.
        self.wrap_lines = False

        self.window = create_buffer_window(
            self, highlight_search, search_buffer_control)
