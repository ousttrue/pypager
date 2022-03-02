from typing import Optional
import prompt_toolkit.layout.containers
import prompt_toolkit.layout.controls
import prompt_toolkit.enums
import prompt_toolkit.filters
import prompt_toolkit.formatted_text
from ..source import Source


class StatusBar(prompt_toolkit.layout.containers.ConditionalContainer):
    def __init__(self, source_info, has_colon) -> None:
        self.source_info = source_info
        super().__init__(
            content=prompt_toolkit.layout.containers.VSplit(
                [
                    prompt_toolkit.layout.containers.Window(
                        height=1,
                        content=prompt_toolkit.layout.controls.FormattedTextControl(
                            self._get_statusbar_left_tokens
                        ),
                        style="class:statusbar",
                    ),
                    prompt_toolkit.layout.containers.Window(
                        height=1,
                        content=prompt_toolkit.layout.controls.FormattedTextControl(
                            self._get_statusbar_right_tokens
                        ),
                        style="class:statusbar.cursorposition",
                        align=prompt_toolkit.layout.containers.WindowAlign.RIGHT,
                    ),
                ]
            ),
            filter=~prompt_toolkit.filters.HasSearch()
            & ~prompt_toolkit.filters.has_focus(prompt_toolkit.enums.SYSTEM_BUFFER)
            & ~has_colon
            & ~prompt_toolkit.filters.has_focus("EXAMINE"),
        )
        self.displaying_help = False
        self.current_source: Optional[Source] = None

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
        assert(self.current_source)
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
