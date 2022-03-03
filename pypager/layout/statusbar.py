from typing import Optional
import prompt_toolkit.layout.containers
import prompt_toolkit.layout.controls
import prompt_toolkit.enums
import prompt_toolkit.filters
import prompt_toolkit.formatted_text
from ..source import Source


class StatusBar(prompt_toolkit.layout.containers.ConditionalContainer):
    def __init__(self,
                 has_colon: prompt_toolkit.filters.Condition,
                 _get_statusbar_left_tokens,
                 _get_statusbar_right_tokens) -> None:

        super().__init__(
            content=prompt_toolkit.layout.containers.VSplit(
                [
                    prompt_toolkit.layout.containers.Window(
                        height=1,
                        content=prompt_toolkit.layout.controls.FormattedTextControl(
                            _get_statusbar_left_tokens
                        ),
                        style="class:statusbar",
                    ),
                    prompt_toolkit.layout.containers.Window(
                        height=1,
                        content=prompt_toolkit.layout.controls.FormattedTextControl(
                            _get_statusbar_right_tokens
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
