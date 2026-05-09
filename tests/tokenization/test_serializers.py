from copy import deepcopy

import pytest

from aperture.tokenization.serializers import stable_serialize_payload


def test_stable_serializer_sorts_keys_and_preserves_input():
    payload = {"b": 2, "a": {"d": 4, "c": 3}}
    original = deepcopy(payload)
    assert stable_serialize_payload(payload) == '{"a":{"c":3,"d":4},"b":2}'
    assert payload == original
    assert stable_serialize_payload({"a": 1, "b": 2}) == stable_serialize_payload({"b": 2, "a": 1})


def test_stable_serializer_fails_clearly_for_unsupported_value():
    with pytest.raises(TypeError):
        stable_serialize_payload({"bad": object()})

