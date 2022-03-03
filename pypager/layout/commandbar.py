import prompt_toolkit.layout.containers
import prompt_toolkit.layout.controls
import prompt_toolkit.filters


class CommandBar(prompt_toolkit.layout.containers.ConditionalContainer):
    def __init__(self, has_colon: prompt_toolkit.filters.Condition) -> None:
        super().__init__(
            content=prompt_toolkit.layout.containers.Window(
                prompt_toolkit.layout.controls.FormattedTextControl(" :"), height=1, style="class:examine"
            ),
            filter=has_colon,
        )
