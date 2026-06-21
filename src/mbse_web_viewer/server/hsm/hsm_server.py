from __future__ import annotations

"""Serve one HSM runtime session together with its rendered SVG viewer."""

import argparse
from dataclasses import asdict
from dataclasses import dataclass
from functools import partial
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
import json
from json import JSONDecodeError
from pathlib import Path
from threading import Thread
from typing import Any
import webbrowser

from mbse.model.hsm.hsm_model import HsmExternalTransitionRelation
from mbse.model.hsm.hsm_model import HsmGuardedTransitionBranchRelation
from mbse.model.hsm.hsm_model import HsmModel
from mbse.model.hsm.hsm_model import HsmRelatedState
from mbse.runtime.hsm.hsm_runtime import HsmRuntime
from mbse.runtime.hsm.hsm_runtime import HsmRuntimeTrace
from mbse_web_viewer.render.hsm.hsm_render import HsmRender


_STATIC_DIR = Path(__file__).resolve().parents[2] / "static"


@dataclass(frozen=True)
class HsmViewerHighlight:
  """Resolved SVG ids to highlight for the current viewer session."""

  state_ids: tuple[str, ...]
  transition_ids: tuple[str, ...]
  text_ids: tuple[str, ...]


@dataclass(frozen=True)
class HsmViewerTrace:
  """Serialized view of the latest runtime trace."""

  event_id: str | None
  entries: list[dict[str, object]]


@dataclass(frozen=True)
class HsmViewerFocus:
  """Resolved SVG ids related directly to the current active state."""

  related_ids: tuple[str, ...]


@dataclass(frozen=True)
class HsmViewerSession:
  """Full JSON session served to the browser viewer."""

  document_id: str
  svg_url: str
  enums: tuple[dict[str, object], ...]
  events: tuple[dict[str, object], ...]
  variables: tuple[dict[str, object], ...]
  state: dict[str, str | None]
  variable_values: dict[str, Any]
  execution_log: list[dict[str, object]]
  highlight: HsmViewerHighlight
  focus: HsmViewerFocus
  last_trace: HsmViewerTrace


class RunningHsmViewerServer:
  """Running HTTP server handle for one HSM viewer instance."""

  def __init__(self, httpd: ThreadingHTTPServer, thread: Thread) -> None:
    """Wrap one started HTTP server and its serving thread."""

    self._httpd = httpd
    self._thread = thread
    self.base_url = f"http://{httpd.server_address[0]}:{httpd.server_address[1]}"

  def waitUntilStopped(self) -> None:
    """Block until the serving thread stops."""

    self._thread.join()

  def close(self) -> None:
    """Stop the HTTP server and wait briefly for shutdown."""

    self._httpd.shutdown()
    self._httpd.server_close()
    self._thread.join(timeout=5)


