"""Minimal application surface for the MBSE web viewer."""

__all__ = [
  "build_and_start_viewer",
  "build_viewer_session",
  "start_viewer_server",
]


def __getattr__(name: str):
  if name == "build_and_start_viewer":
    from mbse_web_viewer.main import build_and_start_viewer

    return build_and_start_viewer
  if name == "build_viewer_session":
    from mbse_web_viewer.app.session import build_viewer_session

    return build_viewer_session
  if name == "start_viewer_server":
    from mbse_web_viewer.app.server import start_viewer_server

    return start_viewer_server
  raise AttributeError(name)
