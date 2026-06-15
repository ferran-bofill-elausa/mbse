from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

import quickjs


VIEWER_JS_PATH = ROOT / "src" / "mbse_web_viewer" / "static" / "viewer.js"


class ViewerBrowserHarness:
  def __init__(
    self,
    *,
    session_payload: dict[str, object],
    svg_text: str,
    fetch_responses: dict[str, list[dict[str, object]]] | None = None,
    viewport_size: dict[str, int] | None = None,
    viewport_padding: dict[str, int] | None = None,
  ) -> None:
    self._context = quickjs.Context()
    self._context.eval(_HARNESS_JS)
    if viewport_size is not None:
      self._context.eval(
        "__setViewportSize(%s, %s);"
        % (
          json.dumps(viewport_size["width"]),
          json.dumps(viewport_size["height"]),
        )
      )
    if viewport_padding is not None:
      self._context.eval(
        "__setViewportPadding(%s, %s);"
        % (
          json.dumps(viewport_padding["x"]),
          json.dumps(viewport_padding["y"]),
        )
      )
    self._context.eval(
      f"__setFetchResponses('/api/session.json', [{json.dumps({'body': session_payload})}]);"
    )
    self._context.eval(
      f"__setFetchResponses('/artifacts/diagram.svg', [{json.dumps({'body': svg_text})}]);"
    )
    for url, responses in (fetch_responses or {}).items():
      self._context.eval(
        f"__setFetchResponses({json.dumps(url)}, {json.dumps(responses)});"
      )
    self._context.eval(VIEWER_JS_PATH.read_text(encoding="utf-8"))

  def render(self) -> dict[str, object]:
    self._drain_jobs()
    return self._snapshot()

  def click(self, element_id: str) -> dict[str, object]:
    self._context.eval(f"__click({json.dumps(element_id)});")
    self._drain_jobs()
    return self._snapshot()

  def drag_splitter(self, *, start_x: int, move_x: int) -> dict[str, object]:
    self._context.eval(
      "__dragSplitter(%s, %s, null, null);"
      % (
        json.dumps(start_x),
        json.dumps(move_x),
      )
    )
    self._drain_jobs()
    return self._snapshot()

  def drag_splitter_with_viewport_resize(
    self,
    *,
    start_x: int,
    move_x: int,
    width: int,
    height: int | None = None,
  ) -> dict[str, object]:
    self._context.eval(
      "__dragSplitter(%s, %s, %s, %s);"
      % (
        json.dumps(start_x),
        json.dumps(move_x),
        json.dumps(width),
        "null" if height is None else json.dumps(height),
      )
    )
    self._drain_jobs()
    return self._snapshot()

  def submit_variable(self, variable_id: str, raw_value: str) -> dict[str, object]:
    self._context.eval(
      f"__submitVariable({json.dumps(variable_id)}, {json.dumps(raw_value)});"
    )
    self._drain_jobs()
    return self._snapshot()

  def submit_event(self, event_id: str) -> dict[str, object]:
    self._context.eval(f"__submitEvent({json.dumps(event_id)});")
    self._drain_jobs()
    return self._snapshot()

  def wheel_viewport(self, *, delta_y: int) -> dict[str, object]:
    self._context.eval(f"__wheelViewport({json.dumps(delta_y)});")
    self._drain_jobs()
    return self._snapshot()

  def wheel_sidebar(self, *, delta_y: int) -> dict[str, object]:
    self._context.eval(f"__wheelSidebar({json.dumps(delta_y)});")
    self._drain_jobs()
    return self._snapshot()

  def drag_viewport(
    self,
    *,
    start_x: int,
    start_y: int,
    move_x: int,
    move_y: int,
  ) -> dict[str, object]:
    self._context.eval(
      "__dragViewport(%s, %s, %s, %s);"
      % (
        json.dumps(start_x),
        json.dumps(start_y),
        json.dumps(move_x),
        json.dumps(move_y),
      )
    )
    self._drain_jobs()
    return self._snapshot()

  def start_viewport_drag(self, *, start_x: int, start_y: int) -> dict[str, object]:
    self._context.eval(
      "__startViewportDrag(%s, %s);"
      % (json.dumps(start_x), json.dumps(start_y))
    )
    self._drain_jobs()
    return self._snapshot()

  def move_document_drag(self, *, move_x: int, move_y: int) -> dict[str, object]:
    self._context.eval(
      "__moveDocumentDrag(%s, %s);"
      % (json.dumps(move_x), json.dumps(move_y))
    )
    self._drain_jobs()
    return self._snapshot()

  def end_document_drag(self, *, end_x: int, end_y: int) -> dict[str, object]:
    self._context.eval(
      "__endDocumentDrag(%s, %s);"
      % (json.dumps(end_x), json.dumps(end_y))
    )
    self._drain_jobs()
    return self._snapshot()

  def resize_viewport(self, *, width: int, height: int) -> dict[str, object]:
    self._context.eval(
      "__setViewportSize(%s, %s);"
      % (json.dumps(width), json.dumps(height))
    )
    self._drain_jobs()
    return self._snapshot()

  def _drain_jobs(self) -> None:
    while self._context.execute_pending_job():
      continue

  def _snapshot(self) -> dict[str, object]:
    return json.loads(self._context.eval("__snapshot()"))


