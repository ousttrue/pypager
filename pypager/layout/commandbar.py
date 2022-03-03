import prompt_toolkit.layout.containers
import prompt_toolkit.layout.controls
from ..filters import BoolFilter


class CommandBar(prompt_toolkit.layout.containers.ConditionalContainer):
    def __init__(self) -> None:
        self.in_colon_mode = BoolFilter(False)

        super().__init__(
            content=prompt_toolkit.layout.containers.Window(
                prompt_toolkit.layout.controls.FormattedTextControl(" :"), height=1, style="class:examine"
            ),
            filter=self.in_colon_mode,
        )