class HsmViewerServerController:
  """Own the rendered SVG, runtime instance, and derived viewer session."""

  def __init__(self, model: HsmModel) -> None:
    """Initialize the controller from one validated HSM model."""

    self._model = model
    self._rendered_svg = HsmRender()
    self._rendered_svg.render(model)
    self._runtime = self._buildRuntime()
    self._last_highlight = self._buildCurrentTraceHighlight()

  def getSvgText(self) -> str:
    """Return the rendered SVG document served by the viewer."""

    return self._rendered_svg.getSvgText()

  def getSession(self) -> HsmViewerSession:
    """Return the current serialized browser session."""

    return HsmViewerSession(
      document_id=self._model.getDocumentId(),
      svg_url="/artifacts/diagram.svg",
      enums=tuple(dict(enum) for enum in self._model.getEnums()),
      events=tuple(dict(event) for event in self._model.getEvents()),
      variables=tuple(dict(variable) for variable in self._model.getVariables()),
      state=self._runtime.getState(),
      variable_values={
        variable["name"]: self._runtime.getVariable(variable["name"])
        for variable in self._model.getVariables()
      },
      execution_log=self._serializeExecutionLog(),
      highlight=self._last_highlight,
      focus=self._buildCurrentStateFocus(),
      last_trace=self._serializeLastTrace(),
    )

  def reset(self) -> HsmViewerSession:
    """Reset the runtime and return the refreshed browser session."""

    self._runtime = self._buildRuntime()
    self._last_highlight = self._buildCurrentTraceHighlight()
    return self.getSession()

  def sendEvent(
    self,
    event_id: str,
    parameters: dict[str, Any] | None = None,
  ) -> HsmViewerSession:
    """Send one runtime event and return the refreshed browser session."""

    self._requireDeclaredEventId(event_id)
    self._runtime.sendEvent(event_id, parameters)
    self._last_highlight = self._buildCurrentTraceHighlight()
    return self.getSession()

  def setVariable(self, variable_id: str, value: Any) -> HsmViewerSession:
    """Set one runtime variable and return the refreshed browser session."""

    self._requireDeclaredVariableId(variable_id)
    self._runtime.setVariable(variable_id, value)
    return self.getSession()

  def _buildRuntime(self) -> HsmRuntime:
    """Create and initialize one fresh runtime from the current model."""

    runtime = HsmRuntime()
    runtime.init(self._model)
    return runtime

  def _serializeLastTrace(self) -> HsmViewerTrace:
    """Serialize the latest runtime trace for lightweight browser inspection."""

    if not self._runtime.getExecutionLog():
      return HsmViewerTrace(event_id=None, entries=[])

    trace = self._runtime.getExecutionLog()[-1]
    return HsmViewerTrace(
      event_id=trace["event"]["event_id"],
      entries=[dict(entry) for entry in trace["entries"]],
    )

  def _serializeExecutionLog(self) -> list[dict[str, object]]:
    """Serialize the full runtime execution log without viewer formatting."""

    return [
      {
        "event": dict(trace["event"]),
        "entries": [dict(entry) for entry in trace["entries"]],
      }
      for trace in self._runtime.getExecutionLog()
    ]

  def _buildCurrentTraceHighlight(self) -> HsmViewerHighlight:
    """Resolve the latest runtime trace into SVG ids for highlighting."""

    trace = self._runtime.getExecutionLog()[-1]
    state_ids = self._buildStateHighlightIds()
    transition_ids = list(self._buildTraceTransitionIds(trace))
    text_ids = list(self._buildTraceTextIds(trace, transition_ids))
    return HsmViewerHighlight(
      state_ids=state_ids,
      transition_ids=tuple(dict.fromkeys(transition_ids)),
      text_ids=tuple(dict.fromkeys(text_ids)),
    )

  def _buildCurrentStateFocus(self) -> HsmViewerFocus:
    """Resolve the SVG ids directly related to the current active state."""

    state_id = self._runtime.getState()["id"]
    if state_id is None:
      return HsmViewerFocus(related_ids=())

    related = self._model.getStateRelatedElements(state_id)
    related_ids = self._buildStateFocusIds(related.states)

    for chain in related.initial_entry_chains:
      for transition in chain:
        if transition.source_state_id is None:
          related_ids.append(self._rendered_svg.getRootInitialTransitionId())
          related_ids.append(self._rendered_svg.getRootInitialTransitionSourceId())
          continue
        related_ids.append(
          self._rendered_svg.getInitialTransitionId(transition.source_state_id)
        )
        related_ids.append(
          self._rendered_svg.getInitialTransitionSourceId(transition.source_state_id)
        )

    for transition in related.outgoing_external_transitions:
      related_ids.extend(self._buildExternalTransitionFocusIds(transition))

    for transition in related.incoming_external_transitions:
      related_ids.extend(self._buildExternalTransitionFocusIds(transition))

    for branch in related.guarded_transition_branches:
      related_ids.extend(self._buildGuardedBranchFocusIds(branch))

    return HsmViewerFocus(related_ids=tuple(dict.fromkeys(related_ids)))

  def _buildStateFocusIds(self, related_states: tuple[HsmRelatedState, ...]) -> list[str]:
    """Resolve state and state-owned text ids for the related state set."""

    related_ids: list[str] = []

    for related_state in related_states:
      state_id = related_state.state_id
      related_ids.append(self._rendered_svg.getStateId(state_id))

      for section_name, activities in (
        ("on_entry", related_state.on_entry_activities),
        ("on_initial", related_state.on_initial_activities),
        ("on_exit", related_state.on_exit_activities),
      ):
        related_ids.extend(
          self._rendered_svg.getLifecycleSectionTextIds(state_id, section_name)
        )
        for activity in activities:
          related_ids.extend(
            self._rendered_svg.getLifecycleActivityTextIds(
              state_id,
              section_name,
              activity,
            )
          )

      for transition in related_state.internal_transitions:
        event_id = transition["event_id"]
        internal_ids = self._rendered_svg.getInternalTransitionIds(state_id, event_id)
        related_ids.extend(internal_ids)
        related_ids.extend(
          self._rendered_svg.getInternalTransitionSectionTextIds(state_id, event_id)
        )
        for transition_id in internal_ids:
          related_ids.extend(
            self._rendered_svg.getInternalTransitionEventTextIds(transition_id)
          )
          for activity in transition.get("activities", []):
            related_ids.extend(
              self._rendered_svg.getInternalTransitionActivityTextIds(
                transition_id,
                activity,
              )
            )

    return related_ids

  def _buildExternalTransitionFocusIds(
    self,
    transition: HsmExternalTransitionRelation,
  ) -> list[str]:
    """Resolve one unguarded external transition and its related ids."""

    related_ids: list[str] = []
    transition_ids = self._rendered_svg.getExternalTransitionIds(
      transition.source_state_id,
      transition.event_id,
      transition.target_state_id,
    )
    related_ids.extend(transition_ids)
    related_ids.append(self._rendered_svg.getStateId(transition.source_state_id))
    related_ids.append(self._rendered_svg.getStateId(transition.target_state_id))
    for transition_id in transition_ids:
      related_ids.extend(
        self._rendered_svg.getExternalTransitionLabelTextIds(transition_id)
      )
      for activity in transition.activities:
        related_ids.extend(
          self._rendered_svg.getExternalTransitionActivityTextIds(
            transition_id,
            activity,
          )
        )
    return related_ids

  def _buildGuardedBranchFocusIds(
    self,
    branch: HsmGuardedTransitionBranchRelation,
  ) -> list[str]:
    """Resolve one guarded branch relation and its related ids."""

    related_ids: list[str] = []
    guarded_ids = self._rendered_svg.getGuardedTransitionIds(
      branch.source_state_id,
      branch.event_id,
    )
    guard_node_ids = self._rendered_svg.getGuardNodeIds(
      branch.source_state_id,
      branch.event_id,
    )
    branch_ids = self._rendered_svg.getGuardBranchIds(
      branch.source_state_id,
      branch.event_id,
      outcome=branch.guard_result,
      target_state_id=branch.target_state_id,
    )
    related_ids.extend(guarded_ids)
    related_ids.extend(guard_node_ids)
    related_ids.extend(branch_ids)
    related_ids.append(self._rendered_svg.getStateId(branch.source_state_id))
    related_ids.append(self._rendered_svg.getStateId(branch.target_state_id))

    for guarded_id in guarded_ids:
      related_ids.extend(
        self._rendered_svg.getExternalTransitionLabelTextIds(guarded_id)
      )
      for activity in branch.transition_activities:
        related_ids.extend(
          self._rendered_svg.getExternalTransitionActivityTextIds(
            guarded_id,
            activity,
          )
        )

    for branch_id in branch_ids:
      related_ids.extend(
        self._rendered_svg.getExternalTransitionLabelTextIds(branch_id)
      )
      for activity in branch.branch_activities:
        related_ids.extend(
          self._rendered_svg.getExternalTransitionActivityTextIds(
            branch_id,
            activity,
          )
        )

    return related_ids

  def _buildStateHighlightIds(self) -> tuple[str, ...]:
    """Return the highlight ids for the current active state."""

    state_id = self._runtime.getState()["id"]
    if state_id is None:
      return ()
    return (self._rendered_svg.getStateId(state_id),)

  def _buildTraceTransitionIds(
    self,
    trace: HsmRuntimeTrace,
  ) -> tuple[str, ...]:
    """Resolve structural transition ids from one completed runtime trace."""

    event_id = trace["event"]["event_id"]
    resolved_ids: list[str] = []

    guarded_targets: set[tuple[str, str]] = set()
    for entry in trace["entries"]:
      if entry["kind"] == "initial_transition":
        source_state_id = entry["source_state_id"]
        if source_state_id is None:
          resolved_ids.append(self._rendered_svg.getRootInitialTransitionId())
        else:
          resolved_ids.append(
            self._rendered_svg.getInitialTransitionId(source_state_id)
          )
        continue

      if event_id is None:
        continue

      if entry["kind"] == "internal_transition":
        resolved_ids.extend(
          self._rendered_svg.getInternalTransitionIds(
            entry["source_state_id"],
            event_id,
          )
        )
        continue

      if entry["kind"] == "guard_condition":
        source_state_id = entry["source_state_id"]
        guarded_targets.add((source_state_id, entry["target_state_id"]))
        resolved_ids.extend(
          self._rendered_svg.getGuardedTransitionIds(
            source_state_id,
            event_id,
          )
        )
        resolved_ids.extend(
          self._rendered_svg.getGuardNodeIds(source_state_id, event_id)
        )
        resolved_ids.extend(
          self._rendered_svg.getGuardBranchIds(
            source_state_id,
            event_id,
            outcome=entry["result"],
            target_state_id=entry["target_state_id"],
          )
        )
        continue

      if entry["kind"] == "external_transition":
        source_state_id = entry["source_state_id"]
        target_state_id = entry["target_state_id"]
        if (source_state_id, target_state_id) in guarded_targets:
          continue
        resolved_ids.extend(
          self._rendered_svg.getExternalTransitionIds(
            source_state_id,
            event_id,
            target_state_id,
          )
        )
    return tuple(resolved_ids)

  def _buildTraceTextIds(
    self,
    trace: HsmRuntimeTrace,
    transition_ids: list[str],
  ) -> tuple[str, ...]:
    """Resolve the text fragment ids associated with the latest trace."""

    event_id = trace["event"]["event_id"]
    resolved_ids: list[str] = []

    for transition_id in transition_ids:
      resolved_ids.extend(
        self._rendered_svg.getExternalTransitionLabelTextIds(transition_id)
      )

    internal_owner_ids_by_state_id: dict[str, tuple[str, ...]] = {}
    external_owner_ids_by_state_id: dict[str, tuple[str, ...]] = {}
    branch_owner_ids_by_state_id: dict[str, tuple[str, ...]] = {}
    guarded_target_by_state_id: dict[str, str] = {}

    for entry in trace["entries"]:
      if entry["kind"] in {"on_entry", "on_initial", "on_exit"}:
        source_state_id = entry["source_state_id"]
        resolved_ids.extend(
          self._rendered_svg.getLifecycleSectionTextIds(
            source_state_id,
            entry["kind"],
          )
        )
        resolved_ids.extend(
          self._rendered_svg.getLifecycleActivityTextIds(
            source_state_id,
            entry["kind"],
            entry["activity"],
          )
        )
        continue

      if event_id is None:
        continue

      if entry["kind"] == "internal_transition":
        source_state_id = entry["source_state_id"]
        internal_ids = self._rendered_svg.getInternalTransitionIds(
          source_state_id,
          event_id,
        )
        internal_owner_ids_by_state_id[source_state_id] = internal_ids
        for transition_id in internal_ids:
          resolved_ids.extend(
            self._rendered_svg.getInternalTransitionSectionTextIds(
              source_state_id,
              event_id,
            )
          )
          resolved_ids.extend(
            self._rendered_svg.getInternalTransitionEventTextIds(
              transition_id,
            )
          )
        continue

      if entry["kind"] == "guard_condition":
        source_state_id = entry["source_state_id"]
        guarded_target_by_state_id[source_state_id] = entry["target_state_id"]
        guarded_ids = self._rendered_svg.getGuardedTransitionIds(
          source_state_id,
          event_id,
        )
        branch_ids = self._rendered_svg.getGuardBranchIds(
          source_state_id,
          event_id,
          outcome=entry["result"],
          target_state_id=entry["target_state_id"],
        )
        external_owner_ids_by_state_id[source_state_id] = guarded_ids
        branch_owner_ids_by_state_id[source_state_id] = branch_ids
        continue

      if entry["kind"] == "external_transition":
        source_state_id = entry["source_state_id"]
        target_state_id = entry["target_state_id"]
        if guarded_target_by_state_id.get(source_state_id) == target_state_id:
          continue
        external_ids = self._rendered_svg.getExternalTransitionIds(
          source_state_id,
          event_id,
          target_state_id,
        )
        external_owner_ids_by_state_id[source_state_id] = external_ids
        continue

      if entry["kind"] != "activity":
        continue

      source_state_id = entry["source_state_id"]
      if entry["activity_owner"] == "internal_transition":
        for transition_id in internal_owner_ids_by_state_id.get(source_state_id, ()):
          resolved_ids.extend(
            self._rendered_svg.getInternalTransitionActivityTextIds(
              transition_id,
              entry["activity"],
            )
          )
        continue

      if entry["activity_owner"] == "guard_branch":
        branch_owner_ids = branch_owner_ids_by_state_id.get(source_state_id)
        if branch_owner_ids is None:
          continue
        for branch_owner_id in branch_owner_ids:
          resolved_ids.extend(
            self._rendered_svg.getExternalTransitionActivityTextIds(
              branch_owner_id,
              entry["activity"],
            )
          )
        continue

      transition_owner_ids = external_owner_ids_by_state_id.get(source_state_id)
      if transition_owner_ids is not None:
        for transition_owner_id in transition_owner_ids:
          resolved_ids.extend(
            self._rendered_svg.getExternalTransitionActivityTextIds(
              transition_owner_id,
              entry["activity"],
            )
          )
    return tuple(resolved_ids)

  def _requireDeclaredEventId(self, event_id: str) -> None:
    """Reject one event id that is not declared by the current model."""

    self._model.getEventById(event_id)

  def _requireDeclaredVariableId(self, variable_id: str) -> None:
    """Reject one variable id that is not declared by the current model."""

    self._model.getVariableByName(variable_id)


