"""Tests for oBIX.common.data_type — enum stability."""
import pytest
from oBIX.common.data_type import DataType


class TestDataTypeValues:
    """Verify that DataType enum values used in serialisation paths are stable."""

    def test_bool_value(self):
        assert DataType.bool == 1

    def test_int_value(self):
        assert DataType.int == 2

    def test_real_value(self):
        assert DataType.real == 3

    def test_str_value(self):
        assert DataType.str == 4

    def test_enum_value(self):
        assert DataType.enum == 5

    def test_abs_time_value(self):
        assert DataType.abs_time == 6

    def test_rel_time_value(self):
        assert DataType.rel_time == 7

    def test_list_value(self):
        assert DataType.list == 10

    def test_href_value(self):
        assert DataType.href == 11

    def test_all_members_present(self):
        names = {m.name for m in DataType}
        expected = {"bool", "int", "real", "str", "enum", "abs_time", "rel_time", "date", "time", "list", "href"}
        assert expected == names
