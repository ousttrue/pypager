import prompt_toolkit.layout.containers
import prompt_toolkit.widgets.toolbars
import prompt_toolkit.filters


class MessageContainer(prompt_toolkit.layout.containers.ConditionalContainer):
    def __init__(self) -> None:
        self.message = None

        def get_message_tokens():
            return [("class:message", self.message)] if self.message else []

        super().__init__(
            content=prompt_toolkit.widgets.toolbars.FormattedTextToolbar(
                get_message_tokens),
            filter=prompt_toolkit.filters.Condition(
                lambda: bool(self.message)),
        )
