/* Canvas-based label layer (v0.3.0 task 1-1/1-2, replaces the old
   label-declutter.js DOM-tooltip approach).

   Why not permanent Leaflet tooltips: every permanent tooltip is its
   own DOM node that Leaflet repositions synchronously inside setZoom.
   Profiled against a synthetic 1,530-point dataset that made every
   single zoom step block for ~1.0-1.2 *seconds*; unbinding all
   tooltips dropped the same steps to 10-40ms. So at the 1,000+ point
   scale this app targets, labels can't live in the DOM at all - this
   draws every visible label onto ONE <canvas> in a dedicated map pane
   instead, and a full redraw (placement + text with halo) costs a few
   ms because text metrics come from ctx.measureText (pure math, no
   layout) and are cached per label.

   Collision handling (task 1-2 - show labels earlier when zoomed out):
   labels are placed greedily in registration order, but the collision
   test uses each label's box shrunk toward its own center
   (FAG_LABEL_COLLISION_INSET_X/Y), so two labels may partially overlap
   before one gets hidden. The spec explicitly prefers "visible early,
   somewhat overlapping" over strict collision avoidance. Hidden labels
   aren't gone - the pass reruns on every view change, so they appear
   as soon as zooming in gives them room.

   Markers flagged `fagLabelMultiDirection` (exact-duplicate-coordinate
   points spread apart by layer-control.js) additionally try
   right/left/below placements before giving up, reusing the same
   cached text metrics - no extra measurement per direction.

   Placements kept by the latest pass are published in
   FAG_LABEL_PLACEMENTS ({entry, marker, rect} - rect in container-
   pixel coords) so initLabelClickPopup below can hit-test clicks
   against them and open the right marker's popup (task 2-1). */

/* Fraction of a label's width/height trimmed from EACH side of its box
   before collision testing - bigger values let labels overlap more
   before one is hidden (0 restores strict non-overlap). */
var FAG_LABEL_COLLISION_INSET_X = 0.2;
var FAG_LABEL_COLLISION_INSET_Y = 0.25;

var FAG_LABEL_PLACEMENTS = [];

// v0.3.0 UX request: an on/off button on the map itself for all
// labels at once (independent of the per-layer checkboxes in
// #layer-panel, which only ever hide/show a layer's markers - the
// label canvas is shared across every layer, so this is a single flag
// rather than something layer-control.js could toggle per layer).
var FAG_LABELS_ENABLED = true;

/* Map-unit label sizes (QGIS マップ単位/メートル(地図単位) font size -
   the label is meant to cover a real-world size, e.g. text sized to
   the building it names, so it grows and shrinks with the zoom instead
   of staying a constant screen size). style_extractor exports those as
   `fontSizeMeters` / `buffer.widthMeters`; everything else keeps the
   fixed px `fontSize` / `buffer.width`.

   The px floor keeps a zoomed-out label readable rather than letting it
   collapse into an illegible smudge (the equivalent of the 0.5px
   hairline floor map-unit line weights use); the ceiling only guards
   against a single label swallowing the viewport when zoomed far in. */
var FAG_LABEL_MIN_PX = 6;
var FAG_LABEL_MAX_PX = 200;

function fagLabelFontSize(map, labelStyle) {
  if (labelStyle && labelStyle.fontSizeMeters) {
    var px = fagMetersToPixels(map, labelStyle.fontSizeMeters);
    // Rounded so panning/zoom jitter can't invalidate the cached text
    // metrics (see computeLabelPlacements) on every single frame.
    return Math.round(Math.max(FAG_LABEL_MIN_PX, Math.min(FAG_LABEL_MAX_PX, px)));
  }
  return (labelStyle && labelStyle.fontSize) || 12;
}

