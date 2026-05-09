"""List compaction for repeated object lists."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from aperture.compression.path_utils import get_path
from aperture.compression.profile_loader import CompressionProfile


def _compact(value: Any, profile: CompressionProfile) -> Any:
    if isinstance(value, list):
        return [_compact(item, profile) for item in value]
    if not isinstance(value, dict):
        return value
    output = deepcopy(value)
    for key, target_path in profile.compact_lists.items():
        if key in output and isinstance(output[key], list):
            compacted = []
            for item in output[key]:
                if isinstance(item, dict):
                    compacted.append(get_path(item, target_path))
                else:
                    compacted.append(item)
            output[key] = [item for item in compacted if item is not None]
    for key, item in list(output.items()):
        output[key] = _compact(item, profile)
    return output


def compact_lists(payload: object, profile: CompressionProfile) -> object:
    """Compact lists of objects into useful scalar arrays when configured."""

    return _compact(payload, profile)

