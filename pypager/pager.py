"""
Pager implementation in Python.
"""
from typing import Optional, Union, Callable
import sys

import prompt_toolkit
from prompt_toolkit.application.current import get_app
import prompt_toolkit.keys
import prompt_toolkit.search
import prompt_toolkit.formatted_text
import prompt_toolkit.key_binding
import prompt_toolkit.widgets.toolbars
import prompt_toolkit.layout.containers
import prompt_toolkit.layout.controls
import prompt_toolkit.layout.processors
import prompt_toolkit.layout.menus
import prompt_toolkit.layout
import prompt_toolkit.buffer
import prompt_toolkit.completion
import prompt_toolkit.document
import prompt_toolkit.enums
import prompt_toolkit.lexers
import prompt_toolkit.styles
import prompt_toolkit.filters
import prompt_toolkit.utils


from .help import HELP
from .source import FormattedTextSource
from .source.pipe_source import PipeSource
from .source.sourcecontainer import SourceContainer
from .style import ui_style
from .layout import PagerLayout

__all__ = [
    "Pager",
]


class Pager:
    """
    The Pager main application.

    Usage::
        p = Pager()
        p.add_source(...)
        p.run()
    """

    def __init__(self) -> None:
        self.source_container = SourceContainer(self.on_message)
        self._message = ''

        self._in_colon_mode = False
        self.has_colon = prompt_toolkit.filters.Condition(
            lambda: self._in_colon_mode)

        self._displaying_help = False
        self.displaying_help = prompt_toolkit.filters.Condition(
            lambda: self._displaying_help)

        self.key_bindings = prompt_toolkit.key_binding.KeyBindings()

        self.layout = PagerLayout(self.source_container.open_file,
                                  has_colon=self.has_colon,
                                  waiting=prompt_toolkit.filters.Condition(
                                      lambda: self.source_container.current_source_info.waiting_for_input_stream),
                                  _get_statusbar_left_tokens=self._get_statusbar_left_tokens,
                                  _get_statusbar_right_tokens=self.source_container._get_statusbar_right_tokens,
                                  source_container=self.source_container,
                                  search_toolbar=self.source_container.search_toolbar,
                                  get_message=lambda: self._message)

        # Input/output.
        # By default, use the stdout device for input.
        # (This makes it possible to pipe data to stdin, but still read key
        # strokes from the TTY).
        from prompt_toolkit.input.defaults import create_input
        input = create_input(sys.stdout)

        self.application = prompt_toolkit.Application(
            input=input,
            layout=prompt_toolkit.layout.Layout(container=self.layout.root),
            enable_page_navigation_bindings=True,
            key_bindings=self.key_bindings,
            style=prompt_toolkit.styles.Style.from_dict(ui_style),
            mouse_support=True,
            after_render=self.source_container._after_render,
            full_screen=True,
            editing_mode=prompt_toolkit.enums.EditingMode.VI,
        )

        # Hide message when a key is pressed.
        self.application.key_processor.before_key_press += self.clear_message

    @classmethod
    def from_pipe(cls, lexer: Optional[prompt_toolkit.lexers.Lexer] = None) -> "Pager":
        """
        Create a pager from another process that pipes in our stdin.
        """
        assert not sys.stdin.isatty()
        self = cls()
        self.source_container.add_source(
            PipeSource(
                fileno=sys.stdin.fileno(), lexer=lexer, encoding=sys.stdin.encoding
            )
        )
        return self

    def bind(self, func: prompt_toolkit.key_binding.key_bindings.KeyHandlerCallable, *keys: Union[prompt_toolkit.keys.Keys, str],
             filter: prompt_toolkit.filters.FilterOrBool = True,
             eager: prompt_toolkit.filters.FilterOrBool = False,
             is_global: prompt_toolkit.filters.FilterOrBool = False,
             save_before: Callable[[prompt_toolkit.key_binding.KeyPressEvent], bool] = (
            lambda e: True),
            record_in_macro: prompt_toolkit.filters.FilterOrBool = True):
        assert keys

        keys = tuple(prompt_toolkit.key_binding.key_bindings._parse_key(k)
                     for k in keys)
        self.key_bindings.bindings.append(
            prompt_toolkit.key_binding.key_bindings.Binding(
                keys,
                func,
                filter=filter,
                eager=eager,
                is_global=is_global,
                save_before=save_before,
                record_in_macro=record_in_macro,
            )
        )
        self.key_bindings._clear_cache()

    def clear_message(self, e):
        self._message = ''

    def on_message(self, msg: str):
        self._message = msg

    def _print_filename(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Print the current file name. "
        self._message = " {} ".format(
            self.source_container.current_source.get_name())

    def _colon(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        self._in_colon_mode = True

    def _cancel_colon(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        self._in_colon_mode = False

    def _any(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        self._in_colon_mode = False
        self._message = "No command."

    def _examine(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        event.app.layout.focus(self.layout.examine.examine_buffer)
        self._in_colon_mode = False

    def _help(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Display Help. "
        self.display_help()

    def display_help(self) -> None:
        """
        Display help text.
        """
        if not self._displaying_help:
            source = FormattedTextSource(HELP, name="<help>")
            self.source_container.add_source(source)
            self._displaying_help = True

    def quit_help(self) -> None:
        """
        Hide the help text.
        """
        if self._displaying_help:
            self.source_container.remove_current_source()
            self._displaying_help = False

    def _get_statusbar_left_tokens(self) -> prompt_toolkit.formatted_text.HTML:
        """
        Displayed at the bottom left.
        """
        if self._displaying_help:
            return prompt_toolkit.formatted_text.HTML(" HELP -- Press <key>[q]</key> when done")
        else:
            return prompt_toolkit.formatted_text.HTML(" (press <key>[h]</key> for help or <key>[q]</key> to quit)")

    def _quit(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Quit. "
        if self._displaying_help:
            self.quit_help()
        else:
            event.app.exit()

    def _repaint(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        event.app.renderer.clear()

    def _suspend(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        " Suspend to bakground. "
        event.app.suspend_to_background()
