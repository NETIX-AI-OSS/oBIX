"""Tests for oBIX.common.util — Util helper methods."""
import pytest
from oBIX.common.data_type import DataType
from oBIX.common.util import Util


class TestParseDataType:
    """Util.parse_data_type: string tag -> DataType."""

    def test_real(self):
        assert Util.parse_data_type("real") == DataType.real

    def test_bool(self):
        assert Util.parse_data_type("bool") == DataType.bool

    def test_int(self):
        assert Util.parse_data_type("int") == DataType.int

    def test_str(self):
        assert Util.parse_data_type("str") == DataType.str

    def test_enum(self):
        assert Util.parse_data_type("enum") == DataType.enum

    def test_abstime(self):
        assert Util.parse_data_type("abstime") == DataType.abs_time

    def test_reltime(self):
        assert Util.parse_data_type("reltime") == DataType.rel_time

    def test_unknown_defaults_to_str(self):
        assert Util.parse_data_type("unknown_tag") == DataType.str

    def test_case_insensitive(self):
        assert Util.parse_data_type("REAL") == DataType.real
        assert Util.parse_data_type("Bool") == DataType.bool

    def test_empty_defaults_to_str(self):
        assert Util.parse_data_type("") == DataType.str


class TestGetDataTypeStr:
    """Util.get_data_type_str: DataType -> string tag."""

    def test_real(self):
        assert Util.get_data_type_str(DataType.real) == "real"

    def test_bool(self):
        assert Util.get_data_type_str(DataType.bool) == "bool"

    def test_int(self):
        assert Util.get_data_type_str(DataType.int) == "int"

    def test_str(self):
        assert Util.get_data_type_str(DataType.str) == "str"

    def test_enum(self):
        assert Util.get_data_type_str(DataType.enum) == "enum"

    def test_abs_time(self):
        assert Util.get_data_type_str(DataType.abs_time) == "abstime"

    def test_rel_time(self):
        assert Util.get_data_type_str(DataType.rel_time) == "reltime"

    def test_unknown_defaults_to_str(self):
        # DataType.list and DataType.href are not in the round-trip map
        assert Util.get_data_type_str(DataType.list) == "str"

    def test_round_trip(self):
        """parse_data_type and get_data_type_str are inverses for supported types."""
        for tag in ("real", "bool", "int", "str", "enum", "abstime", "reltime"):
            dt = Util.parse_data_type(tag)
            assert Util.get_data_type_str(dt) == tag


class TestConvertToType:
    """Util.convert_to_type: string value -> typed value."""

    def test_real(self):
        assert Util.convert_to_type("3.14", DataType.real) == pytest.approx(3.14)

    def test_int(self):
        assert Util.convert_to_type("42", DataType.int) == 42

    def test_bool_true(self):
        assert Util.convert_to_type("true", DataType.bool) is True

    def test_bool_true_mixed_case(self):
        assert Util.convert_to_type("True", DataType.bool) is True

    def test_bool_false(self):
        assert Util.convert_to_type("false", DataType.bool) is False

    def test_str_passthrough(self):
        assert Util.convert_to_type("hello", DataType.str) == "hello"

    def test_enum_passthrough(self):
        # enum falls through to the else branch — returns the string as-is
        assert Util.convert_to_type("active", DataType.enum) == "active"


class TestParsePoint:
    """Util.parse_point: dict -> Point."""

    def _make_real_point_dict(self):
        """Return a minimal real-valued point dict as produced by xmltodict.

        The @is attribute mirrors what oBIX servers actually return: a
        space-separated list that includes 'obix:Point'.
        """
        slots = [
            {"@name": "out", "@display": "42.0", "@val": "42.0"},
            {"@name": "in1", "@display": "{null}", "@val": "null"},
        ]
        return {
            "@is": "obix:NumericPoint obix:Point",
            "@val": "42.0",
            "@href": "/obix/config/station/numeric/",
            "@display": "42.0 units",
            "real": slots,
        }

    def test_returns_point_for_valid_dict(self):
        from oBIX.common.point import Point
        d = self._make_real_point_dict()
        result = Util.parse_point(d, "real")
        assert result is not None
        assert isinstance(result, Point)

    def test_data_type_is_real(self):
        d = self._make_real_point_dict()
        result = Util.parse_point(d, "real")
        assert result.data_type == DataType.real

    def test_out_slot_populated(self):
        d = self._make_real_point_dict()
        result = Util.parse_point(d, "real")
        assert result.out == "42.0"

    def test_null_display_slot_is_none(self):
        d = self._make_real_point_dict()
        result = Util.parse_point(d, "real")
        # in1 has {null} display — should be None
        assert result.in1 is None

    def test_name_derived_from_href(self):
        d = self._make_real_point_dict()
        result = Util.parse_point(d, "real")
        assert result.name == "numeric"

    def test_returns_none_when_missing_is(self):
        d = {"@val": "1", "@href": "/x/", "@display": "1"}
        assert Util.parse_point(d, "real") is None

    def test_returns_none_when_not_obix_point(self):
        # @is does not contain "obix:Point" — should return None
        d = {"@is": "obix:Folder", "@val": "", "@href": "/x/", "@display": ""}
        assert Util.parse_point(d, "real") is None

    def test_with_namespace_prefix_in_tag(self):
        """Tags like 'obix:real' should be handled by stripping the prefix."""
        slots = [{"@name": "out", "@display": "1.0", "@val": "1.0"}]
        d = {
            "@is": "obix:NumericPoint obix:Point",
            "@val": "1.0",
            "@href": "/obix/config/s/p/",
            "@display": "1.0",
            "obix:real": slots,
        }
        result = Util.parse_point(d, "obix:real")
        assert result is not None
        assert result.data_type == DataType.real


class TestParsePoints:
    """Util.parse_points: list or single dict -> list of Points."""

    def _make_bool_point_dict(self, href_suffix="point", val="true"):
        slots = [{"@name": "out", "@display": val, "@val": val}]
        return {
            "@is": "obix:BooleanPoint obix:Point",
            "@val": val,
            "@href": "/obix/config/s/{0}/".format(href_suffix),
            "@display": val,
            "bool": slots,
        }

    def test_single_dict_returns_list_of_one(self):
        d = self._make_bool_point_dict()
        result = Util.parse_points(d, "bool")
        assert len(result) == 1

    def test_list_of_dicts_returns_matching_list(self):
        dicts = [
            self._make_bool_point_dict("p1", "true"),
            self._make_bool_point_dict("p2", "false"),
        ]
        result = Util.parse_points(dicts, "bool")
        assert len(result) == 2

    def test_invalid_items_skipped(self):
        dicts = [
            self._make_bool_point_dict("good"),
            {"@is": "obix:Folder"},  # invalid — will return None from parse_point
        ]
        result = Util.parse_points(dicts, "bool")
        assert len(result) == 1
