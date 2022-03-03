from typing import Callable
import prompt_toolkit.filters
import prompt_toolkit.buffer
import prompt_toolkit.widgets.toolbars
import prompt_toolkit.layout.containers
import prompt_toolkit.layout.menus
from .statusbar import StatusBar
from .commandbar import CommandBar
from .examinebar import ExamineBar
from .message import MessageContainer
from .arg import Arg
from .loading import Loading
import weakref


class DynamicBody(prompt_toolkit.layout.containers.Container):
    def __init__(self, current_source_window: Callable[[], prompt_toolkit.layout.containers.Window]) -> None:
        self.current_source_window = current_source_window
        self._bodies: weakref.WeakKeyDictionary[
            str, prompt_toolkit.layout.containers.Window
        ] = weakref.WeakKeyDictionary()  # Map buffer_name to Window.

    def _get_buffer_window(self) -> prompt_toolkit.layout.containers.Window:
        " Return the Container object according to which Buffer/Source is visible. "
        # return self.pager.current_source_info.window
        return self.current_source_window()

    def reset(self) -> None:
        for body in self._bodies.values():
            body.reset()

    def get_render_info(self):
        return self._get_buffer_window().render_info

    def preferred_width(self, *a, **kw):
        return self._get_buffer_window().preferred_width(*a, **kw)

    def preferred_height(self, *a, **kw):
        return self._get_buffer_window().preferred_height(*a, **kw)

    def write_to_screen(self, *a, **kw):
        return self._get_buffer_window().write_to_screen(*a, **kw)

    def get_children(self):
        return [self._get_buffer_window()]

    def walk(self, *a, **kw):
        # Required for prompt_toolkit.layout.utils.find_window_for_buffer_name.
        return self._get_buffer_window().walk(*a, **kw)


class PagerLayout:
    def __init__(self,
                 open_file,
                 has_colon: prompt_toolkit.filters.Condition,
                 waiting: prompt_toolkit.filters.Condition,
                 _get_statusbar_left_tokens, _get_statusbar_right_tokens,
                 current_source_window
                 ):
        # Search buffer.
        self.search_buffer = prompt_toolkit.buffer.Buffer(multiline=False)

        # self = PagerLayout(self)
        self.dynamic_body = DynamicBody(current_source_window)

        # Build an interface.

        self.search_toolbar = prompt_toolkit.widgets.toolbars.SearchToolbar(
            vi_mode=True, search_buffer=self.search_buffer
        )

        statusbar = StatusBar(
            has_colon, _get_statusbar_left_tokens, _get_statusbar_right_tokens)
        commandbar = CommandBar(has_colon)

        message = MessageContainer()

        def open_buffer(buff: prompt_toolkit.buffer.Buffer) -> bool:
            # Open file.
            open_file(buff.text)
            return False

        self.root = prompt_toolkit.layout.containers.FloatContainer(
            content=prompt_toolkit.layout.containers.HSplit(
                [
                    self.dynamic_body,
                    self.search_toolbar,
                    prompt_toolkit.widgets.toolbars.SystemToolbar(),
                    statusbar,
                    commandbar,
                    ExamineBar(open_buffer),
                ]
            ),
            floats=[
                prompt_toolkit.layout.containers.Float(
                    right=0, height=1, bottom=1, content=Arg()),
                prompt_toolkit.layout.containers.Float(
                    bottom=1,
                    left=0,
                    right=0,
                    height=1,
                    content=message,
                ),
                prompt_toolkit.layout.containers.Float(
                    right=0,
                    height=1,
                    bottom=1,
                    content=Loading(waiting),
                ),
                prompt_toolkit.layout.containers.Float(xcursor=True, ycursor=True,
                                                       content=prompt_toolkit.layout.menus.MultiColumnCompletionsMenu()),
            ],
        )
