import weakref
from typing import TYPE_CHECKING

from prompt_toolkit.application import get_app
from prompt_toolkit.enums import SYSTEM_BUFFER
from prompt_toolkit.filters import Condition, HasArg, HasSearch, has_focus
from prompt_toolkit.formatted_text import HTML, AnyFormattedText, StyleAndTextTuples
from prompt_toolkit.layout.containers import (
    ConditionalContainer,
    Container,
    Float,
    FloatContainer,
    HSplit,
    VSplit,
    Window,
    WindowAlign,
)
import prompt_toolkit.widgets.toolbars
import prompt_toolkit.layout.controls

if TYPE_CHECKING:
    from .pager import Pager

__all__ = [
    "PagerLayout",
]


class _Arg(ConditionalContainer):
    def __init__(self) -> None:
        def get_text() -> str:
            app = get_app()
            if app.key_processor.arg is not None:
                return " %s " % app.key_processor.arg
            else:
                return ""

        super().__init__(
            Window(
                prompt_toolkit.layout.controls.FormattedTextControl(get_text),
                style="class:arg",
                align=WindowAlign.RIGHT,
            ),
            filter=HasArg(),
        )


class Titlebar(prompt_toolkit.widgets.toolbars.FormattedTextToolbar):
    """
    Displayed at the top.
    """

    def __init__(self, pager: "Pager") -> None:
        def get_tokens() -> AnyFormattedText:
            return pager.titlebar_tokens

        super().__init__(get_tokens)


class MessageToolbarBar(prompt_toolkit.widgets.toolbars.FormattedTextToolbar):
    """
    Pop-up (at the bottom) for showing error/status messages.
    """

    def __init__(self, pager: "Pager") -> None:
        def get_tokens():
            return [("class:message", pager.message)] if pager.message else []

        super().__init__(get_tokens)


class _DynamicBody(Container):
    def __init__(self, pager: "Pager") -> None:
        self.pager = pager
        self._bodies: weakref.WeakKeyDictionary[
            str, Window
        ] = weakref.WeakKeyDictionary()  # Map buffer_name to Window.

    def get_buffer_window(self) -> Window:
        " Return the Container object according to which Buffer/Source is visible. "
        return self.pager.current_source_info.window

    def reset(self) -> None:
        for body in self._bodies.values():
            body.reset()

    def get_render_info(self):
        return self.get_buffer_window().render_info

    def preferred_width(self, *a, **kw):
        return self.get_buffer_window().preferred_width(*a, **kw)

    def preferred_height(self, *a, **kw):
        return self.get_buffer_window().preferred_height(*a, **kw)

    def write_to_screen(self, *a, **kw):
        return self.get_buffer_window().write_to_screen(*a, **kw)

    def get_children(self):
        return [self.get_buffer_window()]

    def walk(self, *a, **kw):
        # Required for prompt_toolkit.layout.utils.find_window_for_buffer_name.
        return self.get_buffer_window().walk(*a, **kw)
