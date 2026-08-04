/* Shared helpers for turning style.json (spec 4.2) into Leaflet
   markers/labels. Used by layer-control.js for every configured layer
   (point/line/polygon) - there's no longer a specially-designated
   "sites" layer, so all styling flows through this one path. */

/* Every labeled marker, in registration order - label-layer.js walks
   this on each view change to place and draw the visible labels onto
   its shared canvas. Entries are {marker, text, labelStyle, anchorGap}
   plus a lazily-cached `metrics` (see measureLabelText). Declared here
   (not in label-layer.js) so bindStyledLabel can push into it
   regardless of module load order within the bundled <script>. */
var FAG_LABEL_REGISTRY = [];

/* Paths whose stroke width is a real-world size (QGIS マップ単位/
   メートル(地図単位) line widths - e.g. a road layer whose line width
   IS the road's actual width) rather than a fixed screen px. Leaflet
   only takes px weights, so these get their weight recomputed from
   meters on every zoom change (layer-control.js wires the zoomend
   handler): px = meters / (ground meters per screen pixel at the
   map's center latitude). Entries are {path, meters}. */
var FAG_MAPUNIT_PATHS = [];

// Web-Mercator ground resolution at zoom 0 with 256px tiles:
// earth circumference 40075016.686m / 256px.
var FAG_MERCATOR_M_PER_PX_Z0 = 156543.03392;

/* Screen px covered by `meters` of ground at the map's current zoom and
   center latitude. Shared by the line/outline weights below and by
   label-layer.js's map-unit font sizes. */
function fagMetersToPixels(map, meters) {
  var lat = map.getCenter().lat * Math.PI / 180;
  var metersPerPixel = FAG_MERCATOR_M_PER_PX_Z0 * Math.abs(Math.cos(lat)) /
    Math.pow(2, map.getZoom());
  return meters / metersPerPixel;
}

function fagMapUnitWeight(map, meters) {
  // Floor at a hairline rather than 0 so a zoomed-out road layer stays
  // faintly visible (matching how QGIS still draws sub-pixel-wide map
  // unit lines as thin hairlines instead of dropping them).
  return Math.max(0.5, fagMetersToPixels(map, meters));
}

