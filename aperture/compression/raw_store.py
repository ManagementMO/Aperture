"""Raw output storage with opaque references."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from aperture.config import ApertureConfig
from aperture.tokenization.serializers import stable_serialize_payload
from aperture.types import CompressionContext

_RAW_STORE: dict[str, object] = {}


def _reference_id(raw_payload: object, context: CompressionContext) -> str:
    material = stable_serialize_payload(
        {
            "payload": raw_payload,
            "project_id": context.project_id,
            "user_id": context.user_id,
            "session_id": context.session_id,
            "tool_slug": context.tool_slug,
            "timestamp_bucket": int(time.time()),
        }
    )
    return "raw_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def store_raw_output(raw_payload: object, context: CompressionContext, base_path: Path | None = None) -> str:
    """Store raw payload and return opaque raw_reference_id."""

    raw_reference_id = _reference_id(raw_payload, context)
    _RAW_STORE[raw_reference_id] = raw_payload
    selected_base = base_path or ApertureConfig.from_env().raw_store_path
    selected_base.mkdir(parents=True, exist_ok=True)
    target = selected_base / f"{raw_reference_id}.json"
    target.write_text(
        json.dumps({"context": context.__dict__, "payload": raw_payload}, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    return raw_reference_id


def get_raw_output(raw_reference_id: str, base_path: Path | None = None) -> object:
    """Retrieve raw payload by reference, if available locally."""

    if raw_reference_id in _RAW_STORE:
        return _RAW_STORE[raw_reference_id]
    selected_base = base_path or ApertureConfig.from_env().raw_store_path
    target = selected_base / f"{raw_reference_id}.json"
    if not target.exists():
        raise KeyError(raw_reference_id)
    data = json.loads(target.read_text(encoding="utf-8"))
    _RAW_STORE[raw_reference_id] = data["payload"]
    return data["payload"]