function fagLabelBufferWidth(map, labelStyle) {
  var buffer = labelStyle && labelStyle.buffer;
  if (!buffer) return 0;
  if (buffer.widthMeters) {
    // Same tight cap style_extractor applies to px halos: hundreds of
    // dense labels with big halos merge into one opaque block.
    return Math.min(4, fagMetersToPixels(map, buffer.widthMeters));
  }
  return buffer.width || 0;
}

function initLabelLayer(map) {
  var pane = map.createPane('fag-labels');
  // Above markerPane (600) so labels overlay markers, below popupPane
  // (700) so an open popup still covers nearby labels.
  pane.style.zIndex = 650;
  pane.style.pointerEvents = 'none';

  var canvas = document.createElement('canvas');
  pane.appendChild(canvas);
  var ctx = canvas.getContext('2d');

  var scheduled = false;
  function run() {
    scheduled = false;
    redrawLabels(map, canvas, ctx);
  }
  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(run);
  }
  // layeradd/layerremove fire once per child marker when a whole layer
  // group is toggled - the rAF gate above coalesces that burst into a
  // single redraw.
  map.on('zoomend moveend resize layeradd layerremove', schedule);
  schedule();

  addLabelToggleControl(map, schedule);
}

/* A Leaflet control button (same leaflet-bar look as the zoom
   buttons, so it doesn't need its own bespoke positioning/styling)
   that flips FAG_LABELS_ENABLED and asks for a redraw - `schedule` is
   passed in directly from initLabelLayer's closure rather than
   re-deriving the canvas/ctx here. */
function addLabelToggleControl(map, schedule) {
  var control = L.control({ position: 'topleft' });
  control.onAdd = function () {
    var container = L.DomUtil.create('div', 'leaflet-bar fag-label-toggle');
    var button = L.DomUtil.create('a', '', container);
    button.href = '#';
    button.title = 'Toggle labels';
    button.setAttribute('role', 'button');
    button.setAttribute('aria-label', 'Toggle labels');
    button.textContent = 'Aa';
    L.DomEvent.on(button, 'click', function (e) {
      L.DomEvent.stop(e);
      FAG_LABELS_ENABLED = !FAG_LABELS_ENABLED;
      button.classList.toggle('fag-label-toggle-off', !FAG_LABELS_ENABLED);
      schedule();
    });
    L.DomEvent.disableClickPropagation(container);
    return container;
  };
  control.addTo(map);
}

function redrawLabels(map, canvas, ctx) {
  var size = map.getSize();
  var dpr = window.devicePixelRatio || 1;
  if (canvas.width !== size.x * dpr || canvas.height !== size.y * dpr) {
    canvas.width = size.x * dpr;
    canvas.height = size.y * dpr;
    canvas.style.width = size.x + 'px';
    canvas.style.height = size.y + 'px';
  }
  // The canvas lives in a map pane, which Leaflet translates while
  // panning - pinning it to the viewport's current top-left layer
  // point keeps it covering the screen (same trick Leaflet's own
  // canvas renderer uses); labels drift with the map mid-drag and
  // snap to the refreshed layout on moveend.
  L.DomUtil.setPosition(canvas, map.containerPointToLayerPoint([0, 0]));

  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, size.x, size.y);

  // Labels toggled off: leave the canvas cleared and no placements
  // registered (so a click can't hit a label that isn't drawn - see
  // initLabelClickPopup below) rather than skipping the resize/
  // position update above, which still needs to happen so the canvas
  // is correctly sized/placed the moment labels are turned back on.
  if (!FAG_LABELS_ENABLED) {
    FAG_LABEL_PLACEMENTS = [];
    return;
  }

  var placements = computeLabelPlacements(map, size);
  FAG_LABEL_PLACEMENTS = placements;

  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  ctx.lineJoin = 'round';
  placements.forEach(function (p) {
    var m = p.entry.metrics;
    var labelStyle = p.entry.labelStyle || {};
    var bufferWidth = fagLabelBufferWidth(map, labelStyle);
    ctx.font = m.font;
    var cx = p.rect.left + m.width / 2;
    for (var i = 0; i < m.lines.length; i++) {
      var y = p.rect.top + i * m.lineHeight;
      if (bufferWidth) {
        ctx.strokeStyle = labelStyle.buffer.color || '#ffffff';
        ctx.lineWidth = bufferWidth * 2;
        ctx.strokeText(m.lines[i], cx, y);
      }
      ctx.fillStyle = labelStyle.color || '#333333';
      ctx.fillText(m.lines[i], cx, y);
    }
  });
}

