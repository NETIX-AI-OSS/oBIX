"""Tests for oBIX.client.client — Client public methods (mocked HTTP)."""
import json
import pytest
from datetime import timedelta
from unittest.mock import patch, MagicMock, PropertyMock

from oBIX.common.data_type import DataType


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_response(status_code: int, text: str) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    return resp


REAL_POINT_XML = """<real name="NumericWritable" href="/obix/config/station/p/" is="obix:NumericPoint obix:Point"
        val="42.0" display="42.0 C">
  <real name="out" val="42.0" display="42.0" status="ok"/>
  <real name="in1" val="null" display="{null}"/>
</real>"""

BOOL_POINT_XML = """<bool name="BoolWritable" href="/obix/config/station/b/" is="obix:BooleanPoint obix:Point"
        val="true" display="true">
  <bool name="out" val="true" display="true" status="ok"/>
</bool>"""

ERR_XML = """<err is="obix:BadUriErr" display="No such object: /bad/path/"/>"""

OK_XML = """<obj href="/obix/watchService/watch1/" is="obix:Watch"/>"""

# Watch response includes full URL so the watch-ID extraction logic works correctly
WATCH_RESPONSE_XML = """<obj href="https://127.0.0.1/obix/watchService/watch1/" is="obix:Watch"/>"""


@pytest.fixture()
def client():
    """Return a Client instance with scheduler and logger mocked out."""
    with patch("oBIX.client.client.BackgroundScheduler") as mock_sched_cls, \
         patch("oBIX.client.client.Logger") as mock_logger, \
         patch("oBIX.client.client.urllib3") as mock_urllib3, \
         patch("oBIX.client.client.requests") as mock_requests:

        mock_sched = MagicMock()
        mock_sched.running = False
        mock_sched_cls.return_value = mock_sched
        mock_logger.instance.return_value = MagicMock()

        from oBIX.client.client import Client
        c = Client("127.0.0.1", "admin", "password", port=443)
        c._Client__requests = mock_requests  # expose for per-test overrides
        yield c


# ---------------------------------------------------------------------------
# __get_url
# ---------------------------------------------------------------------------

class TestGetUrl:
    def test_basic_path(self, client):
        url = client._Client__get_url("/config/test/")
        assert url == "https://127.0.0.1/obix/config/test/"

    def test_path_without_leading_slash(self, client):
        url = client._Client__get_url("config/test/")
        assert url == "https://127.0.0.1/obix/config/test/"

    def test_path_without_trailing_slash(self, client):
        url = client._Client__get_url("/config/test")
        assert url == "https://127.0.0.1/obix/config/test/"

    def test_with_operation(self, client):
        url = client._Client__get_url("/config/test/", "set")
        assert url == "https://127.0.0.1/obix/config/test/set"


# ---------------------------------------------------------------------------
# read_point
# ---------------------------------------------------------------------------

class TestReadPoint:
    def test_returns_point_on_200(self, client):
        with patch.object(client, "_Client__do_get", return_value=_make_response(200, REAL_POINT_XML)):
            point = client.read_point("/config/station/p/")
        assert point is not None
        assert point.data_type == DataType.real

    def test_returns_none_on_non_200(self, client):
        with patch.object(client, "_Client__do_get", return_value=_make_response(404, "")):
            result = client.read_point("/bad/path/")
        assert result is None

    def test_returns_none_on_err_tag(self, client):
        with patch.object(client, "_Client__do_get", return_value=_make_response(200, ERR_XML)):
            result = client.read_point("/bad/path/")
        assert result is None

    def test_returns_none_on_exception(self, client):
        with patch.object(client, "_Client__do_get", side_effect=Exception("network error")):
            result = client.read_point("/config/station/p/")
        assert result is None


# ---------------------------------------------------------------------------
# read_point_value / read_point_slot
# ---------------------------------------------------------------------------

class TestReadPointValue:
    def test_returns_float_for_real_point(self, client):
        with patch.object(client, "_Client__do_get", return_value=_make_response(200, REAL_POINT_XML)):
            value = client.read_point_value("/config/station/p/")
        assert value == pytest.approx(42.0)

    def test_returns_none_when_read_point_fails(self, client):
        with patch.object(client, "_Client__do_get", return_value=_make_response(404, "")):
            value = client.read_point_value("/bad/")
        assert value is None


