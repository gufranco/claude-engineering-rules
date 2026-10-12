from __future__ import annotations

import time
from collections.abc import Callable
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")
MS_PER_SECOND = 1000.0


def timed(fn: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> tuple[R, float]:
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    return result, (time.perf_counter() - start) * MS_PER_SECOND