function fagUpdateMapUnitWeights(map) {
  FAG_MAPUNIT_PATHS.forEach(function (entry) {
    var weight = fagMapUnitWeight(map, entry.meters);
    // bindHoverHighlight reads _fagBaseWeight (when set) instead of its
    // own bind-time snapshot, so hover emphasis and mouseout-reset both
    // track the current zoom's weight instead of a stale one.
    entry.path._fagBaseWeight = weight;
    entry.path.setStyle({ weight: weight });
  });
}

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
  // `opacity` is the FILL opacity (color alpha x symbol opacity x layer
  // opacity, multiplied out in style_extractor.py); the outline carries
  // its own independent `strokeOpacity` from the stroke color's alpha.
  // Treating one value as both is what previously made a marker with a
  // transparent fill also lose its border.
  var opacity = (style.opacity === undefined || style.opacity === null) ? 1 : style.opacity;
  var strokeColor = style.strokeColor || color;
  var strokeOpacity = (style.strokeOpacity === undefined || style.strokeOpacity === null)
    ? 1 : style.strokeOpacity;
  var strokeWidth = (style.strokeWidth === undefined || style.strokeWidth === null) ? 1 : style.strokeWidth;
  interactive = interactive !== false;

  if (!style.shape || style.shape === 'circle') {
    var radius = size / 2;
    var visual = L.circleMarker(latlng, {
      radius: radius, color: strokeColor, weight: strokeWidth,
      fillColor: color, fillOpacity: opacity, opacity: strokeOpacity,
      stroke: strokeWidth > 0 && strokeOpacity > 0,
      fill: opacity > 0, interactive: false,
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
  // colored span clipped/rotated by its CSS class (.fag-shape-<shape>).
  // v0.3.0 task 2-5: QGIS's stroke was never drawn for these shapes at
  // all (only circleMarker's `color`/`weight` options rendered a
  // border) - fixed by stacking two same-shape spans: a full-size one
  // in strokeColor "behind", and a fill-color one inset by strokeWidth
  // on every side "in front", so the strokeColor rim shows as a ring
  // that follows the shape's own outline. They're siblings inside a
  // plain (untransformed) wrapper rather than nested - nesting a
  // shape-classed span (which carries its own `transform: rotate(...)`
  // for diamond) inside another instance of the same class would
  // compound the rotation (e.g. diamond ending up at 90deg instead of
  // 45deg); as siblings, each applies its single rotation independently
  // around the same center point, staying concentric.
  var shapeClass = 'fag-shape-' + style.shape;
  var innerSize = Math.max(size - strokeWidth * 2, 0);
  var innerOffset = (size - innerSize) / 2;
  var fillSpan = '<span class="' + shapeClass + '" style="position:absolute;left:' + innerOffset +
    'px;top:' + innerOffset + 'px;width:' + innerSize + 'px;height:' + innerSize +
    'px;background:' + color + ';opacity:' + opacity + '"></span>';
  var html;
  if (strokeWidth > 0 && strokeOpacity > 0) {
    var strokeSpan = '<span class="' + shapeClass + '" style="position:absolute;left:0;top:0;width:' +
      size + 'px;height:' + size + 'px;background:' + strokeColor + ';opacity:' + strokeOpacity + '"></span>';
    html = '<span style="position:relative;display:block;width:' + size + 'px;height:' + size +
      'px;">' + strokeSpan + fillSpan + '</span>';
  } else {
    html = '<span style="position:relative;display:block;width:' + size + 'px;height:' + size +
      'px;">' + fillSpan + '</span>';
  }
  var icon = L.divIcon({
    className: 'fag-marker-icon',
    html: html,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
  return L.marker(latlng, { icon: icon, interactive: interactive });
}

/* Registers `label_text` (spec 4.2.1.1) for canvas drawing by
   label-layer.js. Labels are NOT Leaflet tooltips: a permanent
   tooltip is a DOM node Leaflet repositions synchronously inside
   every zoom step, which profiled at ~1.0-1.2s per step with 1,530
   labeled points - see label-layer.js for the measurement and the
   canvas approach that replaced it. anchorGap mirrors the old
   tooltip offset (label bottom sits that many px above the marker
   center). */
function bindStyledLabel(marker, labelText, markerStyle, labelStyle) {
  if (!labelText) return;
  var radius = (markerStyle.size || 8) / 2;
  FAG_LABEL_REGISTRY.push({
    marker: marker,
    text: String(labelText),
    labelStyle: labelStyle,
    anchorGap: radius + 4,
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
    // Map-unit paths are the one exception: their true base weight
    // changes on every zoom (fagUpdateMapUnitWeights stamps it onto
    // _fagBaseWeight), so a fixed snapshot would restore a stale
    // zoom's width on mouseout - read the stamp when present.
    var original = { weight: target.options.weight, fillOpacity: target.options.fillOpacity };
    var baseWeight = function () {
      return target._fagBaseWeight !== undefined ? target._fagBaseWeight : original.weight;
    };
    var reset = function () {
      target.setStyle({ weight: baseWeight(), fillOpacity: original.fillOpacity });
      if (FAG_ACTIVE_HOVER && FAG_ACTIVE_HOVER.reset === reset) FAG_ACTIVE_HOVER = null;
    };
    interactiveLayer.on('mouseover', function () {
      fagResetActiveHover();
      target.setStyle({
        weight: (baseWeight() || 1) + 2,
        fillOpacity: Math.min(1, (original.fillOpacity || 0) + 0.15),
      });
      // Deliberately NOT calling target.bringToFront() here (removed
      // v0.3.0): Canvas's hit-testing for BOTH click and hover walks
      // the shared _drawFirst/.next paint-order list and picks the
      // LAST match (verified by reading L.Canvas.prototype._onClick/
      // _handleMouseHover directly) - the SAME list layer-control.js's
      // bringLayerToFront() sets up once at load to make front-
      // configured layers win over back layers. bringToFront() here
      // moved just the single hovered feature to the very end of that
      // list, which doesn't get undone on mouseout - so hovering a
      // supposedly-BACK polygon even once permanently jumped it ahead
      // of every front-configured point sharing that location for the
      // rest of the page's life (spec feedback: a background polygon
      // "won" the hover highlight over a point after being hovered).
      // The stronger stroke/fill above is enough to read as "this is
      // the hovered feature" without needing to fight z-order for it.
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
var FAG_IMAGE_EXT_RE = /\.(png|jpe?g|gif|webp|svg|bmp)(\?|#|$)/i;

/* One attribute value, rendered. An http(s) value becomes a link (and
   an image URL an inline thumbnail) when the plugin enabled that -
   only ever http/https, so a `javascript:` or `data:` value in the
   source data can't become a clickable link. Everything else is
   escaped text. */
function buildPopupValueHtml(value, ctx) {
  var text = String(value);
  if (ctx && ctx.linkifyUrls && /^https?:\/\//i.test(text)) {
    var safe = escapeHtml(text);
    var anchor = '<a href="' + safe + '" target="_blank" rel="noopener noreferrer">';
    if (FAG_IMAGE_EXT_RE.test(text)) {
      return anchor + '<img src="' + safe + '" alt="" loading="lazy"></a>';
    }
    return anchor + safe + '</a>';
  }
  return escapeHtml(text);
}

/* Generic "show every attribute" popup. Which attributes reach this
   function, and in what order, is controlled from the plugin's own
   per-layer field picker (ui/field_dialog.py, Tab 1's ポップアップ項目
   設定… button): unchecked fields never get written to the GeoJSON in
   the first place (geojson_writer.py's field_order), so they can't
   show up here. 'label_text' and '_fid' are the plugin's own synthetic
   attributes, not real QGIS data, so they're always excluded
   regardless of that picker.

   `ctx` (built once per layer by layer-control.js) carries the field
   aliases, whether empty values are shown, and the Google/GSI link
   settings. Field labels use QGIS's field ALIAS when the layer defines
   one - that's the root fix for "列名が長いとレイアウトが崩れる", since
   an alias is usually the short human name ("R3_SISETU_MEI" ->
   "施設名").

   Returns '' (not an empty wrapper div) when there's nothing to show,
   so callers (layer-control.js's bindPopupIfAny) can skip binding a
   popup at all instead of opening an empty box on click. */
function buildGenericPopupHtml(props, ctx, latlng) {
  if (!props) return '';
  ctx = ctx || {};
  var aliases = ctx.aliases || {};
  var rows = Object.keys(props)
    .filter(function (key) {
      if (key === 'label_text' || key === '_fid') return false;
      if (ctx.showEmpty) return true;
      var value = props[key];
      return value !== null && value !== undefined && value !== '';
    })
    .map(function (key) {
      var value = props[key];
      if (value === null || value === undefined) value = '';
      return '<div class="fag-popup-row"><span class="fag-popup-label">' +
        escapeHtml(aliases[key] || key) + '</span><span class="fag-popup-value">' +
        buildPopupValueHtml(value, ctx) + '</span></div>';
    }).join('');
  var links = buildPopupLinksHtml(props, latlng, ctx);
  if (!rows && !links) return '';
  return '<div class="fag-popup">' + rows + links + '</div>';
}

/* A representative lat/lng for any geometry, for the map links below.
   Points use their own coordinate; lines/polygons use the mean of
   their vertices (the spec's "頂点座標の平均で実用上十分" - no turf or
   other geometry library needed). A polygon whose vertex mean lands
   outside the shape (a C/crescent outline) would be better served by
   the bounds center, but that's just as wrong for a long diagonal
   line, and the vertex mean is the better default of the two for the
   boundary/zone shapes this actually gets used on. */
function fagFeatureLatLng(layer) {
  if (!layer) return null;
  if (layer.getLatLng) return layer.getLatLng();
  var latlngs = layer.getLatLngs ? layer.getLatLngs() : null;
  if (latlngs) {
    var sumLat = 0;
    var sumLng = 0;
    var count = 0;
    (function walk(list) {
      for (var i = 0; i < list.length; i++) {
        if (Array.isArray(list[i])) walk(list[i]);
        else if (list[i] && list[i].lat !== undefined) {
          sumLat += list[i].lat; sumLng += list[i].lng; count++;
        }
      }
    })(latlngs);
    if (count) return L.latLng(sumLat / count, sumLng / count);
  }
  if (layer.getBounds) {
    try { return layer.getBounds().getCenter(); } catch (e) { /* empty geometry */ }
  }
  return null;
}

/* External map links at the foot of the popup (spec item 11). Every
   entry is opt-in from the plugin's 表示設定 tab, and when the parent
   switch is off this returns '' so no link markup reaches the output
   at all - not hidden-by-CSS links still sitting in the DOM.
   Coordinates are rounded to 6 decimals (~11cm), matching the
   coordinate precision the GeoJSON itself is written at. */
function buildPopupLinksHtml(props, latlng, ctx) {
  var links = ctx && ctx.links;
  if (!links || !latlng) return '';
  var lat = latlng.lat.toFixed(6);
  var lng = latlng.lng.toFixed(6);
  var query = lat + ',' + lng;
  var parts = [];

  function add(url, icon, label) {
    parts.push('<a href="' + escapeHtml(url) + '" target="_blank" rel="noopener noreferrer"' +
      ' title="' + escapeHtml(label) + '">' + icon +
      '<span class="fag-popup-link-label">' + escapeHtml(label) + '</span></a>');
  }

  if (links.googleMaps) {
    add('https://www.google.com/maps/search/?api=1&query=' + query, '🗺', 'Googleマップ');
  }
  if (links.streetView) {
    add('https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=' + query, '📷', 'ストリートビュー');
  }
  if (links.directions) {
    add('https://www.google.com/maps/dir/?api=1&destination=' + query, '🚗', 'ここへの経路');
  }
  if (links.nameSearch && links.nameField) {
    var name = props ? props[links.nameField] : null;
    if (name !== null && name !== undefined && name !== '') {
      // encodeURIComponent, not just HTML-escaping: a facility name with
      // a space, "&" or Japanese text would otherwise truncate or break
      // the query string.
      add('https://www.google.com/search?q=' + encodeURIComponent(String(name)), '🔍', '名称で検索');
    }
  }
  if (links.gsi) {
    add('https://maps.gsi.go.jp/#17/' + lat + '/' + lng + '/', '🗾', '地理院地図');
  }

  if (!parts.length) return '';
  return '<div class="fag-popup-links">' + parts.join('') + '</div>';
}

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
  });
}
