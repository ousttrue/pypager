#!/usr/bin/env python
"""
pypager: A pure Python pager application.
"""


__all__ = [
    "run",
]


def run():
    from pypager.pager import Pager
    import sys
    if not sys.stdin.isatty():
        pager = Pager.from_pipe()
    else:
        import argparse
        parser = argparse.ArgumentParser(
            description="Browse through a text file.")
        parser.add_argument(
            "filename", metavar="filename", nargs="+", help="The file to be displayed."
        )

        args = parser.parse_args()

        pager = Pager()

        # Open files.
        from pypager.source.pipe_source import FileSource
        from prompt_toolkit.lexers import PygmentsLexer
        for filename in args.filename:
            # When a filename is given, take a lexer from that filename.
            lexer = PygmentsLexer.from_filename(
                filename, sync_from_start=False)

            pager.add_source(FileSource(filename, lexer=lexer))

    # Run UI.
    pager.application.run()
