import prompt_toolkit.layout.containers
import prompt_toolkit.layout.controls


class CommandBar(prompt_toolkit.layout.containers.ConditionalContainer):
    def __init__(self, has_colon) -> None:
        super().__init__(
            content=prompt_toolkit.layout.containers.Window(
                prompt_toolkit.layout.controls.FormattedTextControl(" :"), height=1, style="class:examine"
            ),
            filter=has_colon,
        )
