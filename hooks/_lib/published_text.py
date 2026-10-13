from __future__ import annotations

import re

from _lib.comment_regions import views
from _lib.comment_resolution import resolve_family
from _lib.comment_syntax import spans

SCRATCH_PATH = re.compile(r"^(?:/private)?/tmp/claude-\d+/")


def is_scratch_path(path: str) -> bool:
    return SCRATCH_PATH.match(path) is not None


def published_text(path: str, text: str) -> str:
    family = resolve_family(path, text)
    if family is None:
        return text
    return "\n".join(
        view.text[span.start : span.end]
        for view in views(text, family)
        for span in spans(view.text, view.family)
        if span.comment
    )
