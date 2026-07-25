"""String transformation node handler."""

from __future__ import annotations

import re
from typing import Any

from src.app.core.models import TrackMetadata
from src.app.core.nodes.base import NodeConfig, NodeInputs, NodeOutputs
from src.app.core.nodes.registry import register_node


def _apply_string_op(value: Any, config: dict, operation: str) -> Any:
    if operation == "lowercase":
        return str(value).lower()
    if operation == "uppercase":
        return str(value).upper()
    if operation == "trim":
        return re.sub(r"\s+", " ", str(value)).strip()
    if operation == "replace":
        find = config.get("find", "")
        replacement = config.get("replacement", "")
        if config.get("case_sensitive", False):
            return str(value).replace(find, replacement)
        return re.sub(re.escape(find), replacement, str(value), flags=re.IGNORECASE)
    if operation == "regex_replace":
        pattern = config.get("pattern", "")
        replacement = config.get("replacement", "")
        flags = 0 if config.get("case_sensitive", False) else re.IGNORECASE
        return re.sub(pattern, replacement, str(value), flags=flags)
    if operation == "regex_match":
        pattern = config.get("pattern", "")
        flags = 0 if config.get("case_sensitive", False) else re.IGNORECASE
        return bool(re.search(pattern, str(value), flags))
    if operation == "regex_extract":
        pattern = config.get("pattern", "")
        group = config.get("group", 0)
        flags = 0 if config.get("case_sensitive", False) else re.IGNORECASE
        m = re.search(pattern, str(value), flags)
        return m.group(group) if m else None
    if operation == "contains":
        substr = config.get("substring", "")
        if config.get("case_sensitive", False):
            return substr in str(value)
        return substr.lower() in str(value).lower()
    if operation == "split":
        delimiter = config.get("delimiter", ",")
        return [s.strip() for s in str(value).split(delimiter)]
    if operation == "join":
        delimiter = config.get("delimiter", ", ")
        items = value if isinstance(value, list) else [value]
        return delimiter.join(str(v) for v in items)
    if operation == "substring":
        start = config.get("start", 0)
        end = config.get("end")
        return str(value)[start:end] if end is not None else str(value)[start:]
    return value


@register_node("transform")
async def _handle_string_op(
    config: NodeConfig,
    track: TrackMetadata,
    inputs: NodeInputs,
) -> NodeOutputs:
    field = config.get("field", "value")
    target_field = config.get("target_field", field)
    operation = config.get("operation", "lowercase")

    raw_input = inputs.get("in")

    if field == "value":
        value = str(raw_input) if raw_input is not None else ""
        result = _apply_string_op(value, config, operation)
        return {"out": result}

    track_data = raw_input if isinstance(raw_input, dict) else {}
    if not track_data:
        track_data = {
            "title": track.title or "",
            "artist_name": track.artist_name or "",
            "album_name": track.album_name or "",
        }
    value = str(track_data.get(field, ""))
    result = _apply_string_op(value, config, operation)

    out_data = dict(track_data)
    if result is not None:
        out_data[target_field] = result
    return {"out": out_data}
