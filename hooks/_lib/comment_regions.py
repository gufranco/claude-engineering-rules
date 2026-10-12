from __future__ import annotations

import re
from dataclasses import dataclass

from _lib.comment_families import (
    JAVASCRIPT,
    SCSS,
    SHELL,
    CommentFamily,
    Premask,
    Region,
)

from _lib.yaml_shell import yaml_shell_ranges

HEREDOC = re.compile(r"(?<!<)<<([-~]?)[ \t]*(['\"]?)([A-Za-z_]\w*)\2")


YAML_BLOCK_INDICATOR = re.compile(
    r"^(?P<indent>[ \t]*)(?:[^#\n]*?:[ \t]+|(?:-[ \t]+)+)?[|>][-+1-9]{0,2}[ \t]*(?:#.*)?$"
)


SCRIPT_BODY = re.compile(r"<script\b[^>]*>(.*?)</script\s*>", re.I | re.S)


STYLE_BODY = re.compile(r"<style\b[^>]*>(.*?)</style\s*>", re.I | re.S)


TEX_VERBATIM = re.compile(
    r"\\begin\{(verbatim\*?|Verbatim|lstlisting|minted)\}(?:\{[^}\n]*\})?(.*?)\\end\{\1\}",
    re.S,
)
NON_NEWLINE = re.compile(r"[^\n]")


ASTRO_FENCE = "---\n"


TextRange = tuple[int, int]


@dataclass(frozen=True, slots=True)
class View:
    text: str
    family: CommentFamily
    premasked: tuple[TextRange, ...]


def blank(text: str, ranges: list[TextRange] | tuple[TextRange, ...]) -> str:
    pieces: list[str] = []
    cursor = 0
    for start, end in sorted(ranges):
        begin = max(start, cursor)
        if begin >= end:
            continue
        pieces.extend((text[cursor:begin], NON_NEWLINE.sub(" ", text[begin:end])))
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces)


def line_ranges(text: str, keep: bool) -> list[TextRange]:
    ranges: list[TextRange] = []
    offset = 0
    for line in text.split("\n"):
        if keep is _is_recipe_line(line):
            ranges.append((offset, offset + len(line)))
        offset += len(line) + 1
    return ranges


def _is_recipe_line(line: str) -> bool:
    return line.startswith("\t")


def _complement(text: str, ranges: list[TextRange]) -> list[TextRange]:
    gaps: list[TextRange] = []
    cursor = 0
    for start, end in sorted(ranges):
        gaps.append((cursor, start))
        cursor = max(cursor, end)
    gaps.append((cursor, len(text)))
    return [(start, end) for start, end in gaps if start < end]


def _markup_regions(
    text: str, family: CommentFamily
) -> list[tuple[CommentFamily, list[TextRange]]]:
    scripts = [match.span(1) for match in SCRIPT_BODY.finditer(text)]
    styles = [match.span(1) for match in STYLE_BODY.finditer(text)]
    if text.startswith(ASTRO_FENCE):
        fence_end = text.find("\n---", len(ASTRO_FENCE) - 1)
        scripts.append((len(ASTRO_FENCE), fence_end if fence_end != -1 else len(text)))
    return [
        (family, scripts + styles),
        (JAVASCRIPT, _complement(text, scripts)),
        (SCSS, _complement(text, styles)),
    ]


def _just_regions(
    text: str, family: CommentFamily
) -> list[tuple[CommentFamily, list[TextRange]]]:
    recipes: list[TextRange] = []
    shebangs: list[TextRange] = []
    offset = 0
    for line in text.split("\n"):
        span = (offset, offset + len(line))
        if line[:1] in (" ", "\t") and line.strip():
            (shebangs if line.strip().startswith("#!") else recipes).append(span)
        offset += len(line) + 1
    return [
        (family, recipes + shebangs),
        (SHELL, _complement(text, recipes) + shebangs),
    ]


def _regions(
    text: str, family: CommentFamily
) -> list[tuple[CommentFamily, list[TextRange]]]:
    if family.region is Region.MARKUP:
        return _markup_regions(text, family)
    if family.region is Region.MAKE:
        return [(family, line_ranges(text, True)), (SHELL, line_ranges(text, False))]
    if family.region is Region.JUST:
        return _just_regions(text, family)
    if family.region is Region.YAML:
        shell = yaml_shell_ranges(text, line_starts(text))
        return [(family, shell), (SHELL, _complement(text, shell))]
    return [(family, [])]


def line_starts(text: str) -> list[int]:
    return [0] + [match.end() for match in re.finditer("\n", text)]


def _heredoc_ranges(text: str) -> list[TextRange]:
    lines = text.split("\n")
    starts = line_starts(text)
    ranges: list[TextRange] = []
    index = 0
    while index < len(lines):
        match = HEREDOC.search(lines[index])
        terminator = _terminator_index(lines, index, match.group(3)) if match else None
        if terminator is None:
            index += 1
            continue
        ranges.append((starts[index + 1], starts[terminator]))
        index = terminator + 1
    return ranges


def _terminator_index(lines: list[str], opener: int, word: str) -> int | None:
    return next(
        (
            index
            for index in range(opener + 1, len(lines))
            if lines[index].strip() == word
        ),
        None,
    )


def _block_scalar_ranges(text: str) -> list[TextRange]:
    lines = text.split("\n")
    starts = line_starts(text)
    ranges: list[TextRange] = []
    index = 0
    while index < len(lines):
        match = YAML_BLOCK_INDICATOR.match(lines[index])
        index += 1
        if match is None:
            continue
        parent = len(match.group("indent"))
        first = index
        while index < len(lines) and _inside_block_scalar(lines[index], parent):
            index += 1
        if index > first:
            ranges.append((starts[first], starts[index - 1] + len(lines[index - 1])))
    return ranges


def _inside_block_scalar(line: str, parent: int) -> bool:
    return not line.strip() or len(line) - len(line.lstrip()) > parent


def _premask_ranges(text: str, family: CommentFamily) -> list[TextRange]:
    ranges: list[TextRange] = []
    if Premask.HEREDOC in family.premasks:
        ranges.extend(_heredoc_ranges(text))
    if Premask.YAML_BLOCK_SCALAR in family.premasks:
        ranges.extend(_block_scalar_ranges(text))
    if Premask.TEX_VERBATIM in family.premasks:
        ranges.extend(match.span(2) for match in TEX_VERBATIM.finditer(text))
    return ranges


def views(text: str, family: CommentFamily) -> list[View]:
    built: list[View] = []
    for region_family, hidden in _regions(text, family):
        region_text = blank(text, hidden)
        premasked = tuple(_premask_ranges(region_text, region_family))
        built.append(View(blank(region_text, premasked), region_family, premasked))
    return built
