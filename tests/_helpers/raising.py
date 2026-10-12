from __future__ import annotations

from collections.abc import Callable
from typing import NoReturn


def raising(error: BaseException) -> Callable[..., NoReturn]:
    def _raise(*_args: object, **_kwargs: object) -> NoReturn:
        raise error

    return _raise
