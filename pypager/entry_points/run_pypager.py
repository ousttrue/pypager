#!/usr/bin/env python
"""
pypager: A pure Python pager application.
"""
import argparse
import os
import sys

from prompt_toolkit.lexers import PygmentsLexer

from pypager.pager import Pager
from pypager.source.pipe_source import FileSource

__all__ = [
    "run",
]


def run():
    if not sys.stdin.isatty():
        pager = Pager.from_pipe()
        pager.run()
    else:
        parser = argparse.ArgumentParser(
            description="Browse through a text file.")
        parser.add_argument(
            "filename", metavar="filename", nargs="+", help="The file to be displayed."
        )
        parser.add_argument(
            "--vi", help="Prefer Vi key bindings.", action="store_true")
        parser.add_argument(
            "--emacs", help="Prefer Emacs key bindings.", action="store_true"
        )

        args = parser.parse_args()

        pager = Pager()

        # Open files.
        for filename in args.filename:
            # When a filename is given, take a lexer from that filename.
            lexer = PygmentsLexer.from_filename(
                filename, sync_from_start=False)

            pager.add_source(FileSource(filename, lexer=lexer))

        # Run UI.
        pager.run()
