from typing import TYPE_CHECKING

import prompt_toolkit.filters

if TYPE_CHECKING:
    from .pager import Pager

__all__ = [
    "DisplayingHelp",
]


class _PagerFilter(prompt_toolkit.filters.Filter):
    def __init__(self, pager: "Pager") -> None:
        self.pager = pager


class DisplayingHelp(_PagerFilter):
    def __call__(self) -> bool:
        return self.pager.displaying_help


class BoolFilter(prompt_toolkit.filters.Filter):
    def __init__(self, init=False) -> None:
        super().__init__()
        self.value = init

    def __call__(self) -> bool:
        return self.value
