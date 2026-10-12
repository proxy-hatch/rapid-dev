"""JSON decoding rules shared by native CLI response parsers."""

import json
from typing import Any, NoReturn


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON field")
        value[key] = item
    return value


def _invalid_constant(value: str) -> NoReturn:
    raise ValueError(f"invalid JSON constant: {value}")


def decode_json(text: str | bytes) -> object:
    """Decode one value, rejecting duplicate fields and NaN/Infinity constants.

    Callers own message framing, size limits and validation of the decoded value.
    """
    return json.loads(text, object_pairs_hook=_object_pairs, parse_constant=_invalid_constant)
