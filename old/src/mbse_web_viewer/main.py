from __future__ import annotations

import argparse
import json
from pathlib import Path
import webbrowser

from mbse.runtime.hsm import build_hsm_runtime
from mbse_web_viewer.app.runtime_bridge import ViewerRuntimeBridge
from mbse_web_viewer.app.server import RunningViewerServer
from mbse_web_viewer.app.server import start_viewer_server
from mbse_web_viewer.app.session import build_viewer_session
from mbse_web_viewer.app.viewer_state_types import ViewerAppState


def build_and_start_viewer(
  prepared_document_path: Path,
  output_dir: Path,
  *,
  host: str = "127.0.0.1",
  port: int = 0,
  open_browser: bool = True,
  graphviz_command: tuple[str, ...] | None = None,
) -> RunningViewerServer:
  app_state = build_viewer_session(
    prepared_document_path,
    output_dir,
    graphviz_command=graphviz_command,
  )
  runtime_bridge = build_viewer_runtime_bridge(
    prepared_document_path,
    app_state,
  )
  server = start_viewer_server(
    output_dir,
    runtime_bridge=runtime_bridge,
    host=host,
    port=port,
  )
  if open_browser:
    webbrowser.open(server.base_url)
  return server


def build_viewer_runtime_bridge(
  prepared_document_path: Path,
  app_state: ViewerAppState,
) -> ViewerRuntimeBridge:
  payload = json.loads(prepared_document_path.read_text(encoding="utf-8"))
  if "schema_version" not in payload:
    return ViewerRuntimeBridge(
      runtime_factory=lambda: None,
      app_state=app_state,
    )
  return ViewerRuntimeBridge(
    runtime_factory=lambda: build_hsm_runtime(payload),
    app_state=app_state,
  )


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description="Launch the MBSE web viewer.")
  parser.add_argument("prepared_document")
  parser.add_argument("output_dir")
  parser.add_argument("--host", default="127.0.0.1")
  parser.add_argument("--port", default=0, type=int)
  parser.add_argument("--no-browser", action="store_true")
  args = parser.parse_args(argv)

  server = build_and_start_viewer(
    Path(args.prepared_document),
    Path(args.output_dir),
    host=args.host,
    port=args.port,
    open_browser=not args.no_browser,
  )
  print(server.base_url)
  try:
    server.wait_until_stopped()
  except KeyboardInterrupt:
    server.close()
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
