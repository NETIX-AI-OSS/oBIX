"""Tests for oBIX.common.point — Point model and serialisation."""
import json
import pytest
from oBIX.common.point import Point
from oBIX.common.data_type import DataType


class TestPointToJson:
    """Verify Point.to_json() serialises correctly."""

    def test_to_json_returns_string(self):
        p = Point()
        result = p.to_json()
        assert isinstance(result, str)

    def test_to_json_is_valid_json(self):
        p = Point()
        p.name = "TestPoint"
        p.val = "42.0"
        p.display = "42.0"
        p.href = "/config/test/"
        p.data_type = DataType.real
        p.out = "42.0"
        result = p.to_json()
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_to_json_contains_assigned_fields(self):
        p = Point()
        p.name = "MyPoint"
        p.val = "1"
        p.display = "true"
        p.href = "/config/my/"
        p.data_type = DataType.bool
        p.out = "true"
        parsed = json.loads(p.to_json())
        assert parsed["name"] == "MyPoint"
        assert parsed["val"] == "1"
        assert parsed["href"] == "/config/my/"

    def test_to_json_sorted_keys(self):
        p = Point()
        p.name = "z"
        p.val = "0"
        raw = p.to_json()
        parsed = json.loads(raw)
        keys = list(parsed.keys())
        assert keys == sorted(keys)

    def test_to_json_empty_point(self):
        """An empty Point should still serialise without raising."""
        p = Point()
        result = p.to_json()
        assert json.loads(result) == {}
