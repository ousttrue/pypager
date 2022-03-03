from typing import TypeVar, Generic, List, Callable
T = TypeVar('T')


class EventProperty(Generic[T]):
    def __init__(self, init: T) -> None:
        super().__init__()
        self._value: T = init
        self.callbacks: List[Callable[[T], None]] = []

    @property
    def value(self) -> T:
        return self._value

    def set(self, value: T):
        if self._value == value:
            return
        self._value = value
        for callback in self.callbacks:
            callback(value)
