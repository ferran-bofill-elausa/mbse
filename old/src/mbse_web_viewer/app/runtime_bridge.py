from __future__ import annotations

from collections.abc import Callable

from mbse.runtime.hsm import HsmExecutedActivity
from mbse.runtime.hsm import HsmRuntime
from mbse.runtime.hsm import HsmRuntimeLastEvent
from mbse.runtime.hsm import HsmRuntimeMetadata

from .viewer_state_types import RuntimeViewerSession
from .viewer_state_types import ViewerAppState


class ViewerRuntimeBridge:
  def __init__(
    self,
    *,
    runtime_factory: Callable[[], HsmRuntime | None],
    app_state: ViewerAppState,
  ) -> None:
    self._runtime_factory = runtime_factory
    self._app_state = app_state
    self._runtime = self._build_runtime()

  @property
  def app_state(self) -> ViewerAppState:
    return self._app_state

  def get_session(self) -> RuntimeViewerSession:
    metadata = self._get_runtime_metadata()
    return RuntimeViewerSession(
      document_id=self._app_state.document_id,
      svg_url=self._app_state.svg_url,
      event_ids=metadata.event_ids,
      variable_ids=metadata.variable_ids,
      snapshot=self._serialize_snapshot(),
      text_targets=self._app_state.text_targets,
    )

  def reset(self) -> RuntimeViewerSession:
    self._runtime = self._build_runtime()
    return self.get_session()

  def send_event(self, event_id: str) -> RuntimeViewerSession:
    self._require_declared_event_id(event_id)
    if self._runtime is None:
      return self.get_session()
    self._runtime.send_event(event_id)
    return self.get_session()

  def set_variable(self, variable_id: str, value: object) -> RuntimeViewerSession:
    self._require_declared_variable_id(variable_id)
    if self._runtime is None:
      return self.get_session()
    self._runtime.set_variable(variable_id, value)
    return self.get_session()

  def _build_runtime(self) -> HsmRuntime | None:
    runtime = self._runtime_factory()
    if runtime is None:
      return None
    runtime.init()
    return runtime

  def _serialize_snapshot(self) -> dict[str, object]:
    if self._runtime is None:
      return {
        "state_id": "",
        "active_path": (),
        "active_ids": (),
        "variables": {},
        "last_event": self._serialize_last_event(HsmRuntimeLastEvent()),
      }
    snapshot = self._runtime.get_snapshot()
    known_ids = set(self._app_state.highlightable_ids)
    active_ids = ()
    if snapshot.state_id in known_ids:
      active_ids = (snapshot.state_id,)
    return {
      "state_id": snapshot.state_id,
      "active_path": snapshot.active_path,
      "active_ids": active_ids,
      "variables": snapshot.variables,
      "last_event": self._serialize_last_event(
        snapshot.last_event,
        known_ids=known_ids,
      ),
    }

  def _serialize_last_event(
    self,
    last_event: HsmRuntimeLastEvent,
    *,
    known_ids: set[str] | None = None,
  ) -> dict[str, object]:
    visible_ids = known_ids or set()
    guard_node_id = None
    if last_event.guard_node_id in visible_ids:
      guard_node_id = last_event.guard_node_id
    guard_branch_id = None
    if last_event.guard_branch_id in visible_ids:
      guard_branch_id = last_event.guard_branch_id
    return {
      "event_id": last_event.event_id,
      "handled": last_event.handled,
      "handler_kind": last_event.handler_kind,
      "handler_id": last_event.handler_id,
      "guard_node_id": guard_node_id,
      "guard_branch_id": guard_branch_id,
      "transition_path_ids": tuple(
        transition_id
        for transition_id in last_event.transition_path_ids
        if transition_id in visible_ids
      ),
      "executed_activities": tuple(
        self._serialize_activity(activity)
        for activity in last_event.executed_activities
      ),
    }

  def _serialize_activity(
    self,
    activity: HsmExecutedActivity,
  ) -> dict[str, str]:
    return {
      "activity_id": activity.activity_id,
      "owner_kind": activity.owner_kind,
      "owner_id": activity.owner_id,
    }

  def _get_runtime_metadata(self) -> HsmRuntimeMetadata:
    if self._runtime is None:
      return HsmRuntimeMetadata(event_ids=(), variable_ids=())
    return self._runtime.get_metadata()

  def _require_declared_event_id(self, event_id: str) -> None:
    if event_id not in self._get_runtime_metadata().event_ids:
      raise ValueError(f"Unknown event_id '{event_id}'.")

  def _require_declared_variable_id(self, variable_id: str) -> None:
    if variable_id not in self._get_runtime_metadata().variable_ids:
      raise ValueError(f"Unknown variable_id '{variable_id}'.")
