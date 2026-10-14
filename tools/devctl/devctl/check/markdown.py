"""Markdown parsing for the map checks.

Supports inline Markdown links and full, collapsed, or shortcut references with
single-line definitions, optional titles, angle-bracket paths, escapes, and balanced
parentheses. Fenced and inline code are skipped. HTML links, autolinks, and heading
anchors are not checked; use Markdown links for maintained local navigation.
"""

from __future__ import annotations

import re

LABEL = r"\[((?:\\.|[^\]\\\n])*)\]"
TITLE = r"""(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\((?:\\.|[^)\\])*\))"""

_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


def blank(text: str) -> str:
    return re.sub(r"[^\n]", " ", text)


def without_fences(text: str) -> str:
    """The text with fenced code blanked. Line numbers and line lengths stay."""
    lines = []
    fence = ""
    for line in text.splitlines(keepends=True):
        opening = _FENCE.match(line)
        if fence:
            lines.append(blank(line))
            if re.fullmatch(rf" {{0,3}}{fence[0]}{{{len(fence)},}}\s*", line):
                fence = ""
        elif opening:
            fence = opening.group(1)
            lines.append(blank(line))
        else:
            lines.append(line)
    return "".join(lines)


def without_code(text: str) -> str:
    """The text with fenced code and inline code spans blanked."""
    return re.sub(
        r"(?<![\\`])(`+)(?!`)[\s\S]*?(?<!`)\1(?!`)",
        lambda match: blank(match.group()),
        without_fences(text),
    )


def fenced_blocks(text: str) -> list[list[str]]:
    """Return the content lines of each closed fenced code block."""
    blocks: list[list[str]] = []
    fence = ""
    current: list[str] = []
    for line in text.splitlines():
        if not fence:
            if opening := _FENCE.match(line):
                fence = opening.group(1)
            continue
        if re.fullmatch(rf" {{0,3}}{re.escape(fence[0])}{{{len(fence)},}}\s*", line):
            blocks.append(current)
            fence, current = "", []
        else:
            current.append(line)
    return blocks


def destination(text: str) -> tuple[str, str]:
    text = text.lstrip()
    angle = re.match(r"<((?:\\.|[^<>\\\n])*)>", text)
    if angle:
        return angle.group(1), text[angle.end() :]
    depth = 0
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\\" and index + 1 < len(text):
            index += 2
            continue
        if char.isspace() or (char == ")" and depth == 0):
            break
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char in "<>":
            raise ValueError("invalid navigation link syntax; enclose spaced paths in <...>")
        index += 1
    if depth:
        raise ValueError("invalid navigation link syntax; balance destination parentheses")
    return text[:index], text[index:]


def reference_key(label: str) -> str:
    return " ".join(label.split()).casefold()


def _reference_definitions(text: str) -> tuple[dict[str, str], str]:
    """The targets of the single-line reference definitions, and the text with them blanked."""
    references: dict[str, str] = {}
    definitions = list(re.finditer(rf"(?m)^ {{0,3}}{LABEL}:[ \t]*(.*)$", text))
    for definition in definitions:
        line = text.count("\n", 0, definition.start()) + 1
        try:
            target, rest = destination(definition.group(2))
            if not target or not re.fullmatch(rf"\s*(?:{TITLE})?\s*", rest):
                raise ValueError(
                    "invalid navigation reference syntax; use a single-line definition"
                )
        except ValueError as error:
            raise ValueError(f"{line}: {error}") from error
        references.setdefault(reference_key(definition.group(1)), target)
    for definition in reversed(definitions):
        text = text[: definition.start()] + blank(definition.group()) + text[definition.end() :]
    return references, text


def _inline_link(text: str, position: int, line: int) -> tuple[str, int]:
    """The target of the inline link whose "(" is at position, and where scanning resumes."""
    try:
        target, rest = destination(text[position + 1 :])
        closing = re.match(rf"\s*(?:{TITLE}\s*)?\)", rest)
        if not closing:
            raise ValueError("invalid navigation link syntax; use a path and optional title")
        return target, len(text) - len(rest) + closing.end()
    except ValueError as error:
        raise ValueError(f"{line}: {error}") from error


def navigation_links(text: str) -> list[tuple[int, str]]:
    """The (line, target) of every Markdown link outside code. ValueError names a bad line."""
    references, text = _reference_definitions(without_code(text))
    links: list[tuple[int, str]] = []
    position = 0
    while match := re.search(rf"(?<!\\){LABEL}", text[position:]):
        start = position + match.start()
        position += match.end()
        line = text.count("\n", 0, start) + 1
        if text[position : position + 1] == "(":
            target, position = _inline_link(text, position, line)
            links.append((line, target))
            continue
        reference = re.match(LABEL, text[position:])
        label = match.group(1)
        if reference:
            label = reference.group(1) or label
            position += reference.end()
        key = reference_key(label)
        if key in references:
            links.append((line, references[key]))
        elif reference:
            raise ValueError(
                f"{line}: undefined navigation reference {label!r}; add its definition"
            )
    return links
