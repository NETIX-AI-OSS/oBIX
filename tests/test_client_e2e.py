"""End-to-end tests for the oBIX client against a local HTTP server."""

from base64 import b64encode
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from unittest.mock import MagicMock, patch
import xml.etree.ElementTree as ElementTree

import pytest

from oBIX import Client
from oBIX.common.data_type import DataType


POINT_XML = """<real name="NumericWritable" href="/obix/config/station/p/" is="obix:NumericPoint obix:Point"
        val="42.0" display="42.0 C">
  <real name="out" val="42.0" display="42.0" status="ok"/>
  <real name="in1" val="null" display="{null}"/>
</real>"""

ERROR_XML = '<err is="obix:BadUriErr" display="No such object"/>'
OK_XML = '<obj href="/obix/watchService/watch1/" is="obix:Watch"/>'


class ObixHandler(BaseHTTPRequestHandler):
    """Serve a minimal oBIX protocol surface and record client requests."""

    server_version = "oBIX-test-server"

    def _authorized(self) -> bool:
        return self.headers.get("Authorization") == self.server.expected_authorization

    def _record_request(self, body: str = "") -> None:
        self.server.requests.append(
            {
                "method": self.command,
                "path": self.path,
                "authorization": self.headers.get("Authorization"),
                "body": body,
            }
        )

    def _respond(self, status_code: int, body: str, content_type: str = "application/xml") -> None:
        body_bytes = body.encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body_bytes)))
        if status_code == 401:
            self.send_header("WWW-Authenticate", 'Basic realm="oBIX"')
        self.end_headers()
        self.wfile.write(body_bytes)

    def do_GET(self) -> None:
        self._record_request()
        if not self._authorized():
            self._respond(401, "")
            return

        responses = {
            "/obix/config/station/p/": (200, POINT_XML),
            "/obix/config/station/missing/": (200, ERROR_XML),
        }
        status_code, body = responses.get(self.path, (404, ERROR_XML))
        self._respond(status_code, body)

    def do_POST(self) -> None:
        body_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(body_length).decode("utf-8")
        self._record_request(body)
        if not self._authorized():
            self._respond(401, "")
            return

        if self.path == "/obix/config/station/p/set":
            self._respond(200, OK_XML)
        elif self.path == "/obix/watchService/make/":
            host, port = self.server.server_address
            watch_xml = (
                f'<obj href="http://{host}:{port}/obix/watchService/watch1/" '
                'is="obix:Watch"/>'
            )
            self._respond(200, watch_xml)
        elif self.path == "/obix/watchService/watch1/add/":
            self._respond(200, OK_XML)
        else:
            self._respond(404, ERROR_XML)

    def log_message(self, format: str, *args: object) -> None:
        """Keep test output focused on assertion failures."""


@pytest.fixture()
def obix_server() -> ThreadingHTTPServer:
    """Run the local oBIX protocol fixture on an ephemeral port."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), ObixHandler)
    server.daemon_threads = True
    server.expected_authorization = "Basic " + b64encode(b"admin:password").decode("ascii")
    server.requests = []
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture()
def e2e_client(obix_server: ThreadingHTTPServer) -> Client:
    """Create a real client pointed at the local protocol fixture."""
    with patch("oBIX.client.client.Logger") as mock_logger:
        mock_logger.instance.return_value = MagicMock()
        client = Client(
            "127.0.0.1",
            "admin",
            "password",
            port=obix_server.server_port,
            https=False,
        )
        yield client


def test_reads_point_over_http(e2e_client: Client, obix_server: ThreadingHTTPServer) -> None:
    point = e2e_client.read_point("/config/station/p/")
    value = e2e_client.read_point_value("/config/station/p/")

    assert point is not None
    assert point.data_type == DataType.real
    assert value == pytest.approx(42.0)
    assert [request["path"] for request in obix_server.requests] == [
        "/obix/config/station/p/",
        "/obix/config/station/p/",
    ]
    assert all(
        request["authorization"] == obix_server.expected_authorization
        for request in obix_server.requests
    )


def test_writes_point_xml_over_http(
    e2e_client: Client, obix_server: ThreadingHTTPServer
) -> None:
    result = e2e_client.set_point_value("/config/station/p/", 25.0, DataType.real)

    assert result == "OK"
    assert len(obix_server.requests) == 1
    request = obix_server.requests[0]
    assert request["method"] == "POST"
    assert request["path"] == "/obix/config/station/p/set"
    payload = ElementTree.fromstring(request["body"])
    assert payload.tag == "real"
    assert payload.attrib["val"] == "25.0"
    assert request["authorization"] == obix_server.expected_authorization


def test_returns_none_for_protocol_errors(
    e2e_client: Client, obix_server: ThreadingHTTPServer
) -> None:
    assert e2e_client.read_point("/config/station/missing/") is None
    assert e2e_client.read_point("/config/station/unknown/") is None

    assert [request["path"] for request in obix_server.requests] == [
        "/obix/config/station/missing/",
        "/obix/config/station/unknown/",
    ]


def test_creates_watch_and_registers_points(
    e2e_client: Client, obix_server: ThreadingHTTPServer
) -> None:
    watch_id = e2e_client.create_new_watch()
    result = e2e_client.add_watch_points(["/config/station/p/"], watch_id=watch_id)

    assert watch_id == "watch1"
    assert result == "OK"
    assert [request["path"] for request in obix_server.requests] == [
        "/obix/watchService/make/",
        "/obix/watchService/watch1/add/",
    ]
    assert "/obix/config/station/p/" in obix_server.requests[1]["body"]
    assert all(
        request["authorization"] == obix_server.expected_authorization
        for request in obix_server.requests
    )