_HARNESS_JS = r'''
var __fetchQueue = {};
var __fetchCounts = {};
var __lastRequests = {};
var __elements = {};
var __documentListeners = {};
var __viewportSize = { width: 400, height: 200 };
var __viewportPadding = { x: 0, y: 0 };
var __selectionSideEffects = { rangeCount: 0, text: '' };

function __decodeHtml(value) {
  return String(value)
    .replaceAll('&quot;', '"')
    .replaceAll('&#39;', "'")
    .replaceAll('&gt;', '>')
    .replaceAll('&lt;', '<')
    .replaceAll('&amp;', '&');
}

var __svgNodeCounter = 0;

function __svgGeneratedId(tagName) {
  __svgNodeCounter += 1;
  return '__svg_' + String(tagName).toLowerCase() + '_' + String(__svgNodeCounter);
}

function __svgAttributeMap(rawAttributes) {
  var attributes = {};
  var matches = Array.from(String(rawAttributes || '').matchAll(/([:\w-]+)="([^"]*)"/g));
  for (var i = 0; i < matches.length; i += 1) {
    attributes[matches[i][1]] = __decodeHtml(matches[i][2]);
  }
  return attributes;
}

function __parseSvgLength(value) {
  var raw = String(value || '').trim();
  if (!raw.length) {
    return 0;
  }
  var match = raw.match(/^(-?\d+(?:\.\d+)?)([a-z%]*)$/i);
  if (!match) {
    return 0;
  }
  var numeric = Number(match[1]);
  if (!Number.isFinite(numeric)) {
    return 0;
  }
  var unit = match[2].toLowerCase();
  if (!unit || unit === 'px') {
    return numeric;
  }
  if (unit === 'pt') {
    return numeric * (96 / 72);
  }
  return numeric;
}

function __currentSvgRootScale() {
  var transform = String((__elements['svg-root'] && __elements['svg-root'].style.transform) || '');
  var match = transform.match(/scale\(([^)]+)\)/);
  if (!match) {
    return 1;
  }
  var scale = Number(match[1]);
  return Number.isFinite(scale) && scale > 0 ? scale : 1;
}

function __createSvgNode(tagName, attributes) {
  var elementId = attributes.id || __svgGeneratedId(tagName);
  var element = __elements[elementId] || __createElement(elementId, tagName);
  element.tagName = tagName;
  element.__children = [];
  element.__parent = null;
  element.__classes = element.__classes || [];
  element.className = element.__classes.join(' ');
  __elements[elementId] = element;
  return element;
}

function __buildSvgTree(svgText, svgElement) {
  var stack = [svgElement];
  var tagMatches = Array.from(String(svgText).matchAll(/<\/?([:\w-]+)([^>]*)>/g));
  for (var i = 0; i < tagMatches.length; i += 1) {
    var fullMatch = tagMatches[i][0];
    var tagName = tagMatches[i][1].toLowerCase();
    if (tagName === 'svg') {
      continue;
    }
    if (fullMatch.slice(0, 2) === '</') {
      if (stack.length > 1) {
        stack.pop();
      }
      continue;
    }
    var node = __createSvgNode(tagName, __svgAttributeMap(tagMatches[i][2]));
    stack[stack.length - 1].appendChild(node);
    if (!fullMatch.endsWith('/>')) {
      stack.push(node);
    }
  }
}

function __summarizeHighlightGroup(element) {
  var directChildTags = element.__children.map(function(child) {
    return child.tagName.toLowerCase();
  });
  var directShapeTags = element.__children
    .filter(function(child) {
      return ['ellipse', 'path', 'polygon', 'rect'].indexOf(child.tagName.toLowerCase()) !== -1;
    })
    .map(function(child) {
      return child.tagName.toLowerCase();
    });
  var textDescendantTags = [];
  var nestedGroupIds = [];

  function walk(node) {
    for (var i = 0; i < node.__children.length; i += 1) {
      var child = node.__children[i];
      var tagName = child.tagName.toLowerCase();
      if (tagName === 'text') {
        textDescendantTags.push(tagName);
      }
      if (tagName === 'g' && child.id) {
        nestedGroupIds.push(child.id);
      }
      walk(child);
    }
  }

  walk(element);
  return {
    id: element.id,
    direct_child_tags: directChildTags,
    direct_shape_tags: directShapeTags,
    text_descendant_tags: textDescendantTags,
    nested_group_ids: nestedGroupIds,
  };
}

function __highlightGroupsFor(className) {
  return Object.keys(__elements)
    .map(function(key) {
      return __elements[key];
    })
    .filter(function(element) {
      return element.__classes.indexOf(className) !== -1;
    })
    .sort(function(left, right) {
      return left.id.localeCompare(right.id);
    })
    .map(__summarizeHighlightGroup);
}

function __matchesSelector(element, selector) {
  if (selector[0] === '#') {
    return element.id === selector.slice(1);
  }
  if (selector[0] === '.') {
    return element.__classes.indexOf(selector.slice(1)) !== -1;
  }
  return element.tagName.toLowerCase() === selector.toLowerCase();
}

function __createClassList(element) {
  return {
    add: function(name) {
      if (element.__classes.indexOf(name) === -1) {
        element.__classes.push(name);
      }
      element.className = element.__classes.join(' ');
    },
    remove: function(name) {
      element.__classes = element.__classes.filter(function(item) {
        return item !== name;
      });
      element.className = element.__classes.join(' ');
    },
    toggle: function(name, force) {
      var shouldAdd = force;
      if (arguments.length === 1) {
        shouldAdd = element.__classes.indexOf(name) === -1;
      }
      if (shouldAdd) {
        this.add(name);
        return true;
      }
      this.remove(name);
      return false;
    }
  };
}

function __createElement(id, tagName) {
  var element = {
    id: id || '',
    tagName: tagName || 'div',
    dataset: {},
    style: {
      setProperty: function(name, value) {
        this[name] = value;
      }
    },
    value: '',
    disabled: false,
    textContent: '',
    scrollTop: 0,
    scrollLeft: 0,
    clientWidth: 0,
    clientHeight: 0,
    className: '',
    __classes: [],
    __children: [],
    __listeners: {},
    __parent: null,
    __innerHTML: '',
    addEventListener: function(type, handler) {
      this.__listeners[type] = handler;
    },
    appendChild: function(child) {
      child.__parent = this;
      this.__children.push(child);
      return child;
    },
    closest: function(selector) {
      var current = this;
      while (current) {
        if (__matchesSelector(current, selector)) {
          return current;
        }
        current = current.__parent;
      }
      return null;
    },
    querySelector: function(selector) {
      var matches = this.querySelectorAll(selector);
      return matches.length ? matches[0] : null;
    },
    querySelectorAll: function(selector) {
      var matches = [];
      function walk(node) {
        for (var i = 0; i < node.__children.length; i += 1) {
          var child = node.__children[i];
          if (__matchesSelector(child, selector)) {
            matches.push(child);
          }
          walk(child);
        }
      }
      walk(this);
      return matches;
    },
  };
  element.classList = __createClassList(element);
  Object.defineProperty(element, 'innerHTML', {
    get: function() {
      return element.__innerHTML;
    },
    set: function(value) {
      element.__innerHTML = value;
      element.__children = [];
      if (element.id === 'svg-root') {
        var svgMatch = String(value).match(/<svg([^>]*)>/);
        var svgElement = __createElement('svg-root-svg', 'svg');
        var svgAttributes = __svgAttributeMap(svgMatch ? svgMatch[1] : '');
        var viewBoxValues = (svgAttributes.viewBox || '0 0 0 0').split(/\s+/).map(Number);
        svgElement.viewBox = {
          baseVal: {
            width: viewBoxValues[2] || 0,
            height: viewBoxValues[3] || 0,
          }
        };
        svgElement.width = {
          baseVal: {
            value: __parseSvgLength(svgAttributes.width),
          }
        };
        svgElement.height = {
          baseVal: {
            value: __parseSvgLength(svgAttributes.height),
          }
        };
        svgElement.getBBox = function() {
          return {
            x: 0,
            y: 0,
            width: this.viewBox.baseVal.width,
            height: this.viewBox.baseVal.height,
          };
        };
        svgElement.getBoundingClientRect = function() {
          var width = this.width.baseVal.value || this.viewBox.baseVal.width;
          var height = this.height.baseVal.value || this.viewBox.baseVal.height;
          var scale = __currentSvgRootScale();
          return {
            x: 0,
            y: 0,
            width: width * scale,
            height: height * scale,
          };
        };
        svgElement.clientWidth = svgElement.width.baseVal.value || svgElement.viewBox.baseVal.width;
        svgElement.clientHeight = svgElement.height.baseVal.value || svgElement.viewBox.baseVal.height;
        __elements[svgElement.id] = svgElement;
        element.appendChild(svgElement);
        __buildSvgTree(String(value), svgElement);
      }
      if (element.id === 'variable-list') {
        var rowMatches = Array.from(String(value).matchAll(/<form[\s\S]*?class="variable-row"[\s\S]*?data-variable-id="([^"]+)"([\s\S]*?)<\/form>/g));
        for (var j = 0; j < rowMatches.length; j += 1) {
          var rowMarkup = rowMatches[j][2];
          var labelMatch = rowMarkup.match(/<strong>([^<]+)<\/strong>/);
          var inputMatch = rowMarkup.match(/<input[\s\S]*?value="([^"]*)"/);
          var unsetMatch = rowMarkup.match(/<span class="variable-unset">([^<]*)<\/span>/);
          var row = __createElement('variable-row-' + j, 'form');
          row.__classes = ['variable-row'];
          row.className = 'variable-row';
          row.dataset.variableId = rowMatches[j][1];
          row.compactLayout = rowMarkup.indexOf('class="variable-row-main"') !== -1;
          row.variableLabel = labelMatch ? __decodeHtml(labelMatch[1]) : '';
          row.textboxValue = inputMatch ? __decodeHtml(inputMatch[1]) : '';
          row.inlineUnsetText = unsetMatch ? __decodeHtml(unsetMatch[1]).trim() : '';
          row.hasValueDisplay = rowMarkup.indexOf('class="value-display"') !== -1;
          var input = __createElement(row.id + '-input', 'input');
          input.value = row.textboxValue;
          row.appendChild(input);
          __elements[row.id] = row;
          __elements[input.id] = input;
          element.appendChild(row);
        }
      }
    }
  });
  return element;
}

function __registerElement(id, tagName) {
  __elements[id] = __createElement(id, tagName);
  return __elements[id];
}

var document = {
  addEventListener: function(type, handler) {
    __documentListeners[type] = handler;
  },
  getElementById: function(id) {
    if (!__elements[id]) {
      __elements[id] = __createElement(id, 'div');
    }
    return __elements[id];
  },
  removeEventListener: function(type, handler) {
    if (__documentListeners[type] === handler) {
      delete __documentListeners[type];
    }
  },
  createElement: function(tagName) {
    return __createElement('', tagName);
  },
  querySelector: function(selector) {
    if (selector === '#variable-form button') {
      return __elements['variable-submit-button'];
    }
    var matches = this.querySelectorAll(selector);
    return matches.length ? matches[0] : null;
  },
  querySelectorAll: function(selector) {
    var matches = [];
    for (var key in __elements) {
      if (__matchesSelector(__elements[key], selector)) {
        matches.push(__elements[key]);
      }
    }
    return matches;
  }
};

function fetch(url, options) {
  __fetchCounts[url] = (__fetchCounts[url] || 0) + 1;
   if (options && options.body) {
    __lastRequests[url] = JSON.parse(options.body);
   }
  var queue = __fetchQueue[url] || [];
  if (!queue.length) {
    throw new Error('Missing fetch response for ' + url);
  }
  var payload = queue.shift();
  return Promise.resolve({
    ok: payload.ok !== false,
    json: function() {
      return Promise.resolve(payload.body);
    },
    text: function() {
      return Promise.resolve(payload.body);
    }
  });
}

function __setFetchResponses(url, responses) {
  __fetchQueue[url] = responses.slice();
}

function __setViewportSize(width, height) {
  __viewportSize.width = width;
  __viewportSize.height = height;
  __elements['svg-viewport'].clientWidth = width;
  __elements['svg-viewport'].clientHeight = height;
}

function __setViewportPadding(x, y) {
  __viewportPadding.x = x;
  __viewportPadding.y = y;
}

function getComputedStyle(element) {
  if (element && element.id === 'svg-viewport') {
    return {
      paddingLeft: String(__viewportPadding.x) + 'px',
      paddingRight: String(__viewportPadding.x) + 'px',
      paddingTop: String(__viewportPadding.y) + 'px',
      paddingBottom: String(__viewportPadding.y) + 'px',
    };
  }
  return {
    paddingLeft: '0px',
    paddingRight: '0px',
    paddingTop: '0px',
    paddingBottom: '0px',
  };
}

function __click(id) {
  var element = __elements[id];
  if (!element) {
    throw new Error('Missing element ' + id);
  }
  if (!element.__listeners.click) {
    throw new Error('Missing click handler for ' + id);
  }
  return element.__listeners.click({ preventDefault: function() {} });
}

function __dragSplitter(startX, moveX, viewportWidth, viewportHeight) {
  var element = __elements['layout-splitter'];
  if (!element.__listeners.mousedown) {
    throw new Error('Missing mousedown handler for layout-splitter');
  }
  element.__listeners.mousedown({ clientX: startX, preventDefault: function() {} });
  if (!__documentListeners.mousemove) {
    throw new Error('Missing mousemove listener for splitter drag');
  }
  if (!__documentListeners.mouseup) {
    throw new Error('Missing mouseup listener for splitter drag');
  }
  if (viewportWidth !== null) {
    __setViewportSize(
      viewportWidth,
      viewportHeight === null ? __viewportSize.height : viewportHeight,
    );
  }
  __documentListeners.mousemove({ clientX: moveX });
  __documentListeners.mouseup({ clientX: moveX });
}

function __submitVariable(variableId, rawValue) {
  var forms = __elements['variable-list'].__children || [];
  for (var i = 0; i < forms.length; i += 1) {
    if (forms[i].dataset.variableId === variableId) {
      forms[i].querySelector('input').value = rawValue;
      forms[i].__listeners.submit({ preventDefault: function() {} });
      return;
    }
  }
  throw new Error('Missing variable row for ' + variableId);
}

function __submitEvent(eventId) {
  var form = __elements['event-form'];
  var select = __elements['event-select'];
  if (!form.__listeners.submit) {
    throw new Error('Missing submit handler for event-form');
  }
  select.value = eventId;
  form.__listeners.submit({ preventDefault: function() {} });
}

function __wheelViewport(deltaY) {
  var element = __elements['svg-viewport'];
  if (!element.__listeners.wheel) {
    throw new Error('Missing wheel handler for svg-viewport');
  }
  var event = {
    deltaY: deltaY,
    defaultPrevented: false,
    preventDefault: function() {
      this.defaultPrevented = true;
    }
  };
  var result = element.__listeners.wheel(event);
  if (!event.defaultPrevented) {
    __elements['workbench-page'].scrollTop += deltaY;
  }
  return result;
}

function __wheelSidebar(deltaY) {
  var element = __elements['sidebar'];
  element.scrollTop += deltaY;
}

function __dragViewport(startX, startY, moveX, moveY) {
  var element = __elements['svg-viewport'];
  if (!element.__listeners.mousedown) {
    throw new Error('Missing mousedown handler for svg-viewport');
  }
  element.__listeners.mousedown({
    clientX: startX,
    clientY: startY,
    preventDefault: function() {}
  });
  __moveDocumentDrag(moveX, moveY);
  __endDocumentDrag(moveX, moveY);
}

function __startViewportDrag(startX, startY) {
  var element = __elements['svg-viewport'];
  if (!element.__listeners.mousedown) {
    throw new Error('Missing mousedown handler for svg-viewport');
  }
  element.__listeners.mousedown({
    clientX: startX,
    clientY: startY,
    preventDefault: function() {}
  });
}

function __moveDocumentDrag(moveX, moveY) {
  if (!__documentListeners.mousemove) {
    throw new Error('Missing document mousemove listener for viewport drag');
  }
  if ((__elements['workbench-page'].__classes || []).indexOf('is-pan-active') === -1) {
    __selectionSideEffects = { rangeCount: 1, text: 'svg label' };
  } else {
    __selectionSideEffects = { rangeCount: 0, text: '' };
  }
  __documentListeners.mousemove({
    clientX: moveX,
    clientY: moveY,
    preventDefault: function() {}
  });
}

function __endDocumentDrag(endX, endY) {
  if (!__documentListeners.mouseup) {
    throw new Error('Missing document mouseup listener for viewport drag');
  }
  __documentListeners.mouseup({
    clientX: endX,
    clientY: endY,
    preventDefault: function() {}
  });
  if ((__elements['workbench-page'].__classes || []).indexOf('is-pan-active') !== -1) {
    __selectionSideEffects = { rangeCount: 0, text: '' };
  }
}

function __snapshot() {
  var stateHighlightIds = [];
  var transitionHighlightIds = [];
  var textHighlightIds = [];
  for (var key in __elements) {
    var element = __elements[key];
    if (element.__classes.indexOf('is-active-state') !== -1) {
      stateHighlightIds.push(element.id);
    }
    if (element.__classes.indexOf('is-active-transition') !== -1) {
      transitionHighlightIds.push(element.id);
    }
    if (element.__classes.indexOf('is-active-text') !== -1) {
      textHighlightIds.push(element.id);
    }
  }
  stateHighlightIds.sort();
  transitionHighlightIds.sort();
  textHighlightIds.sort();
  var variableRows = (__elements['variable-list'].__children || []).map(function(row) {
    return {
      variable_id: row.dataset.variableId,
      textbox_value: row.textboxValue,
      inline_unset_text: row.inlineUnsetText,
      has_value_display: row.hasValueDisplay === true,
      unset: row.inlineUnsetText.length > 0,
    };
  });
  var stageWidth = Number((__elements['svg-stage'].style.width || '0px').replace('px', ''));
  var stageHeight = Number((__elements['svg-stage'].style.height || '0px').replace('px', ''));
  var viewportContentWidth = Math.max(0, (__elements['svg-viewport'].clientWidth || 0) - (__viewportPadding.x * 2));
  var viewportContentHeight = Math.max(0, (__elements['svg-viewport'].clientHeight || 0) - (__viewportPadding.y * 2));
  return JSON.stringify({
    compact_variable_rows: variableRows.length > 0 && (__elements['variable-list'].__children || []).every(function(item) {
      return item.compactLayout === true;
    }),
    state_highlight_ids: stateHighlightIds,
    state_highlight_groups: __highlightGroupsFor('is-active-state'),
    transition_highlight_ids: transitionHighlightIds,
    transition_highlight_groups: __highlightGroupsFor('is-active-transition'),
    text_highlight_ids: textHighlightIds,
    text_highlight_groups: __highlightGroupsFor('is-active-text'),
    variable_rows: variableRows,
    zoom_transform: __elements['svg-root'].style.transform || __elements['svg-stage'].style.transform || '',
    sidebar_width_px: Number((__elements['layout'].style['--sidebar-width'] || '288px').replace('px', '')),
    fit_baseline: __getViewerState().fitBaseline ? {
      zoom_scale: __getViewerState().fitBaseline.zoomScale,
      scroll_left: __getViewerState().fitBaseline.scrollLeft,
      scroll_top: __getViewerState().fitBaseline.scrollTop,
    } : null,
    is_pan_active: __getViewerState().isDragging === true,
    selection_guard_active: (__elements['workbench-page'].__classes || []).indexOf('is-pan-active') !== -1,
    selection_side_effects: {
      range_count: __selectionSideEffects.rangeCount,
      text: __selectionSideEffects.text,
    },
    document_listener_types: Object.keys(__documentListeners).sort(),
    page_scroll_top: __elements['workbench-page'].scrollTop || 0,
    sidebar_scroll_top: __elements['sidebar'].scrollTop || 0,
    viewport_scroll_left: __elements['svg-viewport'].scrollLeft || 0,
    viewport_scroll_top: __elements['svg-viewport'].scrollTop || 0,
    viewport_size: {
      width: __elements['svg-viewport'].clientWidth || 0,
      height: __elements['svg-viewport'].clientHeight || 0,
    },
    viewport_content_size: {
      width: viewportContentWidth,
      height: viewportContentHeight,
    },
    stage_size: {
      width: stageWidth,
      height: stageHeight,
      scaled_width: Number(__elements['svg-stage'].dataset.scaledWidth || 0),
      scaled_height: Number(__elements['svg-stage'].dataset.scaledHeight || 0),
    },
    viewport_has_overflow: {
      x: stageWidth > viewportContentWidth,
      y: stageHeight > viewportContentHeight,
    },
    fetch_counts: {
      '/api/session.json': __fetchCounts['/api/session.json'] || 0,
      '/artifacts/diagram.svg': __fetchCounts['/artifacts/diagram.svg'] || 0,
      '/api/runtime/reset': __fetchCounts['/api/runtime/reset'] || 0,
      '/api/runtime/events': __fetchCounts['/api/runtime/events'] || 0,
      '/api/runtime/variables': __fetchCounts['/api/runtime/variables'] || 0,
    },
    last_requests: {
      '/api/runtime/variables': __lastRequests['/api/runtime/variables'] || null,
      '/api/runtime/events': __lastRequests['/api/runtime/events'] || null,
      '/api/runtime/reset': __lastRequests['/api/runtime/reset'] || null,
    },
  });
}

function __getViewerState() {
  return viewerState;
}

var __layout = __registerElement('layout', 'main');
var __body = __registerElement('workbench-page', 'body');
var __sidebar = __registerElement('sidebar', 'aside');
var __stateSummary = __registerElement('state-summary', 'div');
var __variableList = __registerElement('variable-list', 'div');
var __resetForm = __registerElement('reset-form', 'form');
var __resetViewButton = __registerElement('reset-view-button', 'button');
var __resetButton = __registerElement('reset-submit-button', 'button');
var __eventForm = __registerElement('event-form', 'form');
var __eventSelect = __registerElement('event-select', 'select');
var __eventButton = __registerElement('event-submit-button', 'button');
var __snapshotResult = __registerElement('snapshot-result', 'pre');
var __layoutSplitter = __registerElement('layout-splitter', 'div');
var __svgViewport = __registerElement('svg-viewport', 'div');
var __svgRoot = __registerElement('svg-root', 'div');
var __svgStage = __registerElement('svg-stage', 'div');

__svgViewport.clientWidth = __viewportSize.width;
__svgViewport.clientHeight = __viewportSize.height;
__body.__classes = ['workbench-page'];
__body.className = 'workbench-page';
document.body = __body;
__layout.appendChild(__sidebar);
__body.appendChild(__layout);
__sidebar.appendChild(__stateSummary);
__sidebar.appendChild(__variableList);
__sidebar.appendChild(__resetForm);
__resetForm.appendChild(__resetButton);
__sidebar.appendChild(__resetViewButton);
__sidebar.appendChild(__eventForm);
__eventForm.appendChild(__eventSelect);
__eventForm.appendChild(__eventButton);
__sidebar.appendChild(__snapshotResult);
__layout.appendChild(__layoutSplitter);
__svgViewport.appendChild(__svgStage);
__svgStage.appendChild(__svgRoot);
'''
