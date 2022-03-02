import prompt_toolkit.layout.containers
import prompt_toolkit.layout.controls
import prompt_toolkit.filters
from prompt_toolkit.application.current import get_app


class Arg(prompt_toolkit.layout.containers.ConditionalContainer):
    def __init__(self) -> None:
        def get_text() -> str:
            app = get_app()
            if app.key_processor.arg is not None:
                return " %s " % app.key_processor.arg
            else:
                return ""

        super().__init__(
            prompt_toolkit.layout.containers.Window(
                prompt_toolkit.layout.controls.FormattedTextControl(get_text),
                style="class:arg",
                align=prompt_toolkit.layout.containers.WindowAlign.RIGHT,
            ),
            filter=prompt_toolkit.filters.HasArg(),
        )
