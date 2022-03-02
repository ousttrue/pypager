"""
A pager implementation in Python.
"""
__version__ = "3.0.0"

from .pager import Pager
from .source import FormattedTextSource, GeneratorSource, StringSource
from .source.pipe_source import PipeSource

__all__ = [
    "FormattedTextSource",
    "GeneratorSource",
    "Pager",
    "PipeSource",
    "StringSource",
]