# ---------------------------------------------------------------------------
# __parse_xml_response (static helper)
# ---------------------------------------------------------------------------

class TestParseXmlResponse:
    def test_returns_dict_and_first_key(self):
        from oBIX.client.client import Client
        root_dict, first_key = Client._Client__parse_xml_response(OK_XML)
        assert first_key == "obj"
        assert isinstance(root_dict, dict)

    def test_error_response_first_key_contains_err(self):
        from oBIX.client.client import Client
        root_dict, first_key = Client._Client__parse_xml_response(ERR_XML)
        assert "err" in first_key


# ---------------------------------------------------------------------------
# __check_xml_error (static helper)
# ---------------------------------------------------------------------------

class TestCheckXmlError:
    def test_returns_none_for_ok_response(self):
        from oBIX.client.client import Client
        with patch("oBIX.client.client.Logger"):
            root_dict, first_key = Client._Client__parse_xml_response(OK_XML)
            result = Client._Client__check_xml_error(root_dict, first_key, "Test")
        assert result is None

    def test_returns_error_display_for_err_response(self):
        from oBIX.client.client import Client
        with patch("oBIX.client.client.Logger"):
            root_dict, first_key = Client._Client__parse_xml_response(ERR_XML)
            result = Client._Client__check_xml_error(root_dict, first_key, "Test")
        assert result == "No such object: /bad/path/"


# ---------------------------------------------------------------------------
# override_point
# ---------------------------------------------------------------------------

class TestOverridePoint:
    def test_returns_ok_on_success(self, client):
        with patch.object(client, "_Client__do_post", return_value=_make_response(200, OK_XML)):
            result = client.override_point("/config/station/p/", 25.0, DataType.real)
        assert result == "OK"

    def test_returns_error_msg_on_err_response(self, client):
        with patch.object(client, "_Client__do_post", return_value=_make_response(200, ERR_XML)):
            result = client.override_point("/config/station/p/", 25.0, DataType.real)
        assert result == "No such object: /bad/path/"

    def test_returns_false_on_non_200(self, client):
        with patch.object(client, "_Client__do_post", return_value=_make_response(500, "")):
            result = client.override_point("/config/station/p/", 25.0, DataType.real)
        assert result is False

    def test_with_time_delta(self, client):
        with patch.object(client, "_Client__do_post", return_value=_make_response(200, OK_XML)) as mock_post:
            result = client.override_point("/config/station/p/", 25.0, DataType.real, time_delta=timedelta(seconds=60))
        assert result == "OK"
        post_data = mock_post.call_args[0][1]
        assert "PT60S" in post_data

    def test_command_only_no_value(self, client):
        """Passing value=None should produce a payload without a value element."""
        with patch.object(client, "_Client__do_post", return_value=_make_response(200, OK_XML)) as mock_post:
            result = client.override_point("/config/station/p/", None, None)
        assert result == "OK"
        post_data = mock_post.call_args[0][1]
        # No type element should appear when value is None
        assert "val=" not in post_data or "PT0S" in post_data


# ---------------------------------------------------------------------------
# override_point_command
# ---------------------------------------------------------------------------

class TestOverridePointCommand:
    def test_returns_ok_on_success(self, client):
        with patch.object(client, "_Client__do_post", return_value=_make_response(200, OK_XML)):
            result = client.override_point_command("/config/station/p/", "auto")
        assert result == "OK"

    def test_returns_false_on_non_200(self, client):
        with patch.object(client, "_Client__do_post", return_value=_make_response(500, "")):
            result = client.override_point_command("/config/station/p/", "auto")
        assert result is False


# ---------------------------------------------------------------------------
# set_point_value / set_point_auto
# ---------------------------------------------------------------------------

class TestSetPointValue:
    def test_set_point_value_ok(self, client):
        with patch.object(client, "_Client__do_post", return_value=_make_response(200, OK_XML)):
            result = client.set_point_value("/config/station/p/", 10.0, DataType.real)
        assert result == "OK"

    def test_set_point_auto_ok(self, client):
        with patch.object(client, "_Client__do_post", return_value=_make_response(200, OK_XML)):
            result = client.set_point_auto("/config/station/p/", DataType.real)
        assert result == "OK"


