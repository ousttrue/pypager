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
from ..source.sourcecontainer import SourceContainer


class PagerLayout:
    def __init__(self,
                 open_file,
                 has_colon: prompt_toolkit.filters.Condition,
                 waiting: prompt_toolkit.filters.Condition,
                 _get_statusbar_left_tokens, _get_statusbar_right_tokens,
                 source_container: SourceContainer,
                 search_toolbar: prompt_toolkit.widgets.toolbars.SearchToolbar):

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
                    source_container,
                    search_toolbar,
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
