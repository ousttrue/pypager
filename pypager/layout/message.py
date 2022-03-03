from typing import Callable
import prompt_toolkit.layout.containers
import prompt_toolkit.widgets.toolbars
import prompt_toolkit.filters


class MessageContainer(prompt_toolkit.layout.containers.ConditionalContainer):
    def __init__(self, get_message: Callable[[], str]) -> None:

        def get_message_tokens():
            msg = get_message()
            return [("class:message", msg)] if msg else []

        super().__init__(
            content=prompt_toolkit.widgets.toolbars.FormattedTextToolbar(
                get_message_tokens),
            filter=prompt_toolkit.filters.Condition(
                lambda: bool(get_message())),
        )
