"""Nested object flattening for compressed payloads."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from aperture.compression.path_utils import delete_path, get_path, set_path
from aperture.compression.profile_loader import CompressionProfile


def _flatten_one(item: Any, profile: CompressionProfile) -> Any:
    if isinstance(item, list):
        return [_flatten_one(child, profile) for child in item]
    if not isinstance(item, dict):
        return item
    output = deepcopy(item)
    for source, destination in profile.flatten.items():
        value = get_path(output, source)
        if value is not None:
            set_path(output, destination, value)
            delete_path(output, source)
    return output


def flatten_fields(payload: object, profile: CompressionProfile) -> object:
    """Flatten configured nested fields such as user.login -> author."""

    return _flatten_one(payload, profile)

