from typing import Callable
import prompt_toolkit.layout.containers
import weakref


class SourceContainer(prompt_toolkit.layout.containers.Container):
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