// Past this zoom, every in-view label is drawn even if its box
// overlaps another's (spec feedback: some labels stayed hidden until
// zoomed in almost all the way, which read as "this facility has no
// name" rather than "decluttered"). Fixed at maxZoom-3 rather than a
// hardcoded absolute level so it scales with whatever zoom range this
// particular export actually uses.
function fagLabelForceShowZoom(map) {
  return Math.max(map.getMinZoom(), map.getMaxZoom() - 3);
}

function computeLabelPlacements(map, size) {
  var kept = [];
  var keptTestRects = [];
  var forceAll = map.getZoom() >= fagLabelForceShowZoom(map);
  // Slight bounds padding so a label whose text sticks into the view
  // from a just-offscreen marker still gets drawn.
  var viewBounds = map.getBounds().pad(0.1);

  FAG_LABEL_REGISTRY.forEach(function (entry) {
    var marker = entry.marker;
    if (!marker._map) return; // layer currently toggled off
    var latlng = marker.getLatLng();
    if (!viewBounds.contains(latlng)) return;

    // Fixed-px labels measure once and hit the cache forever after; a
    // map-unit label re-measures only when its rounded px size actually
    // changes (i.e. on a zoom step, not on every pan frame).
    var fontSize = fagLabelFontSize(map, entry.labelStyle);
    var m = entry.metrics;
    if (!m || entry.metricsFontSize !== fontSize) {
      m = entry.metrics = measureLabelText(entry, fontSize);
      entry.metricsFontSize = fontSize;
    }
    if (!m.lines.length) return;

    var pt = map.latLngToContainerPoint(latlng);
    // Default placement: centered above the marker (same anchor the
    // old tooltip version used).
    var baseLeft = pt.x - m.width / 2;
    var baseTop = pt.y - entry.anchorGap - m.height;

    var candidates = [{ dx: 0, dy: 0 }];
    if (marker.fagLabelMultiDirection) {
      var dx = m.width * 0.85 + 6;
      var dy = m.height * 1.3 + 4;
      candidates.push({ dx: dx, dy: 0 }, { dx: -dx, dy: 0 }, { dx: 0, dy: dy });
    }

    var placed = false;
    var fallbackRect = null;
    for (var i = 0; i < candidates.length; i++) {
      var off = candidates[i];
      var rect = {
        left: baseLeft + off.dx, right: baseLeft + m.width + off.dx,
        top: baseTop + off.dy, bottom: baseTop + m.height + off.dy,
      };

      if (rect.right < 0 || rect.left > size.x || rect.bottom < 0 || rect.top > size.y) continue;
      if (!fallbackRect) fallbackRect = rect; // first on-screen candidate, used by forceAll below

      var insetX = m.width * FAG_LABEL_COLLISION_INSET_X;
      var insetY = m.height * FAG_LABEL_COLLISION_INSET_Y;
      var test = {
        left: rect.left + insetX, right: rect.right - insetX,
        top: rect.top + insetY, bottom: rect.bottom - insetY,
      };

      var overlaps = keptTestRects.some(function (other) {
        return !(test.right < other.left || test.left > other.right ||
          test.bottom < other.top || test.top > other.bottom);
      });

      if (!overlaps) {
        kept.push({ entry: entry, marker: marker, rect: rect });
        keptTestRects.push(test);
        placed = true;
        break;
      }
    }
    // Past fagLabelForceShowZoom every in-view label shows regardless of
    // overlap - draw it at its best (first on-screen) candidate rect
    // rather than dropping it just because every candidate collided.
    if (!placed && forceAll && fallbackRect) {
      kept.push({ entry: entry, marker: marker, rect: fallbackRect });
    }
  });

  return kept;
}

