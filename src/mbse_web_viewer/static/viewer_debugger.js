import { renderDebuggerSummaryLine } from "./viewer_declared_values.js";
import { escapeHtml } from "./viewer_utils.js";


export function renderDebugger(debuggerState, currentRuntimeState) {
  const currentState = document.getElementById("debugger-current-state");
  const currentEvent = document.getElementById("debugger-current-event");
  const queue = document.getElementById("debugger-queue");
  const playButton = document.getElementById("debugger-play-button");
  const pauseButton = document.getElementById("debugger-pause-button");
  const stepIntoButton = document.getElementById("debugger-step-into-button");
  const stepOverButton = document.getElementById("debugger-step-over-button");
  const stepOutButton = document.getElementById("debugger-step-out-button");
  const activeEvent = debuggerState.current_event;
  const queuedEvents = debuggerState.queued_events || [];
  const hasPendingExecution = Boolean(debuggerState.has_pending_execution);
  const canStep = Boolean(debuggerState.can_step);
  const isPaused = Boolean(debuggerState.is_paused);

  playButton.disabled = !isPaused && !hasPendingExecution && queuedEvents.length === 0;
  pauseButton.disabled = isPaused;
  stepIntoButton.disabled = !canStep;
  stepOverButton.disabled = !canStep;
  stepOutButton.disabled = !canStep;

  currentState.innerHTML = renderDebuggerSummaryLine(
    "Current state",
    currentRuntimeState?.label || currentRuntimeState?.id || "Uninitialized",
  );

  currentEvent.innerHTML = activeEvent === null
    ? renderDebuggerSummaryLine("Current event", "idle")
    : `
      ${renderDebuggerSummaryLine("Current event", activeEvent.event_id || "<init>")}
      ${renderEventParametersSummary(activeEvent.parameters || {})}
    `;

  queue.innerHTML = [
    '<div class="debugger-queue-block">',
    `<div class="debugger-queue-item">Queued events <strong>(${queuedEvents.length})</strong>:</div>`,
    queuedEvents.length === 0
      ? ""
      : `
        <ul class="debugger-queue-list">
          ${queuedEvents.map((event) => `
            <li class="debugger-queue-list-item">
              <div class="debugger-queue-item">${escapeHtml(event.event_id || "<init>")}</div>
              ${renderEventParametersSummary(event.parameters || {})}
            </li>
          `).join("")}
        </ul>
      `,
    "</div>",
  ].join("");
}


export function renderEventParametersSummary(parameters) {
  const parameterNames = Object.keys(parameters);
  if (parameterNames.length === 0) {
    return "";
  }
  return `<div class="debugger-queue-item">${escapeHtml(JSON.stringify(parameters))}</div>`;
}
