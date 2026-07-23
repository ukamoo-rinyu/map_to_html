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
   FAG_LABEL_PLACEMENTS ({marker, rect} in container-pixel coords) so
   a later feature can hit-test label clicks (e.g. open the marker's
   popup when its label text is clicked). */

/* Fraction of a label's width/height trimmed from EACH side of its box
   before collision testing - bigger values let labels overlap more
   before one is hidden (0 restores strict non-overlap). */
var FAG_LABEL_COLLISION_INSET_X = 0.2;
var FAG_LABEL_COLLISION_INSET_Y = 0.25;

var FAG_LABEL_PLACEMENTS = [];

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

  var placements = computeLabelPlacements(map, size);
  FAG_LABEL_PLACEMENTS = placements;

  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  ctx.lineJoin = 'round';
  placements.forEach(function (p) {
    var m = p.entry.metrics;
    var labelStyle = p.entry.labelStyle || {};
    ctx.font = m.font;
    var cx = p.rect.left + m.width / 2;
    for (var i = 0; i < m.lines.length; i++) {
      var y = p.rect.top + i * m.lineHeight;
      if (labelStyle.buffer && labelStyle.buffer.width) {
        ctx.strokeStyle = labelStyle.buffer.color || '#ffffff';
        ctx.lineWidth = labelStyle.buffer.width * 2;
        ctx.strokeText(m.lines[i], cx, y);
      }
      ctx.fillStyle = labelStyle.color || '#333333';
      ctx.fillText(m.lines[i], cx, y);
    }
  });
}

function computeLabelPlacements(map, size) {
  var kept = [];
  var keptTestRects = [];
  // Slight bounds padding so a label whose text sticks into the view
  // from a just-offscreen marker still gets drawn.
  var viewBounds = map.getBounds().pad(0.1);

  FAG_LABEL_REGISTRY.forEach(function (entry) {
    var marker = entry.marker;
    if (!marker._map) return; // layer currently toggled off
    var latlng = marker.getLatLng();
    if (!viewBounds.contains(latlng)) return;

    var m = entry.metrics || (entry.metrics = measureLabelText(entry));
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

    for (var i = 0; i < candidates.length; i++) {
      var off = candidates[i];
      var rect = {
        left: baseLeft + off.dx, right: baseLeft + m.width + off.dx,
        top: baseTop + off.dy, bottom: baseTop + m.height + off.dy,
      };

      if (rect.right < 0 || rect.left > size.x || rect.bottom < 0 || rect.top > size.y) continue;

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
        break;
      }
    }
  });

  return kept;
}

/* Measures the label's text block once per label (font/text never
   change after load, so the result is cached on the registry entry by
   the caller). Shares one detached canvas context - measureText does
   no DOM layout, unlike the getBoundingClientRect calls the old
   tooltip version needed. */
var FAG_MEASURE_CTX = null;

function measureLabelText(entry) {
  if (!FAG_MEASURE_CTX) {
    FAG_MEASURE_CTX = document.createElement('canvas').getContext('2d');
  }
  var labelStyle = entry.labelStyle || {};
  var fontSize = labelStyle.fontSize || 12;
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
