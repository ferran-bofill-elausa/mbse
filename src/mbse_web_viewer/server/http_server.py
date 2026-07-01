"""Generic HTTP transport for the MBSE web viewer."""

from __future__ import annotations

from dataclasses import asdict
from functools import partial
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
import json
from json import JSONDecodeError
import mimetypes
from pathlib import Path
from threading import Thread
from typing import Any
from typing import Protocol
from urllib.parse import urlparse


_STATIC_DIR = Path(__file__).resolve().parents[1] / "static"


class ViewerController(Protocol):
  """Controller contract consumed by the generic HTTP viewer transport."""

  def getModelSvgText(self, model_id: str) -> str:
    """Return the SVG document for one rendered model."""

  def getSession(self) -> object:
    """Return the current viewer session dataclass."""

  def reset(self) -> object:
    """Reset runtime state and return a viewer session dataclass."""

  def sendEvent(
    self,
    event_id: str,
    parameters: dict[str, Any] | None = None,
  ) -> object:
    """Send one event and return a viewer session dataclass."""

  def play(self) -> object:
    """Run the runtime and return a viewer session dataclass."""

  def pause(self) -> object:
    """Pause the runtime and return a viewer session dataclass."""

  def stepInto(self) -> object:
    """Step into the runtime and return a viewer session dataclass."""

  def stepOver(self) -> object:
    """Step over the runtime and return a viewer session dataclass."""

  def stepOut(self) -> object:
    """Step out of the runtime and return a viewer session dataclass."""

  def setVariable(self, variable_id: str, value: Any) -> object:
    """Set one runtime variable and return a viewer session dataclass."""

  def toggleBreakpoint(self, breakpoint_id: str) -> object:
    """Toggle one breakpoint and return a viewer session dataclass."""

  def removeBreakpoint(self, breakpoint_id: str) -> object:
    """Remove one breakpoint and return a viewer session dataclass."""

  def setBreakpointEnabled(self, breakpoint_id: str, enabled: bool) -> object:
    """Enable or disable one breakpoint and return a viewer session dataclass."""

  def reorderBreakpoints(self, breakpoint_ids: list[str]) -> object:
    """Reorder set breakpoints and return a viewer session dataclass."""


class RunningViewerServer:
  """Running HTTP server handle for one viewer instance."""

  def __init__(self, httpd: ThreadingHTTPServer, thread: Thread) -> None:
    """Wrap one started HTTP server and its serving thread."""

    self._httpd = httpd
    self._thread = thread
    self.base_url = (
      f"http://{httpd.server_address[0]}:{httpd.server_address[1]}"
    )

  def waitUntilStopped(self) -> None:
    """Block until the serving thread stops."""

    self._thread.join()

  def close(self) -> None:
    """Stop the HTTP server and wait briefly for shutdown."""

    self._httpd.shutdown()
    self._httpd.server_close()
    self._thread.join(timeout=5)


