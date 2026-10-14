from __future__ import annotations

import os
from typing import Final

_STAGE_FILTER_ENV: Final[str] = "MUTATION_METHOD_TC39_STAGE_FILTER"
_DEFAULT_STAGE: Final[int] = 4
_MIN_STAGE: Final[int] = 2


def tc39_stage_filter() -> int:
    raw = os.environ.get(_STAGE_FILTER_ENV, str(_DEFAULT_STAGE))
    try:
        val = int(raw)
    except ValueError:
        return _DEFAULT_STAGE
    return min(max(val, _MIN_STAGE), _DEFAULT_STAGE)
