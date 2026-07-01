from __future__ import annotations

"""Project viewer application entrypoint."""

import argparse
from pathlib import Path
import webbrowser

from mbse.model.project.project_registry import ProjectRegistry
from mbse_web_viewer.server.http_server import RunningViewerServer
from mbse_web_viewer.server.http_server import startViewerServer
from mbse_web_viewer.server.controller import ProjectViewerController


def startProjectViewerServer(
  registry: ProjectRegistry,
  *,
  host: str = "127.0.0.1",
  port: int = 0,
) -> RunningViewerServer:
  """Start one local project viewer HTTP server."""

  return startViewerServer(
    ProjectViewerController(registry),
    host=host,
    port=port,
  )


def startProjectViewerServerFromProjectPath(
  project_path: str | Path,
  *,
  host: str = "127.0.0.1",
  port: int = 0,
  open_browser: bool = False,
) -> RunningViewerServer:
  """Load one project file and start the local project viewer server."""

  server = startProjectViewerServer(
    ProjectRegistry.load(project_path),
    host=host,
    port=port,
  )
  if open_browser:
    webbrowser.open(server.base_url)
  return server


def main(argv: list[str] | None = None) -> int:
  """Start the project viewer server from the command line."""

  parser = argparse.ArgumentParser(description="Launch the MBSE project web viewer.")
  parser.add_argument("project_path")
  parser.add_argument("--host", default="127.0.0.1")
  parser.add_argument("--port", default=0, type=int)
  parser.add_argument("--open-browser", action="store_true")
  args = parser.parse_args(argv)

  server = startProjectViewerServerFromProjectPath(
    args.project_path,
    host=args.host,
    port=args.port,
    open_browser=args.open_browser,
  )
  print(server.base_url)
  try:
    server.waitUntilStopped()
  except KeyboardInterrupt:
    server.close()
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
