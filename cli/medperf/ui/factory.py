from .cli import CLI
from .interface import UI
from .stdin import StdIn
from medperf.exceptions import InvalidArgumentError


class UIFactory:
    @staticmethod
    def create_ui(name: str) -> UI:
        name = name.lower()
        if name == "cli":
            return CLI()
        elif name == "stdin":
            return StdIn()
        else:
            msg = f"{name}: the indicated UI interface doesn't exist"
            raise InvalidArgumentError(msg)
