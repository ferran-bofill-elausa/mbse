from __future__ import annotations

from dataclasses import asdict
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
import json
from json import JSONDecodeError
from pathlib import Path
from threading import Thread
from typing import Any

from mbse_web_viewer.svg_render.graphviz.contract_validation import (
  extract_svg_ids,
)
from mbse_web_viewer.svg_render.graphviz.contract_validation import (
  validate_rendered_contract,
)

from .runtime_bridge import ViewerRuntimeBridge


STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


class RunningViewerServer:
  def __init__(self, httpd: ThreadingHTTPServer, thread: Thread):
    self._httpd = httpd
    self._thread = thread
    self.base_url = f"http://{httpd.server_address[0]}:{httpd.server_address[1]}"

  def wait_until_stopped(self) -> None:
    self._thread.join()

  def close(self) -> None:
    self._httpd.shutdown()
    self._httpd.server_close()
    self._thread.join(timeout=5)


def start_viewer_server(
  session_dir: Path,
  *,
  runtime_bridge: ViewerRuntimeBridge,
  host: str = "127.0.0.1",
  port: int = 0,
) -> RunningViewerServer:
  rendered_ids = extract_svg_ids(
    (session_dir / "diagram.svg").read_text(encoding="utf-8")
  )
  validate_rendered_contract(runtime_bridge.app_state.highlightable_ids, rendered_ids)
  httpd = ThreadingHTTPServer(
    (host, port),
    _build_handler(session_dir=session_dir, runtime_bridge=runtime_bridge),
  )
  thread = Thread(target=httpd.serve_forever, daemon=True)
  thread.start()
  return RunningViewerServer(httpd, thread)


def _build_handler(
  *,
  session_dir: Path,
  runtime_bridge: ViewerRuntimeBridge,
) -> type[BaseHTTPRequestHandler]:
  class ViewerRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
      if self.path == "/":
        self._serve_static("index.html", "text/html; charset=utf-8")
        return
      if self.path == "/viewer.css":
        self._serve_static("viewer.css", "text/css; charset=utf-8")
        return
      if self.path == "/viewer.js":
        self._serve_static("viewer.js", "application/javascript; charset=utf-8")
        return
      if self.path == "/api/session.json":
        self._send_json(asdict(runtime_bridge.get_session()))
        return
      if self.path == "/artifacts/diagram.svg":
        svg_path = session_dir / "diagram.svg"
        self._send_bytes(
          svg_path.read_bytes(),
          content_type="image/svg+xml; charset=utf-8",
        )
        return

      self.send_error(404)

    def do_POST(self) -> None:
      if self.path == "/api/runtime/reset":
        self._read_json_body()
        self._send_json(asdict(runtime_bridge.reset()))
        return
      if self.path == "/api/runtime/events":
        payload = self._read_json_body()
        try:
          self._send_json(
            asdict(runtime_bridge.send_event(str(payload["event_id"])))
          )
        except (KeyError, ValueError) as exc:
          self.send_error(400, str(exc))
        return
      if self.path == "/api/runtime/variables":
        payload = self._read_json_body()
        try:
          self._send_json(
            asdict(
              runtime_bridge.set_variable(
                str(payload["variable_id"]),
                payload.get("value"),
              )
            )
          )
        except (KeyError, ValueError) as exc:
          self.send_error(400, str(exc))
        return

      if self.path != "/api/runtime/reset":
        self.send_error(404)

    def log_message(self, format: str, *args: Any) -> None:
      return

    def _read_json_body(self) -> dict[str, object]:
      content_length = int(self.headers.get("Content-Length", "0"))
      raw_body = self.rfile.read(content_length)
      if not raw_body:
        return {}
      try:
        return json.loads(raw_body.decode("utf-8"))
      except JSONDecodeError as exc:
        self.send_error(400, f"Invalid JSON body: {exc.msg}")
        return {}

    def _serve_static(self, file_name: str, content_type: str) -> None:
      self._send_bytes(
        (STATIC_DIR / file_name).read_bytes(),
        content_type=content_type,
      )

    def _send_json(self, payload: dict[str, object]) -> None:
      self._send_bytes(
        json.dumps(payload).encode("utf-8"),
        content_type="application/json; charset=utf-8",
      )

    def _send_bytes(self, body: bytes, *, content_type: str) -> None:
      self.send_response(200)
      self.send_header("Content-Type", content_type)
      self.send_header("Content-Length", str(len(body)))
      self.end_headers()
      self.wfile.write(body)

  return ViewerRequestHandler
