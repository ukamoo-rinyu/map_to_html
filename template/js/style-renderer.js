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

function createStyledMarker(latlng, style) {
  // QGIS's marker `size` is the full diameter/width, not a radius -
  // L.circleMarker's `radius` option needs half that, or every marker
  // rendered ~2x too large (spec feedback: markers looked oversized).
  var size = style.size || 8;
  var color = style.color || '#4a4a4a';
  var opacity = (style.opacity === undefined || style.opacity === null) ? 1 : style.opacity;
  var strokeColor = style.strokeColor || color;
  var strokeWidth = (style.strokeWidth === undefined || style.strokeWidth === null) ? 1 : style.strokeWidth;

  if (!style.shape || style.shape === 'circle') {
    return L.circleMarker(latlng, {
      radius: size / 2,
      color: strokeColor,
      weight: strokeWidth,
      fillColor: color,
      fillOpacity: opacity,
      opacity: opacity,
    });
  }

  var shapeClass = 'fag-shape-' + style.shape;
  var html;
  if (style.shape === 'triangle') {
    // CSS triangle trick: size is expressed via border widths, not width/height.
    html = '<span class="' + shapeClass + '" style="opacity:' + opacity + '"></span>';
  } else {
    html = '<span class="' + shapeClass + '" style="width:' + size + 'px;height:' + size +
      'px;background:' + color + ';opacity:' + opacity + '"></span>';
  }
  var icon = L.divIcon({
    className: 'fag-marker-icon',
    html: html,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
  return L.marker(latlng, { icon: icon });
}

/* Binds a permanent tooltip showing `label_text` (spec 4.2.1.1),
   styled to match the QGIS label format (font/size/color/buffer). */
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

/* Momentarily emphasizes a feature on mouseover so it's clear which
   one the cursor is over in dense areas (spec feedback: qgis2web-style
   hover highlight). L.Path-based layers (circleMarker/polyline/
   polygon) get a stronger stroke/fill via setStyle; plain L.Marker
   (divIcon shapes) don't support setStyle, so those get a CSS class
   toggled on their icon element instead (see .fag-marker-hover). */
function bindHoverHighlight(layer) {
  if (layer.setStyle) {
    // Snapshot the true baseline once, up front - NOT inside the
    // mouseover handler. Densely packed/overlapping features (or a
    // marker's own label tooltip sitting right on top of it) can fire
    // mouseover again before mouseout cleanly fires, and re-reading
    // layer.options at that point would capture the already-
    // highlighted values as "original", then boost those further -
    // each missed mouseout ratcheted the fill/weight darker forever.
    // Always computing from/to this fixed snapshot instead means
    // extra mouseovers just reapply the same highlight, never stack.
    var original = { weight: layer.options.weight, fillOpacity: layer.options.fillOpacity };
    layer.on('mouseover', function () {
      layer.setStyle({
        weight: (original.weight || 1) + 2,
        fillOpacity: Math.min(1, (original.fillOpacity || 0) + 0.15),
      });
      if (layer.bringToFront) layer.bringToFront();
    });
    layer.on('mouseout', function () {
      layer.setStyle(original);
    });
  } else if (layer.getElement) {
    layer.on('mouseover', function () {
      var el = layer.getElement();
      if (el) el.classList.add('fag-marker-hover');
    });
    layer.on('mouseout', function () {
      var el = layer.getElement();
      if (el) el.classList.remove('fag-marker-hover');
    });
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
