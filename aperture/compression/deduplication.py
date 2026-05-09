"""Deterministic repeated-object deduplication."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from aperture.compression.path_utils import delete_path, get_path
from aperture.compression.profile_loader import CompressionProfile
from aperture.tokenization.serializers import stable_serialize_payload


def _dedupe_list(items: list[Any], profile: CompressionProfile) -> list[Any]:
    seen: dict[str, str] = {}
    output: list[Any] = []
    for index, item in enumerate(items):
        if isinstance(item, dict):
            item = deduplicate_repeated_objects(item, profile)
            for path in profile.deduplicate:
                value = get_path(item, path)
                if isinstance(value, dict):
                    signature = stable_serialize_payload(value)
                    if signature in seen:
                        delete_path(item, path)
                    else:
                        seen[signature] = f"dedup_{index}"
        output.append(item)
    return output


def deduplicate_repeated_objects(payload: object, profile: CompressionProfile) -> object:
    """Remove repeated configured nested objects when safe."""

    if isinstance(payload, list):
        return _dedupe_list(deepcopy(payload), profile)
    if isinstance(payload, dict):
        output = deepcopy(payload)
        for key, value in list(output.items()):
            output[key] = deduplicate_repeated_objects(value, profile)
        return output
    return payload