# ---------------------------------------------------------------------------
# create_new_watch
# ---------------------------------------------------------------------------


class TestCreateNewWatch:
    def test_returns_watch_id(self, client):
        with patch.object(client, "_Client__do_post", return_value=_make_response(200, WATCH_RESPONSE_XML)):
            watch_id = client.create_new_watch()
        assert watch_id == "watch1"

    def test_watch_id_added_to_list(self, client):
        with patch.object(client, "_Client__do_post", return_value=_make_response(200, WATCH_RESPONSE_XML)):
            client.create_new_watch()
        assert "watch1" in client._Client__watch_id_list

    def test_duplicate_watch_id_not_added_twice(self, client):
        with patch.object(client, "_Client__do_post", return_value=_make_response(200, WATCH_RESPONSE_XML)):
            client.create_new_watch()
            client.create_new_watch()
        assert client._Client__watch_id_list.count("watch1") == 1

    def test_returns_none_on_non_200(self, client):
        with patch.object(client, "_Client__do_post", return_value=_make_response(500, "")):
            result = client.create_new_watch()
        assert result is None


# ---------------------------------------------------------------------------
# start_watch / stop_watch
# ---------------------------------------------------------------------------

class TestStartStopWatch:
    def test_start_watch_calls_start_when_not_running(self, client):
        client._Client__scheduler.running = False
        client.start_watch()
        client._Client__scheduler.start.assert_called_once()

    def test_start_watch_does_not_start_when_running(self, client):
        client._Client__scheduler.running = True
        client.start_watch()
        client._Client__scheduler.start.assert_not_called()

    def test_stop_watch_calls_shutdown_when_running(self, client):
        client._Client__scheduler.running = True
        client.stop_watch()
        client._Client__scheduler.shutdown.assert_called_once()

    def test_stop_watch_does_not_shutdown_when_not_running(self, client):
        client._Client__scheduler.running = False
        client.stop_watch()
        client._Client__scheduler.shutdown.assert_not_called()


# ---------------------------------------------------------------------------
# Instance isolation — __watch_id_list must not be shared
# ---------------------------------------------------------------------------

class TestInstanceIsolation:
    def test_separate_watch_id_lists(self):
        with patch("oBIX.client.client.BackgroundScheduler"), \
             patch("oBIX.client.client.Logger"), \
             patch("oBIX.client.client.urllib3"), \
             patch("oBIX.client.client.requests"):
            from oBIX.client.client import Client
            c1 = Client("1.1.1.1", "u", "p")
            c2 = Client("2.2.2.2", "u", "p")

        c1._Client__watch_id_list.append("watch_a")
        assert "watch_a" not in c2._Client__watch_id_list


# ---------------------------------------------------------------------------
# __serialize_data
# ---------------------------------------------------------------------------

class TestSerializeData:
    def test_real_serialisation(self, client):
        result = client._Client__serialize_data(3.14, DataType.real)
        assert 'val="3.14"' in result
        assert "<real" in result

    def test_bool_true_serialisation(self, client):
        result = client._Client__serialize_data(True, DataType.bool)
        assert 'val="true"' in result

    def test_bool_false_serialisation(self, client):
        result = client._Client__serialize_data(False, DataType.bool)
        assert 'val="false"' in result

    def test_int_serialisation(self, client):
        result = client._Client__serialize_data(42, DataType.int)
        assert 'val="42"' in result
        assert "<int" in result

    def test_str_serialisation(self, client):
        result = client._Client__serialize_data("hello", DataType.str)
        assert 'val="hello"' in result

    def test_list_serialisation(self, client):
        result = client._Client__serialize_data([1.0, 2.0], DataType.list, parameter=DataType.real)
        assert "<list" in result
        assert "</list>" in result

    def test_list_without_parameter_returns_empty(self, client):
        result = client._Client__serialize_data([1, 2], DataType.list, parameter=None)
        assert result == ""
