from typing import Optional, Generator
from abc import ABCMeta, abstractmethod
import prompt_toolkit.lexers
import prompt_toolkit.formatted_text
import prompt_toolkit.layout.utils

__all__ = [
    "Source",
    "DummySource",
    "GeneratorSource",
    "StringSource",
    "FormattedTextSource",
]


class Source(metaclass=ABCMeta):
    #: The lexer to be used in the layout.
    lexer: Optional[prompt_toolkit.lexers.Lexer] = None

    @abstractmethod
    def get_name(self) -> str:
        " Return the filename or name for this input. "

    @abstractmethod
    def eof(self) -> bool:
        " Return True when we reached the end of the input. "

    @abstractmethod
    def read_chunk(self) -> prompt_toolkit.formatted_text.StyleAndTextTuples:
        """
        Read data from input. Return a list of token/text tuples.

        This can be blocking and will be called in another thread.
        """

    def close(self) -> None:
        pass


class DummySource(Source):
    """
    Empty source.
    """

    def get_name(self) -> str:
        return ""

    def eof(self) -> bool:
        return True

    def read_chunk(self) -> prompt_toolkit.formatted_text.StyleAndTextTuples:
        return []


class GeneratorSource(Source):
    """
    When the input is coming from a Python generator.
    """

    def __init__(
        self,
        generator: Generator[prompt_toolkit.formatted_text.StyleAndTextTuples, None, None],
        lexer: Optional[prompt_toolkit.lexers.Lexer] = None,
        name: str = "",
    ) -> None:
        self._eof = False
        self.generator = generator
        self.lexer = lexer
        self.name = name

    def get_name(self) -> str:
        return self.name

    def eof(self) -> bool:
        return self._eof

    def read_chunk(self) -> prompt_toolkit.formatted_text.StyleAndTextTuples:
        " Read data from input. Return a list of token/text tuples. "
        try:
            return prompt_toolkit.layout.utils.explode_text_fragments(next(self.generator))
        except StopIteration:
            self._eof = True
            return []


class StringSource(Source):
    """
    Take a Python string is input for the pager.
    """

    def __init__(
        self, text: str, lexer: Optional[prompt_toolkit.lexers.Lexer] = None, name: str = ""
    ) -> None:
        self.text = text
        self.lexer = lexer
        self.name = name
        self._read = False

    def get_name(self) -> str:
        return self.name

    def eof(self) -> bool:
        return self._read

    def read_chunk(self) -> prompt_toolkit.formatted_text.StyleAndTextTuples:
        if self._read:
            return []
        else:
            self._read = True
            return prompt_toolkit.layout.utils.explode_text_fragments([("", self.text)])


class FormattedTextSource(Source):
    """
    Take any kind of prompt_toolkit formatted text as input for the pager.
    """

    def __init__(self, formatted_text: prompt_toolkit.formatted_text. AnyFormattedText, name: str = "") -> None:
        self.formatted_text = prompt_toolkit.formatted_text.to_formatted_text(
            formatted_text)
        self.name = name
        self._read = False

    def get_name(self) -> str:
        return self.name

    def eof(self) -> bool:
        return self._read

    def read_chunk(self) -> prompt_toolkit.formatted_text.StyleAndTextTuples:
        if self._read:
            return []
        else:
            self._read = True
            return prompt_toolkit.layout.utils.explode_text_fragments(self.formatted_text)
