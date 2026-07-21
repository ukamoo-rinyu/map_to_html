/* Shared helpers for turning style.json (spec 4.2) into Leaflet
   markers/labels. Used by layer-control.js for every configured layer
   (point/line/polygon) - there's no longer a specially-designated
   "sites" layer, so all styling flows through this one path. */

/* Markers currently on the map with a permanent label bound, in
   registration order - label-declutter.js walks this to hide
   overlapping labels once the map gets dense. Declared here (not in
   label-declutter.js) so bindStyledLabel can push into it regardless
   of module load order within the bundled <script>. */
var FAG_LABEL_REGISTRY = [];

// A raw QGIS marker size (often ~8px diameter) is fine to look at but
// too small to reliably tap on a phone. Verified via profiling (real
// ~570-feature dataset, canvas renderer + zoomAnimation:false already
// in place) that a second invisible larger circleMarker per point -
// previously blamed for making pan/zoom sluggish - is NOT measurably
// slower now that the actual bottleneck (animated multi-level zoom)
// is fixed: steady-state zooms stayed 70-130ms with double the marker
// count (1103->2115 map layers). Reintroduced on that basis.
var FAG_TOUCH_HIT_PADDING = 10;
var FAG_MIN_HIT_RADIUS = 14;

function createStyledMarker(latlng, style, interactive) {
  // QGIS's marker `size` is the full diameter/width, not a radius -
  // L.circleMarker's `radius` option needs half that, or every marker
  // rendered ~2x too large (spec feedback: markers looked oversized).
  var size = style.size || 8;
  var color = style.color || '#4a4a4a';
  var opacity = (style.opacity === undefined || style.opacity === null) ? 1 : style.opacity;
  var strokeColor = style.strokeColor || color;
  var strokeWidth = (style.strokeWidth === undefined || style.strokeWidth === null) ? 1 : style.strokeWidth;
  interactive = interactive !== false;

  if (!style.shape || style.shape === 'circle') {
    var radius = size / 2;
    var visual = L.circleMarker(latlng, {
      radius: radius, color: strokeColor, weight: strokeWidth,
      fillColor: color, fillOpacity: opacity, opacity: opacity, interactive: false,
    });
    var hitRadius = Math.max(radius + FAG_TOUCH_HIT_PADDING, FAG_MIN_HIT_RADIUS);
    // データ設定 tab's per-layer "ポップアップ表示" checkbox, unchecked -
    // the hit target itself must also be non-interactive, or it still
    // steals clicks/hover from whatever's underneath even with no
    // popup/highlight ever bound to it (see buildStyledLayer).
    var hit = L.circleMarker(latlng, { radius: hitRadius, stroke: false, fillOpacity: 0.001, interactive: interactive });
    // Returned as a group so both layers add/remove together; callers
    // use .fagInteractive (events) / .fagVisual (what setStyle/getElement
    // should act on) instead of the group itself.
    var group = L.layerGroup([visual, hit]);
    group.fagInteractive = hit;
    group.fagVisual = visual;
    return group;
  }

  // Every non-circle shape (square/diamond/triangle/star/cross) is a
  // plain colored span whose outline comes from its CSS class's
  // clip-path/transform - so the QGIS symbol's fill color applies
  // uniformly via background (the triangle previously used the CSS
  // border trick, which hardcoded its color and ignored this).
  var shapeClass = 'fag-shape-' + style.shape;
  var html = '<span class="' + shapeClass + '" style="width:' + size + 'px;height:' + size +
    'px;background:' + color + ';opacity:' + opacity + '"></span>';
  var icon = L.divIcon({
    className: 'fag-marker-icon',
    html: html,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
  return L.marker(latlng, { icon: icon, interactive: interactive });
}

/* Binds a permanent tooltip showing `label_text` (spec 4.2.1.1),
   styled to match the QGIS label format (font/size/color/buffer).
   Always anchored 'top' - label-declutter.js handles moving a
   colliding label elsewhere itself, via a plain margin offset on the
   same element rather than rebinding this tooltip in a different
   Leaflet `direction` (an earlier version did that and it was
   measurably too expensive at this app's real dataset scale - see
   label-declutter.js's fagNudgeLabelElement). */
function bindStyledLabel(marker, labelText, markerStyle, labelStyle) {
  if (!labelText) return;
  var radius = (markerStyle.size || 8) / 2;
  marker.bindTooltip(String(labelText), {
    permanent: true,
    direction: 'top',
    className: 'fag-label',
    offset: [0, -(radius + 4)],
  });
  applyLabelTextStyle(marker, labelStyle);
  FAG_LABEL_REGISTRY.push(marker);
}

function applyLabelTextStyle(marker, labelStyle) {
  if (!labelStyle) return;
  marker.on('tooltipopen', function (e) {
    var el = e.tooltip.getElement();
    if (!el) return;
    el.style.fontFamily = labelStyle.fontFamily || '';
    el.style.fontSize = (labelStyle.fontSize || 12) + 'px';
    el.style.color = labelStyle.color || '#333333';
    el.style.fontWeight = labelStyle.bold ? '700' : '400';
    if (labelStyle.buffer) {
      var w = labelStyle.buffer.width || 0;
      var c = labelStyle.buffer.color || '#ffffff';
      el.style.textShadow = buildHaloShadow(w, c);
    }
  });
}

/* Tracks whichever single feature is currently hover-highlighted, so a
   new mouseover can force-clear the previous one even if its own
   mouseout never fired. Adjacent/overlapping shapes (or a marker's own
   label tooltip sitting on top of it) don't always deliver a clean
   mouseout before the next mouseover - previously that left a feature
   permanently bold ("太いままになる" - spec feedback) since nothing else
   ever told it to reset. initLayerControl also wires the map's own
   mouseout to this, so moving the pointer off the map entirely clears
   it too. */
var FAG_ACTIVE_HOVER = null;

function fagResetActiveHover() {
  if (FAG_ACTIVE_HOVER && FAG_ACTIVE_HOVER.reset) FAG_ACTIVE_HOVER.reset();
}

/* Momentarily emphasizes a feature on mouseover so it's clear which
   one the cursor is over in dense areas (spec feedback: qgis2web-style
   hover highlight). `interactiveLayer` is what mouseover/mouseout are
   bound to (usually the same as `visualLayer`, but point markers use a
   separate larger invisible hit target for touch - see
   createStyledMarker); `visualLayer` is what actually gets restyled/
   scaled. L.Path-based visuals (circleMarker/polyline/polygon) get a
   stronger stroke/fill via setStyle; plain L.Marker (divIcon shapes)
   don't support setStyle, so those get a CSS class toggled on their
   icon element instead (see .fag-marker-hover). Pass a falsy
   popupTrigger check at the call site to skip binding this entirely
   (表示設定 tab's "ホバー効果なし" option). */
function bindHoverHighlight(interactiveLayer, visualLayer) {
  var target = visualLayer || interactiveLayer;
  if (target.setStyle) {
    // Snapshot the true baseline once, up front - NOT inside the
    // mouseover handler - so repeated mouseovers always compute from
    // the same fixed values instead of ratcheting darker each time.
    var original = { weight: target.options.weight, fillOpacity: target.options.fillOpacity };
    var reset = function () {
      target.setStyle(original);
      if (FAG_ACTIVE_HOVER && FAG_ACTIVE_HOVER.reset === reset) FAG_ACTIVE_HOVER = null;
    };
    interactiveLayer.on('mouseover', function () {
      fagResetActiveHover();
      target.setStyle({
        weight: (original.weight || 1) + 2,
        fillOpacity: Math.min(1, (original.fillOpacity || 0) + 0.15),
      });
      if (target.bringToFront) target.bringToFront();
      FAG_ACTIVE_HOVER = { reset: reset };
    });
    interactiveLayer.on('mouseout', reset);
  } else if (target.getElement) {
    var resetEl = function () {
      var el = target.getElement();
      if (el) el.classList.remove('fag-marker-hover');
      if (FAG_ACTIVE_HOVER && FAG_ACTIVE_HOVER.reset === resetEl) FAG_ACTIVE_HOVER = null;
    };
    interactiveLayer.on('mouseover', function () {
      fagResetActiveHover();
      var el = target.getElement();
      if (el) el.classList.add('fag-marker-hover');
      FAG_ACTIVE_HOVER = { reset: resetEl };
    });
    interactiveLayer.on('mouseout', resetEl);
  }
}

/* Generic "show every attribute" popup - there's no curated field
   mapping in this round (spec's per-layer field mapping is deferred
   until cross-layer search is designed). Which attributes actually
   reach this function is controlled from the plugin's own per-layer
   field picker (ui/field_dialog.py, Tab 1's ポップアップ項目 設定…
   button): unchecked fields never get written to the GeoJSON in the
   first place (geojson_writer.py's hidden_fields), so they can't show
   up here. 'label_text' and '_fid' are the plugin's own synthetic
   attributes, not real QGIS data, so they're always excluded
   regardless of that picker. Returns '' (not an empty wrapper div)
   when there's nothing to show, so callers (layer-control.js's
   bindPopupIfAny) can skip binding a popup at all instead of opening
   an empty box on click. */
function buildGenericPopupHtml(props) {
  if (!props) return '';
  var rows = Object.keys(props)
    .filter(function (key) {
      return key !== 'label_text' && key !== '_fid' &&
        props[key] !== null && props[key] !== undefined && props[key] !== '';
    })
    .map(function (key) {
      return '<div class="fag-popup-row"><span class="fag-popup-label">' + escapeHtml(key) +
        '</span><span class="fag-popup-value">' + escapeHtml(String(props[key])) + '</span></div>';
    }).join('');
  if (!rows) return '';
  return '<div class="fag-popup">' + rows + '</div>';
}

/* Approximates a true text-stroke halo with layered text-shadows: 12
   directions around the circle, each at radius w plus a couple of
   tighter inner rings, so the result reads as a soft round outline
   instead of the blocky diamond four corner-shadows produce. */
function buildHaloShadow(w, color) {
  if (!w) return 'none';
  var shadows = [];
  var rings = w <= 1.5 ? [w] : [w, w * 0.6];
  var steps = 12;
  rings.forEach(function (r) {
    for (var i = 0; i < steps; i++) {
      var angle = (Math.PI * 2 * i) / steps;
      var dx = (r * Math.cos(angle)).toFixed(2);
      var dy = (r * Math.sin(angle)).toFixed(2);
      shadows.push(dx + 'px ' + dy + 'px 0 ' + color);
    }
  });
  return shadows.join(',');
}

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
  });
}
