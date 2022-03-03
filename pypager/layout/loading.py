import prompt_toolkit.layout.containers
import prompt_toolkit.widgets.toolbars
import prompt_toolkit.filters


class Loading(prompt_toolkit.layout.containers.ConditionalContainer):
    def __init__(self, waiting: prompt_toolkit.filters.Condition):
        super().__init__(
            content=prompt_toolkit.widgets.toolbars.FormattedTextToolbar(
                lambda: [("class:loading", " Loading... ")],
            ),
            filter=waiting,
        )
