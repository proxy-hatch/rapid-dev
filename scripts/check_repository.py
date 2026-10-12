"""Check maintained AGENTS.md links and skill aliases without changing files.

Supports inline Markdown links and full, collapsed, or shortcut references with
single-line definitions, optional titles, angle-bracket paths, escapes, and balanced
parentheses. Fenced and inline code are skipped. HTML links, autolinks, and heading
anchors are not checked; use Markdown links for maintained local navigation.
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

LABEL = r"\[((?:\\.|[^\]\\\n])*)\]"
TITLE = r"""(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\((?:\\.|[^)\\])*\))"""


def blank(text: str) -> str:
    return re.sub(r"[^\n]", " ", text)


def without_code(text: str) -> str:
    lines = []
    fence = ""
    for line in text.splitlines(keepends=True):
        opening = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if fence:
            lines.append(blank(line))
            if re.fullmatch(rf" {{0,3}}{fence[0]}{{{len(fence)},}}\s*", line):
                fence = ""
        elif opening:
            fence = opening.group(1)
            lines.append(blank(line))
        else:
            lines.append(line)
    return re.sub(
        r"(?<![\\`])(`+)(?!`)[\s\S]*?(?<!`)\1(?!`)",
        lambda match: blank(match.group()),
        "".join(lines),
    )


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


def navigation_links(text: str) -> list[tuple[int, str]]:
    text = without_code(text)
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

    links = []
    position = 0
    while match := re.search(rf"(?<!\\){LABEL}", text[position:]):
        start = position + match.start()
        position += match.end()
        line = text.count("\n", 0, start) + 1
        if text[position : position + 1] == "(":
            try:
                target, rest = destination(text[position + 1 :])
                closing = re.match(rf"\s*(?:{TITLE}\s*)?\)", rest)
                if not closing:
                    raise ValueError(
                        "invalid navigation link syntax; use a path and optional title"
                    )
                position = len(text) - len(rest) + closing.end()
            except ValueError as error:
                raise ValueError(f"{line}: {error}") from error
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


def repository_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        capture_output=True,
        check=True,
    )
    return sorted({Path(os.fsdecode(name)) for name in result.stdout.split(b"\0") if name})


def check_navigation(root: Path, paths: list[Path]) -> list[str]:
    errors = []
    maintained = set(paths)
    maintained.update(parent for path in paths for parent in path.parents)
    aliases = [root / path for path in paths if (root / path).is_symlink()]
    for path in paths:
        if path.name != "AGENTS.md":
            continue
        document = root / path
        try:
            links = navigation_links(document.read_text())
        except (OSError, ValueError) as error:
            errors.append(f"{path}:{error}")
            continue
        for line, target in links:
            target = re.sub(r"\\([!\"#$%&'()*+,\-./:;<=>?@\[\]\\^_`{|}~])", r"\1", target)
            url = urlsplit(target)
            if url.scheme or url.netloc or not url.path:
                continue
            dependency = Path(os.path.normpath(document.parent / unquote(url.path)))
            if not dependency.exists():
                errors.append(
                    f"{path}:{line}: missing target {target!r}; update the navigation link"
                )
                continue
            relative = dependency.relative_to(root) if dependency.is_relative_to(root) else None
            # Git records directory aliases, not their descendants. Both the navigation
            # path (or its alias) and the resolved destination must belong to the checkout.
            resolved = dependency.resolve()
            if (
                (
                    relative in maintained
                    or any(dependency.is_relative_to(alias) for alias in aliases)
                )
                and resolved.is_relative_to(root)
                and resolved.relative_to(root) in maintained
            ):
                continue
            errors.append(
                f"{path}:{line}: target {target!r} is not maintained in this checkout; "
                "track its source or update the navigation link"
            )
    return errors


def check_skill_aliases(root: Path, paths: list[Path]) -> list[str]:
    skills = {
        path.parts[2]
        for path in paths
        if len(path.parts) == 4
        and path.parts[:2] == ("rapid_ship", "skills")
        and path.name == "SKILL.md"
    }
    if not skills:
        return ["rapid_ship/skills: no maintained SKILL.md files; restore the packaged skills"]
    errors = []
    for surface in (".agents", ".claude"):
        aliases = root / surface / "skills"
        if aliases.is_symlink() or not aliases.resolve().is_relative_to(root):
            errors.append(f"{surface}/skills: restore a directory inside the repository")
            continue
        for skill in sorted(skills):
            relative = Path(surface) / "skills" / skill
            alias = root / relative
            canonical = root / "rapid_ship/skills" / skill
            expected = f"../../rapid_ship/skills/{skill}"
            valid = (
                relative in paths
                and alias.is_symlink()
                and not alias.readlink().is_absolute()
                and alias.is_dir()
                and alias.resolve().is_relative_to(root)
                and alias.resolve() == canonical
                and (canonical / "SKILL.md").is_file()
            )
            if not valid:
                errors.append(
                    f"{relative}: maintain a relative directory symlink to {expected} in Git"
                )
        discovered = {
            path.parts[2]
            for path in paths
            if len(path.parts) >= 3 and path.parts[:2] == (surface, "skills")
        }
        for name in sorted(discovered - skills - {"AGENTS.md"}):
            errors.append(
                f"{surface}/skills/{name}: no matching packaged skill; "
                "remove the extra alias or add its canonical SKILL.md"
            )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    root = parser.parse_args(argv).root.resolve()
    try:
        paths = repository_files(root)
        errors = check_navigation(root, paths) + check_skill_aliases(root, paths)
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"Cannot check repository at {root}: {error}", file=sys.stderr)
        return 1
    for diagnostic in errors:
        print(diagnostic, file=sys.stderr)
    if errors:
        return 1
    print("Repository navigation and skill aliases passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
