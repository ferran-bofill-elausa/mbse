from __future__ import annotations

from pathlib import Path

from mbse_web_viewer.app.viewer_state_types import RuntimeViewerTextTargets
from mbse_web_viewer.app.viewer_state_types import ViewerAppState
from mbse_web_viewer import main as cli_main


class _FakeServer:
  def __init__(self) -> None:
    self.base_url = "http://127.0.0.1:8123"
    self.wait_calls = 0
    self.close_calls = 0

  def wait_until_stopped(self) -> None:
    self.wait_calls += 1

  def close(self) -> None:
    self.close_calls += 1


class _FakeRuntimeBridge:
  pass


def test_main_waits_for_server_lifecycle(monkeypatch):
  fake_server = _FakeServer()
  captured = {}

  def fake_build_and_start_viewer(
    prepared_document_path: Path,
    output_dir: Path,
    *,
    host: str,
    port: int,
    open_browser: bool,
    graphviz_command: tuple[str, ...] | None = None,
  ) -> _FakeServer:
    captured["prepared_document_path"] = prepared_document_path
    captured["output_dir"] = output_dir
    captured["host"] = host
    captured["port"] = port
    captured["open_browser"] = open_browser
    captured["graphviz_command"] = graphviz_command
    return fake_server

  monkeypatch.setattr(
    cli_main,
    "build_and_start_viewer",
    fake_build_and_start_viewer,
  )

  exit_code = cli_main.main([
    "prepared-document.json",
    "session-artifacts",
    "--host",
    "0.0.0.0",
    "--port",
    "8123",
    "--no-browser",
  ])

  assert exit_code == 0
  assert captured == {
    "prepared_document_path": Path("prepared-document.json"),
    "output_dir": Path("session-artifacts"),
    "host": "0.0.0.0",
    "port": 8123,
    "open_browser": False,
    "graphviz_command": None,
  }
  assert fake_server.wait_calls == 1
  assert fake_server.close_calls == 0


def test_build_and_start_viewer_builds_runtime_bridge_before_starting_server(
  monkeypatch,
  tmp_path,
):
  prepared_document_path = tmp_path / "door-machine.json"
  output_dir = tmp_path / "session-artifacts"
  prepared_document_path.write_text('{"schema_version": "hsm-v1"}', encoding="utf-8")
  fake_server = _FakeServer()
  fake_bridge = _FakeRuntimeBridge()
  built = {}
  app_state = ViewerAppState(
    document_id="door_machine",
    svg_url="/artifacts/diagram.svg",
    highlightable_ids=("idle",),
    text_targets=RuntimeViewerTextTargets(),
  )

  monkeypatch.setattr(
    cli_main,
    "build_viewer_session",
    lambda *args, **kwargs: app_state,
  )
  monkeypatch.setattr(
    cli_main,
    "build_viewer_runtime_bridge",
    lambda path, session_app_state: built.update(
      {"path": path, "app_state": session_app_state}
    )
    or fake_bridge,
  )
  monkeypatch.setattr(
    cli_main,
    "start_viewer_server",
    lambda session_dir, *, runtime_bridge, host, port: built.update(
      {
        "session_dir": session_dir,
        "runtime_bridge": runtime_bridge,
        "host": host,
        "port": port,
      }
    )
    or fake_server,
  )
  opened_urls: list[str] = []
  monkeypatch.setattr(cli_main.webbrowser, "open", opened_urls.append)

  server = cli_main.build_and_start_viewer(
    prepared_document_path,
    output_dir,
    host="0.0.0.0",
    port=8123,
    open_browser=True,
    graphviz_command=("dot",),
  )

  assert server is fake_server
  assert built == {
    "path": prepared_document_path,
    "app_state": app_state,
    "session_dir": output_dir,
    "runtime_bridge": fake_bridge,
    "host": "0.0.0.0",
    "port": 8123,
  }
  assert opened_urls == [fake_server.base_url]


def test_main_closes_server_when_interrupted(monkeypatch):
  fake_server = _FakeServer()

  def fake_wait_until_stopped() -> None:
    fake_server.wait_calls += 1
    raise KeyboardInterrupt

  fake_server.wait_until_stopped = fake_wait_until_stopped

  monkeypatch.setattr(
    cli_main,
    "build_and_start_viewer",
    lambda *args, **kwargs: fake_server,
  )

  exit_code = cli_main.main([
    "prepared-document.json",
    "session-artifacts",
    "--no-browser",
  ])

  assert exit_code == 0
  assert fake_server.wait_calls == 1
  assert fake_server.close_calls == 1
