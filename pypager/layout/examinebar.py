import prompt_toolkit.layout.containers
import prompt_toolkit.layout.controls
import prompt_toolkit.layout.processors
import prompt_toolkit.buffer
import prompt_toolkit.completion
import prompt_toolkit.lexers
import prompt_toolkit.filters


class ExamineBar(prompt_toolkit.layout.containers.ConditionalContainer):
    def __init__(self, open_file) -> None:
        # Buffer for the 'Examine:' input.
        def open_buffer(buff: prompt_toolkit.buffer.Buffer) -> bool:
            # Open file.
            open_file(buff.text)
            return False

        self.examine_buffer = prompt_toolkit.buffer.Buffer(
            name="EXAMINE",
            completer=prompt_toolkit.completion.PathCompleter(expanduser=True),
            accept_handler=open_buffer,
            multiline=False,
        )

        self.examine_control = prompt_toolkit.layout.controls.BufferControl(
            buffer=self.examine_buffer,
            lexer=prompt_toolkit.lexers.SimpleLexer(
                style="class:examine,examine-text"),
            input_processors=[prompt_toolkit.layout.processors.BeforeInput(
                lambda: [("class:examine", " Examine: ")])],
        )

        super().__init__(
            content=prompt_toolkit.layout.containers.Window(
                self.examine_control, height=1, style="class:examine"
            ),
            filter=prompt_toolkit.filters.has_focus(
                self.examine_buffer),
        )