class HsmViewerRequestHandler(BaseHTTPRequestHandler):
  """Serve static assets plus a small runtime API for one HSM viewer."""

  def __init__(
    self,
    *args: Any,
    controller: HsmViewerServerController,
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
    if self.path == "/viewer.css":
      self._serveStatic("viewer.css", "text/css; charset=utf-8")
      return
    if self.path == "/viewer.js":
      self._serveStatic("viewer.js", "application/javascript; charset=utf-8")
      return
    if self.path == "/api/session.json":
      self._sendJson(asdict(self._controller.getSession()))
      return
    if self.path == "/artifacts/diagram.svg":
      self._sendBytes(
        self._controller.getSvgText().encode("utf-8"),
        content_type="image/svg+xml; charset=utf-8",
      )
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
              payload.get("parameters") if isinstance(payload.get("parameters"), dict) else None,
            )
          )
        )
      except (KeyError, ValueError) as error:
        self.send_error(400, str(error))
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


def startHsmViewerServer(
  model: HsmModel,
  *,
  host: str = "127.0.0.1",
  port: int = 0,
) -> RunningHsmViewerServer:
  """Start one local HSM viewer HTTP server for the given model."""

  controller = HsmViewerServerController(model)
  httpd = ThreadingHTTPServer(
    (host, port),
    partial(HsmViewerRequestHandler, controller=controller),
  )
  thread = Thread(target=httpd.serve_forever, daemon=True)
  thread.start()
  return RunningHsmViewerServer(httpd, thread)


def startHsmViewerServerFromModelPath(
  model_path: str | Path,
  *,
  host: str = "127.0.0.1",
  port: int = 0,
  open_browser: bool = False,
) -> RunningHsmViewerServer:
  """Load one HSM model file and start the local viewer server."""

  server = startHsmViewerServer(
    HsmModel.loadAndValidate(model_path),
    host=host,
    port=port,
  )
  if open_browser:
    webbrowser.open(server.base_url)
  return server


def main(argv: list[str] | None = None) -> int:
  """Start the HSM viewer server from the command line."""

  parser = argparse.ArgumentParser(description="Launch the MBSE HSM web viewer.")
  parser.add_argument("model_path")
  parser.add_argument("--host", default="127.0.0.1")
  parser.add_argument("--port", default=0, type=int)
  parser.add_argument("--open-browser", action="store_true")
  args = parser.parse_args(argv)

  server = startHsmViewerServerFromModelPath(
    args.model_path,
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
