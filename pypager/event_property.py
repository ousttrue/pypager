from typing import TypeVar, Generic, List, Callable
T = TypeVar('T')


class EventProperty(Generic[T]):
    def __init__(self, init: T) -> None:
        super().__init__()
        self.value: T = init
        self.callbacks: List[Callable[[T], None]] = []

    def set(self, value: T):
        if self.value == value:
            return
        self.value = value
        for callback in self.callbacks:
            callback(value)