class ViewerRequestHandler(BaseHTTPRequestHandler):
  """Serve static assets plus the viewer runtime API."""

  def __init__(
    self,
    *args: Any,
    controller: ViewerController,
    **kwargs: Any,
  ) -> None:
    """Bind one viewer controller to one handler instance."""

    self._controller = controller
    super().__init__(*args, **kwargs)

  def do_GET(self) -> None:
    """Serve one static asset or one read-only session endpoint."""

    if self.path == "/":
      self._serveStatic("index.html", "text/html; charset=utf-8")
      return
    if self._tryServeStaticPath():
      return
    if self.path == "/api/session.json":
      self._sendJson(asdict(self._controller.getSession()))
      return
    parsed_path = urlparse(self.path).path
    if parsed_path.startswith("/artifacts/models/") and parsed_path.endswith("/diagram.svg"):
      model_id = parsed_path.removeprefix("/artifacts/models/").removesuffix("/diagram.svg")
      try:
        self._sendBytes(
          self._controller.getModelSvgText(model_id).encode("utf-8"),
          content_type="image/svg+xml; charset=utf-8",
        )
      except KeyError as error:
        self.send_error(404, str(error))
      return

    self.send_error(404)

  def do_POST(self) -> None:
    """Serve one mutating runtime endpoint."""

    if self.path == "/api/runtime/reset":
      self._readJsonBody()
      self._sendJson(asdict(self._controller.reset()))
      return

    if self.path == "/api/runtime/events":
      payload = self._readJsonBody()
      try:
        self._sendJson(
          asdict(
            self._controller.sendEvent(
              str(payload["event_id"]),
              (
                payload.get("parameters")
                if isinstance(payload.get("parameters"), dict)
                else None
              ),
            )
          )
        )
      except (KeyError, ValueError) as error:
        self.send_error(400, str(error))
      return

    if self.path == "/api/runtime/play":
      self._readJsonBody()
      self._sendJson(asdict(self._controller.play()))
      return

    if self.path == "/api/runtime/pause":
      self._readJsonBody()
      self._sendJson(asdict(self._controller.pause()))
      return

    if self.path == "/api/runtime/step-into":
      self._readJsonBody()
      self._sendJson(asdict(self._controller.stepInto()))
      return

    if self.path == "/api/runtime/step-over":
      self._readJsonBody()
      self._sendJson(asdict(self._controller.stepOver()))
      return

    if self.path == "/api/runtime/step-out":
      self._readJsonBody()
      self._sendJson(asdict(self._controller.stepOut()))
      return

    if self.path == "/api/runtime/variables":
      payload = self._readJsonBody()
      try:
        self._sendJson(
          asdict(
            self._controller.setVariable(
              str(payload["variable_id"]),
              payload.get("value"),
            )
          )
        )
      except (KeyError, ValueError) as error:
        self.send_error(400, str(error))
      return

    if self.path == "/api/debugger/breakpoints/toggle":
      payload = self._readJsonBody()
      try:
        self._sendJson(
          asdict(
            self._controller.toggleBreakpoint(str(payload["breakpoint_id"]))
          )
        )
      except KeyError as error:
        self.send_error(400, str(error))
      return

    if self.path == "/api/debugger/breakpoints/remove":
      payload = self._readJsonBody()
      try:
        self._sendJson(
          asdict(
            self._controller.removeBreakpoint(str(payload["breakpoint_id"]))
          )
        )
      except KeyError as error:
        self.send_error(400, str(error))
      return

    if self.path == "/api/debugger/breakpoints/enabled":
      payload = self._readJsonBody()
      try:
        self._sendJson(
          asdict(
            self._controller.setBreakpointEnabled(
              str(payload["breakpoint_id"]),
              bool(payload["enabled"]),
            )
          )
        )
      except KeyError as error:
        self.send_error(400, str(error))
      return

    if self.path == "/api/debugger/breakpoints/order":
      payload = self._readJsonBody()
      breakpoint_ids = payload.get("breakpoint_ids", [])
      if not isinstance(breakpoint_ids, list):
        self.send_error(400, "'breakpoint_ids' must be a JSON array.")
        return
      try:
        self._sendJson(
          asdict(
            self._controller.reorderBreakpoints(
              [str(breakpoint_id) for breakpoint_id in breakpoint_ids]
            )
          )
        )
      except (KeyError, ValueError) as error:
        self.send_error(400, str(error))
      return

    self.send_error(404)

  def log_message(self, format: str, *args: Any) -> None:
    """Suppress default console request logging for local viewer use."""

    return

  def _readJsonBody(self) -> dict[str, object]:
    """Read and decode one JSON request body."""

    content_length = int(self.headers.get("Content-Length", "0"))
    raw_body = self.rfile.read(content_length)
    if not raw_body:
      return {}
    try:
      return json.loads(raw_body.decode("utf-8"))
    except JSONDecodeError as error:
      self.send_error(400, f"Invalid JSON body: {error.msg}")
      return {}

  def _serveStatic(self, file_name: str, content_type: str) -> None:
    """Serve one static viewer asset from the package static directory."""

    self._sendBytes(
      (_STATIC_DIR / file_name).read_bytes(),
      content_type=content_type,
    )

  def _tryServeStaticPath(self) -> bool:
    """Serve one package static file when the request path maps to it safely."""

    parsed_path = urlparse(self.path).path
    if parsed_path in {"", "/"}:
      return False

    relative_path = parsed_path.removeprefix("/")
    static_path = (_STATIC_DIR / relative_path).resolve()
    if not static_path.is_file():
      return False
    if _STATIC_DIR.resolve() not in static_path.parents:
      self.send_error(403)
      return True

    content_type, _ = mimetypes.guess_type(static_path.name)
    if content_type is None:
      content_type = "application/octet-stream"
    if content_type.startswith("text/") or content_type in {
      "application/javascript",
      "image/svg+xml",
    }:
      content_type = f"{content_type}; charset=utf-8"

    self._sendBytes(static_path.read_bytes(), content_type=content_type)
    return True

  def _sendJson(self, payload: dict[str, object]) -> None:
    """Serialize and send one JSON response payload."""

    self._sendBytes(
      json.dumps(payload).encode("utf-8"),
      content_type="application/json; charset=utf-8",
    )

  def _sendBytes(self, body: bytes, *, content_type: str) -> None:
    """Send one raw response body with the given content type."""

    self.send_response(200)
    self.send_header("Content-Type", content_type)
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)


def startViewerServer(
  controller: ViewerController,
  *,
  host: str = "127.0.0.1",
  port: int = 0,
) -> RunningViewerServer:
  """Start one local viewer HTTP server for the given controller."""

  httpd = ThreadingHTTPServer(
    (host, port),
    partial(ViewerRequestHandler, controller=controller),
  )
  thread = Thread(target=httpd.serve_forever, daemon=True)
  thread.start()
  return RunningViewerServer(httpd, thread)