/* Measures the label's text block at `fontSize` px. The text never
   changes after load and the size only changes for map-unit labels on
   a zoom step, so the caller caches the result on the registry entry
   alongside the size it was measured at. Shares one detached canvas
   context - measureText does no DOM layout, unlike the
   getBoundingClientRect calls the old tooltip version needed. */
var FAG_MEASURE_CTX = null;

function measureLabelText(entry, fontSize) {
  if (!FAG_MEASURE_CTX) {
    FAG_MEASURE_CTX = document.createElement('canvas').getContext('2d');
  }
  var labelStyle = entry.labelStyle || {};
  fontSize = fontSize || 12;
  var family = labelStyle.fontFamily
    ? '"' + labelStyle.fontFamily + '", "Noto Sans JP", sans-serif'
    : '"Noto Sans JP", sans-serif';
  var font = (labelStyle.bold ? '700 ' : '') + fontSize + 'px ' + family;
  // Explicit \n from QGIS wordwrap()/expressions makes a multi-line
  // label; there's no auto-wrapping (matches the old white-space: pre
  // behavior - CJK text would otherwise wrap at every character).
  var lines = String(entry.text).split('\n').filter(function (line, i, arr) {
    return line !== '' || i < arr.length - 1; // drop a trailing empty line only
  });
  FAG_MEASURE_CTX.font = font;
  var width = 0;
  lines.forEach(function (line) {
    width = Math.max(width, FAG_MEASURE_CTX.measureText(line).width);
  });
  var lineHeight = Math.round(fontSize * 1.2);
  return {
    font: font,
    lines: lines,
    width: Math.ceil(width),
    height: lines.length * lineHeight,
    lineHeight: lineHeight,
  };
}

/* v0.3.0 task 2-1: clicking a label's TEXT (not just the marker under
   it) opens the same popup. The label canvas has pointer-events:none
   (deliberately - see initLabelLayer - so clicks pass through to
   whatever marker/shape sits underneath), so it never receives its
   own click event; instead this hit-tests the map's click point
   against the latest FAG_LABEL_PLACEMENTS.

   Must not steal a popup a directly-clicked feature already opened
   via its own click handler - Leaflet fires a layer's own 'click'
   (and any popup it opens, via bindPopup's internal click listener)
   BEFORE the map's own 'click' listeners run (its simulated event
   bubbling: layer first, then map). So tracking whether 'popupopen'
   already fired earlier in this same click's dispatch is enough to
   tell "the click was actually on a feature" apart from "the click
   only hit a label drawn over empty space" - no marker hit-testing of
   our own is needed for that half of the decision. */
function initLabelClickPopup(map) {
  var popupOpenedThisClick = false;
  map.on('popupopen', function () { popupOpenedThisClick = true; });
  map.on('click', function (e) {
    var openedByFeature = popupOpenedThisClick;
    popupOpenedThisClick = false;
    if (openedByFeature) return;
    var hit = hitTestLabelPlacement(e.containerPoint);
    if (hit && hit.marker.openPopup) hit.marker.openPopup();
  });
}

function hitTestLabelPlacement(containerPoint) {
  for (var i = 0; i < FAG_LABEL_PLACEMENTS.length; i++) {
    var r = FAG_LABEL_PLACEMENTS[i].rect;
    if (containerPoint.x >= r.left && containerPoint.x <= r.right &&
      containerPoint.y >= r.top && containerPoint.y <= r.bottom) {
      return FAG_LABEL_PLACEMENTS[i];
    }
  }
  return null;
}
