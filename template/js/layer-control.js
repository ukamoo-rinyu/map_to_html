/* Renders every configured layer (spec 3.1/4.2/4.3) and the toggle
   panel that shows/hides each one - the qgis2web-style "show
   everything, each with its own QGIS symbology" model this round
   settled on. Point layers get styled markers + labels (reusing
   style-renderer.js helpers), line/polygon layers get their
   color/width or fill/stroke. Layers using a QGIS categorized
   renderer (spec 4.2.2) resolve each feature's style from
   styleData.byCategory before falling back to defaultStyle (see
   resolveCategoryStyle/buildStyledLayer below). Every feature gets a
   generic "all attributes" popup since there's no curated field
   mapping yet. */

/* {layerId: {fid: {feature, layer}}} - every feature from every
   geometry layer (marker/line/fill; tile layers have no attributes so
   they're never registered here), keyed by the auto-incrementing
   '_fid' core/geojson_writer.py always writes. search.js (v0.3.0 task
   3-1, cross-layer) and point-list.js (task 3-2, per-layer feature
   table) both use this to go from "a GeoJSON feature the user picked
   in a list/table row" back to the actual Leaflet layer to zoom to
   and open the popup of - `layer` is exactly what bindPopupIfAny
   below bound the popup to, so .openPopup() on it is a safe no-op if
   this layer's ポップアップ表示 is off (same as initLabelClickPopup
   in label-layer.js relies on). */
var FAG_FEATURES_BY_LAYER = {};

function registerFeature(layerId, feature, layer) {
  var fid = feature.properties && feature.properties._fid;
  if (fid === undefined || fid === null) return;
  if (!FAG_FEATURES_BY_LAYER[layerId]) FAG_FEATURES_BY_LAYER[layerId] = {};
  FAG_FEATURES_BY_LAYER[layerId][fid] = { feature: feature, layer: layer };
}

/* Shared by search.js (task 3-1) and point-list.js (task 3-2): zoom to
   and open the popup of one FAG_FEATURES_BY_LAYER entry, regardless of
   geometry type. If the owning layer is currently toggled off in
   #layer-panel (the feature table can list a hidden layer - search
   results can't, they're pre-filtered to visible layers only, so this
   is a no-op for search), checks its checkbox first and dispatches the
   same 'change' event renderLayerTree's own listener reacts to, so the
   layer is actually added to the map before openPopup (which otherwise
   silently no-ops without a map) runs. */
function focusFeature(map, layerId, entry) {
  var checkbox = document.getElementById('layer-toggle-' + layerId);
  if (checkbox && !checkbox.checked) {
    checkbox.checked = true;
    checkbox.dispatchEvent(new Event('change'));
  }
  var layer = entry.layer;
  if (layer.getLatLng) {
    map.setView(layer.getLatLng(), Math.max(map.getZoom(), 16));
  } else if (layer.getBounds) {
    map.fitBounds(layer.getBounds(), { maxZoom: 17 });
  }
  if (layer.openPopup) layer.openPopup();
}

/* Per-layer popup settings, assembled once from the layer's own config
   entry plus the global 表示設定 options, then handed to every feature's
   bindPopupIfAny. Kept out of the per-feature path so the alias table
   and link flags are looked up once per layer, not once per feature. */
function buildPopupContext(layerConfig, display) {
  return {
    aliases: layerConfig.fieldAliases || {},
    showEmpty: display.popupShowEmpty === true,
    linkifyUrls: display.popupLinkifyUrls !== false,
    // Absent (parent checkbox off in the plugin) means no link markup
    // is generated at all - see buildPopupLinksHtml.
    links: display.popupLinks || null,
  };
}

function initLayerControl(map, layersConfig, layersData, layersStyleData, display) {
  if (!layersConfig || !layersConfig.length) return;
  display = display || {};
  var popupTrigger = display.popupTrigger;

  var panel = document.getElementById('layer-panel');
  var listEl = document.getElementById('layer-panel-list');
  panel.classList.remove('fag-hidden');

  // Collapsible panel (spec feedback: on a phone it can cover a large
  // part of the small map) - starts collapsed on narrow screens,
  // expanded on desktop; either way the toggle button always works.
  var toggleBtn = document.getElementById('layer-panel-toggle');
  if (toggleBtn) {
    if (window.innerWidth <= 768) panel.classList.add('fag-collapsed');
    toggleBtn.addEventListener('click', function () {
      panel.classList.toggle('fag-collapsed');
    });
  }

  // Reset any stuck hover highlight when the pointer leaves the map
  // entirely - a fast swipe/drag off the map edge doesn't always
  // deliver a clean mouseout to whatever feature was last hovered.
  map.on('mouseout', fagResetActiveHover);

  // Spread exact-duplicate-coordinate points apart *before* any layer
  // is built - must run across every marker layer together, not one at
  // a time, since two facilities can be split across separate legend
  // layers (e.g. by 活用方針: 事業予定地/処分検討地/継続保有地 filtered
  // from what was one shared dataset) yet still share a coordinate. A
  // per-layer-only pass would never notice that case, leaving both
  // points invisibly stacked with only one label/color winning.
  spreadOverlappingPointsAcrossLayers(layersConfig, layersData, layersStyleData);

  // Group layers by their QGIS layer-tree group path (spec feedback:
  // a flat checkbox list got hard to read once there were many
  // layers, so this mirrors the QGIS panel's group/subgroup nesting).
  // `order` holds tagged {type: 'group'|'item', ...} entries in the
  // order each was first encountered below, so a group and its sibling
  // items/groups keep their original relative position instead of
  // being split into "all groups, then all items".
  var tree = { children: {}, order: [] };
  layersConfig.forEach(function (layerConfig) {
    var geojson = layersData[layerConfig.id];
    var styleData = layersStyleData[layerConfig.id] || {};
    // showPopup === false (データ設定 tab's per-layer "ポップアップ表示"
    // checkbox) means this layer should be entirely click/hover-inert -
    // not just popup-less. A background reference layer (e.g. a ward
    // boundary) is otherwise still `interactive` and can win Leaflet's
    // hit-test over a point layer sitting on top of it, since Canvas/
    // SVG resolve overlapping clicks to whichever eligible layer was
    // added to the map last (spec feedback: clicking a point kept
    // opening the boundary's popup instead). Making it non-interactive
    // removes it from hit-testing entirely, so clicks/hover pass
    // through to whatever's actually underneath.
    var layerInteractive = layerConfig.showPopup !== false;
    var layerGroup = buildStyledLayer(
      geojson, styleData, popupTrigger, layerInteractive, layerConfig.id,
      buildPopupContext(layerConfig, display)
    );
    if (layerConfig.defaultVisible) layerGroup.addTo(map);
    // v0.3.0 spec feedback: even with the population/table order fixed
    // so layersConfig is genuinely back-to-front (data_tab.py task
    // 2-4), a polygon/line layer earlier in that order could STILL win
    // click hit-tests over a point layer listed later/in-front - traced
    // to Leaflet's Canvas renderer resolving _onClick by walking its
    // OWN internal paint-order linked list (_drawFirst/.next), which
    // does NOT reliably match layersConfig's addTo() call order once
    // circleMarkers and Polygons/Polylines are mixed (verified via a
    // 7-layer repro: circleMarkers ended up grouped ahead of BOTH
    // polygons in that list regardless of where the polygons sat in
    // layersConfig). bringToFront() explicitly re-appends a layer's
    // Path children to the end of that same linked list, so calling it
    // here - once per layer, in layersConfig's already-correct
    // back-to-front order - makes it the authoritative click-priority
    // order instead of leaving it to Leaflet's internal registration
    // order. No-ops safely for a not-yet-visible (defaultVisible:false)
    // layer (bringToFront checks the layer actually has a renderer).
    bringLayerToFront(layerGroup);

    var node = tree;
    (layerConfig.groupPath || []).forEach(function (groupName) {
      if (!node.children[groupName]) {
        node.children[groupName] = { children: {}, order: [] };
        node.order.push({ type: 'group', name: groupName });
      }
      node = node.children[groupName];
    });
    node.order.push({
      type: 'item',
      item: {
        config: layerConfig,
        layerGroup: layerGroup,
        style: styleData.defaultStyle || {},
        categoryLegend: styleData.categoryLegend || null,
      },
    });
  });

  // Map-unit stroke widths (real-world meters, see style-renderer.js's
  // FAG_MAPUNIT_PATHS): resolve them to px for the initial zoom now
  // that every layer is built, then keep them tracking the zoom level
  // so zooming out shrinks them exactly like QGIS's マップ単位 widths
  // (instead of a constant screen thickness swallowing the whole map).
  if (FAG_MAPUNIT_PATHS.length) {
    fagUpdateMapUnitWeights(map);
    map.on('zoomend', function () { fagUpdateMapUnitWeights(map); });
  }

  renderLayerTree(tree, listEl, map);
  refreshGroupCheckboxStates();
}

/* Recursively brings every Path child (circleMarker/polygon/polyline -
   the things that actually participate in Canvas's click hit-test
   order) to the front of the shared canvas's paint order. Point
   markers are LayerGroups of two circleMarkers (visual + invisible hit
   target - see createStyledMarker), reached via .eachLayer; a non-
   circle marker (divIcon L.marker) has neither .eachLayer nor
   .bringToFront and is silently skipped - it doesn't need this, since
   plain DOM markers already click-prioritize correctly via normal DOM
   stacking (later-added = later in markerPane = on top), a completely
   separate mechanism from the shared canvas. */
function bringLayerToFront(layer) {
  if (layer.eachLayer) {
    layer.eachLayer(bringLayerToFront);
    return;
  }
  if (layer.bringToFront) layer.bringToFront();
}

// {checkbox, leaves: [...leaf <input> elements]} for every group
// header rendered so far, refreshed together (checked/indeterminate)
// whenever any leaf layer checkbox changes - see refreshGroupCheckboxStates.
var FAG_GROUP_CHECKBOXES = [];
var fagGroupIdSeq = 0;

function refreshGroupCheckboxStates() {
  FAG_GROUP_CHECKBOXES.forEach(function (entry) {
    var total = entry.leaves.length;
    var checkedCount = entry.leaves.filter(function (cb) { return cb.checked; }).length;
    entry.checkbox.checked = total > 0 && checkedCount === total;
    entry.checkbox.indeterminate = checkedCount > 0 && checkedCount < total;
  });
}

/* Renders one tree level and returns every leaf layer <input> checkbox
   under it (including ones nested in sub-groups), so a group header's
   own checkbox can toggle - and its checked/indeterminate state can
   reflect - all of its descendants, not just its direct children.

   node.order is walked in reverse: node.order[last] was added to the
   map LAST (drawn on top of its siblings), so listing it FIRST here
   makes "top of this panel" mean "top of the map" - same convention
   data_tab.py uses for its own table. Groups and items share this one
   reversal (spec feedback: keeping group order untouched while only
   reversing sibling items split them into "every group, then every
   item" and could put a group's header out of place relative to
   siblings it's actually interleaved with in the QGIS layer tree). */
function renderLayerTree(node, containerEl, map) {
  var leafCheckboxes = [];

  node.order.slice().reverse().forEach(function (entry) {
    if (entry.type === 'group') {
      var groupName = entry.name;
      var child = node.children[groupName];
      var groupLi = document.createElement('li');
      groupLi.className = 'fag-layer-group';

      var groupCheckboxId = 'layer-group-toggle-' + (fagGroupIdSeq++);
      var header = document.createElement('div');
      header.className = 'fag-layer-group-header';
      header.innerHTML = '<input type="checkbox" id="' + groupCheckboxId + '" checked>' +
        '<label for="' + groupCheckboxId + '" class="fag-layer-group-title"></label>';
      header.querySelector('label').textContent = groupName;
      groupLi.appendChild(header);

      var subUl = document.createElement('ul');
      subUl.className = 'fag-layer-sublist';
      groupLi.appendChild(subUl);

      containerEl.appendChild(groupLi);

      var groupLeaves = renderLayerTree(child, subUl, map);
      var groupCheckbox = header.querySelector('input');
      groupCheckbox.addEventListener('change', function (e) {
        var checked = e.target.checked;
        groupLeaves.forEach(function (cb) {
          if (cb.checked !== checked) {
            cb.checked = checked;
            cb.dispatchEvent(new Event('change'));
          }
        });
      });
      FAG_GROUP_CHECKBOXES.push({ checkbox: groupCheckbox, leaves: groupLeaves });
      leafCheckboxes = leafCheckboxes.concat(groupLeaves);
    } else {
      var item = entry.item;
      var layerConfig = item.config;
      var layerGroup = item.layerGroup;
      var checkboxId = 'layer-toggle-' + layerConfig.id;
      var li = document.createElement('li');
      li.className = 'fag-layer-item';
      li.innerHTML = '<input type="checkbox" id="' + checkboxId + '"' +
        (layerConfig.defaultVisible ? ' checked' : '') + '>' +
        buildLegendSwatchHtml(item.style) +
        '<label for="' + checkboxId + '"></label>';
      li.querySelector('label').textContent = layerConfig.label;
      // A categorized layer lists each of its categories underneath,
      // so the panel matches what QGIS's own legend shows for it.
      var categoryList = buildCategoryLegendHtml(item.categoryLegend);
      if (categoryList) li.appendChild(categoryList);
      var checkbox = li.querySelector('input');
      checkbox.addEventListener('change', function (e) {
        if (e.target.checked) {
          layerGroup.addTo(map);
        } else {
          map.removeLayer(layerGroup);
        }
        refreshGroupCheckboxStates();
      });
      containerEl.appendChild(li);
      leafCheckboxes.push(checkbox);
    }
  });

  return leafCheckboxes;
}

/* Small swatch shown next to each layer's toggle checkbox so the
   panel doubles as a legend (spec feedback: previously just a
   checkbox + name, with no hint of what the layer actually looks
   like on the map). Uses the layer's defaultStyle only - a
   categorized layer's per-category colors aren't broken out here,
   just its fallback style. */
/* A fully opaque swatch background would misrepresent a semi-transparent
   fill, and would show a solid block for an outline-only polygon
   (fillOpacity 0) as if it had a real fill - so the swatch's background
   must carry the same opacity the map itself uses, not just its color. */
function hexToRgba(hex, opacity) {
  if (!hex) return 'transparent';
  var h = hex.replace('#', '');
  if (h.length === 3) h = h.split('').map(function (c) { return c + c; }).join('');
  var r = parseInt(h.substring(0, 2), 16);
  var g = parseInt(h.substring(2, 4), 16);
  var b = parseInt(h.substring(4, 6), 16);
  var a = (opacity === undefined || opacity === null) ? 1 : opacity;
  return 'rgba(' + r + ',' + g + ',' + b + ',' + a + ')';
}

function buildLegendSwatchHtml(style) {
  if (!style) return '';
  if (style.marker) {
    var m = style.marker;
    var shape = m.shape || 'circle';
    var bg = hexToRgba(m.color, m.opacity);
    if (shape === 'circle' || shape === 'square') {
      // Same fill/stroke opacity split the map itself uses, so a
      // see-through marker reads as see-through in the legend too.
      var strokeColor = hexToRgba(m.strokeColor || m.color, m.strokeOpacity);
      var strokeWidth = (m.strokeWidth === undefined || m.strokeWidth === null) ? 1 : m.strokeWidth;
      var shapeClass = shape === 'circle' ? 'fag-legend-circle' : 'fag-legend-box';
      return '<span class="fag-legend-swatch ' + shapeClass + '" style="background:' + bg +
        ';border:' + strokeWidth + 'px solid ' + strokeColor + ';"></span>';
    }
    // Clipped/rotated shapes (star/cross/triangle/diamond) mirror the
    // map's own divIcon rendering, which is borderless fill-only - a
    // border would get unevenly cut off by the clip-path anyway. The
    // shape vocabulary here matches SHAPE_NAME_MAP on the Python side
    // (style_extractor.py), so each has a .fag-legend-<shape> rule.
    return '<span class="fag-legend-swatch fag-legend-' + shape + '" style="background:' + bg + ';"></span>';
  }
  if (style.line) {
    return '<span class="fag-legend-swatch fag-legend-line" style="background:' +
      hexToRgba(style.line.color, style.line.opacity) + ';"></span>';
  }
  if (style.fill) {
    var f = style.fill;
    var fillBg = (f.hasFill === false) ? 'transparent' : hexToRgba(f.fillColor, f.fillOpacity);
    var border = (f.hasStroke === false || !f.strokeWidth)
      ? '0'
      : Math.min(f.strokeWidth, 3) + 'px solid ' + hexToRgba(f.strokeColor, f.strokeOpacity);
    return '<span class="fag-legend-swatch fag-legend-box" style="background:' + fillBg +
      ';border:' + border + ';"></span>';
  }
  if (style.tile) {
    return '<span class="fag-legend-swatch fag-legend-tile"></span>';
  }
  return '';
}

/* Per-category legend rows for a layer using a QGIS categorized
   renderer (spec item 3: "凡例もカテゴリ単位で出力する"). Without
   this the panel showed one swatch per LAYER - for a layer whose whole
   point is that it's colored by 施設種別 or 活用方針, that single
   swatch is one arbitrary category's color and tells the reader
   nothing. `label` is QGIS's own legend text for the category, which
   is often not the raw value ("1" -> "小学校"). Uses the same
   buildLegendSwatchHtml as the layer rows, so a categorized polygon's
   entries show the same transparency/outline treatment as everything
   else. */
function buildCategoryLegendHtml(categoryLegend) {
  if (!categoryLegend || !categoryLegend.entries || !categoryLegend.entries.length) return null;
  var ul = document.createElement('ul');
  ul.className = 'fag-legend-categories';
  categoryLegend.entries.forEach(function (entry) {
    var li = document.createElement('li');
    li.innerHTML = buildLegendSwatchHtml(entry.style) + '<span></span>';
    // textContent, not innerHTML - a category label is raw QGIS data and
    // can contain <, & or quotes.
    li.querySelector('span:last-child').textContent = entry.label;
    ul.appendChild(li);
  });
  return ul;
}

/* For a categorized-renderer layer (spec 4.2.2/4.2.3), pick the
   per-category sub-style (marker/line/fill[+label]) matching this
   feature's classification field value; null if there's no byCategory
   table or the value doesn't match any category (caller then falls
   back to defaultStyle - the same outcome QGIS gives an unmatched
   value that isn't covered by an "all other values" catch-all). */
function resolveCategoryStyle(byCategory, props) {
  if (!byCategory) return null;
  var field = Object.keys(byCategory)[0];
  if (!field) return null;
  var table = byCategory[field];
  var raw = props ? props[field] : undefined;
  var key = (raw === null || raw === undefined) ? '' : String(raw);
  return Object.prototype.hasOwnProperty.call(table, key) ? table[key] : null;
}

/* When multiple point features sit at the exact same coordinate (or a
   QGIS-precision-identical one - geojson_writer.py already rounds to 6
   decimals, so two truly co-located source points end up byte-identical
   here), their circleMarkers/hit-targets stack exactly on top of each
   other: only the topmost color is visible, its label overlaps the
   others illegibly (label-declutter.js then hides one, since both
   permanent tooltips anchor at the same screen position), and a click
   can hit whichever one happens to be on top in DOM order - not
   necessarily the one that's visually showing (spec feedback: point
   color/label/popup didn't match at a shared coordinate). This must
   run across *every* marker layer together, not one layer at a time:
   two facilities can be split across separate legend layers (e.g.
   filtered from one shared dataset into 事業予定地/処分検討地/継続保有地
   by their 活用方針 value) and still share a coordinate - a per-layer
   check would never see that, since each layer's own GeoJSON only has
   one of the two points. Spreading every exact-duplicate group into a
   small ring (a fixed real-world radius, not a screen-pixel one -
   simple and avoids pulling in a clustering library) gives each point
   its own position, so color/label/popup all correspond to the same
   dot again regardless of which layer(s) they came from. Mutates the
   layersData features in place, once, before any layer is built. */
function spreadOverlappingPointsAcrossLayers(layersConfig, layersData, layersStyleData) {
  var groups = {};
  layersConfig.forEach(function (layerConfig) {
    var styleData = layersStyleData[layerConfig.id] || {};
    if (!(styleData.defaultStyle && styleData.defaultStyle.marker)) return; // point/marker layers only
    var geojson = layersData[layerConfig.id];
    if (!geojson || !geojson.features) return;
    geojson.features.forEach(function (feature) {
      if (!feature.geometry || feature.geometry.type !== 'Point') return;
      var coords = feature.geometry.coordinates;
      var key = coords[0].toFixed(6) + ',' + coords[1].toFixed(6);
      (groups[key] = groups[key] || []).push(feature);
    });
  });
  Object.keys(groups).forEach(function (key) {
    var group = groups[key];
    if (group.length < 2) return;
    var lng0 = group[0].geometry.coordinates[0];
    var lat0 = group[0].geometry.coordinates[1];
    var n = group.length;
    // Grows a little with group size so 5-6 stacked features still end
    // up with visibly separate dots, not just a slightly-fatter ring.
    var radiusMeters = 3 + Math.min(n, 8) * 0.6;
    var latRad = (lat0 * Math.PI) / 180;
    var lngScale = Math.cos(latRad) || 1;
    group.forEach(function (feature, i) {
      var angle = (2 * Math.PI * i) / n;
      var dLat = (radiusMeters * Math.sin(angle)) / 111320;
      var dLng = (radiusMeters * Math.cos(angle)) / (111320 * lngScale);
      feature.geometry.coordinates = [lng0 + dLng, lat0 + dLat];
      // Flags this feature for pointToLayer below - only spread-apart
      // points are close enough together that label-declutter.js needs
      // to try more than one label direction (see fagLabelMultiDirection);
      // trying all 4 directions for every one of a dataset's labels
      // (most of which never sit this close to a neighbor) made a
      // full-extent view with hundreds of labels noticeably slow to
      // lay out.
      feature.__fagSpread = true;
    });
  });
}

function buildStyledLayer(geojson, styleData, popupTrigger, interactive, layerId, popupCtx) {
  var style = (styleData && styleData.defaultStyle) || {};
  var byCategory = (styleData && styleData.byCategory) || null;
  // データ設定 tab's per-layer "ポップアップ表示" checkbox, unchecked.
  // Labels/legend still show as normal - only click/hover interactivity
  // (popup, hover highlight, and being hit-tested at all) is disabled,
  // which is also how a background reference layer is kept from
  // stealing clicks meant for a layer on top of it (see
  // initLayerControl's layerInteractive and the `fill` comment below
  // for the same idea applied to just fillOpacity:0 polygons).
  interactive = interactive !== false;

  if (style.tile) {
    // A raster/XYZ layer already present in the QGIS project (e.g. a
    // 国土地理院 basemap), published as-is rather than styled GeoJSON.
    // `opacity` (v0.3.0 task 2-3) is either the layer's own native
    // QGIS transparency or the plugin's per-layer override - see
    // core/tile_layer.py::extract_tile_style.
    var tileOpacity = (style.tile.opacity === undefined || style.tile.opacity === null) ? 1 : style.tile.opacity;
    return L.tileLayer(style.tile.url, {
      minZoom: style.tile.minZoom,
      maxZoom: style.tile.maxNativeZoom,
      maxNativeZoom: style.tile.maxNativeZoom,
      opacity: tileOpacity,
    });
  }

  if (!geojson) return L.layerGroup();

  if (style.marker) {
    // Duplicate-coordinate spreading already happened once, across all
    // layers, in initLayerControl - see spreadOverlappingPointsAcrossLayers.
    return L.geoJSON(geojson, {
      pointToLayer: function (feature, latlng) {
        var props = feature.properties || {};
        var resolved = resolveCategoryStyle(byCategory, props);
        var markerStyle = (resolved && resolved.marker) || style.marker;
        var labelStyle = (resolved && resolved.label) || style.label;
        var marker = createStyledMarker([latlng.lat, latlng.lng], markerStyle, interactive);
        var hit = marker.fagInteractive || marker;
        var visual = marker.fagVisual || marker;
        bindStyledLabel(hit, props.label_text, markerStyle, labelStyle);
        hit.fagLabelMultiDirection = !!feature.__fagSpread;
        registerFeature(layerId, feature, hit);
        if (interactive) {
          bindPopupIfAny(hit, props, popupTrigger, popupCtx);
          if (popupTrigger !== 'none') bindHoverHighlight(hit, visual);
        }
        return marker;
      },
    });
  }

  if (style.line) {
    return L.geoJSON(geojson, {
      style: function (feature) {
        var props = (feature && feature.properties) || {};
        var resolved = resolveCategoryStyle(byCategory, props);
        var lineStyle = (resolved && resolved.line) || style.line;
        return {
          color: lineStyle.color,
          weight: lineStyle.width,
          // Independent of the color itself: QGIS multiplies the line
          // color's own alpha by the symbol's opacity and the layer's
          // opacity, and style_extractor.py exports that product.
          opacity: lineStyle.opacity === undefined ? 1 : lineStyle.opacity,
          // Already a px pattern derived from the Qt pen style (or a
          // custom dash vector) - see _dash_array_for_pen.
          dashArray: lineStyle.dashArray || null,
          interactive: interactive,
        };
      },
      onEachFeature: function (feature, layer) {
        registerFeature(layerId, feature, layer);
        // widthMeters = QGIS マップ単位 width (a real-world size, e.g.
        // a road drawn at its actual width). The px weight for it is
        // zoom-dependent, recomputed by fagUpdateMapUnitWeights -
        // initLayerControl runs it once after all layers are built
        // (before that this feature keeps the fallback px width from
        // style() above) and again on every zoomend.
        var resolved = resolveCategoryStyle(byCategory, (feature && feature.properties) || {});
        var lineStyle = (resolved && resolved.line) || style.line;
        if (lineStyle.widthMeters) {
          FAG_MAPUNIT_PATHS.push({ path: layer, meters: lineStyle.widthMeters });
        }
        if (!interactive) return;
        bindPopupIfAny(layer, feature.properties, popupTrigger, popupCtx);
        if (popupTrigger !== 'none') bindHoverHighlight(layer);
      },
    });
  }

  if (style.fill) {
    return L.geoJSON(geojson, {
      style: function (feature) {
        var props = (feature && feature.properties) || {};
        var resolved = resolveCategoryStyle(byCategory, props);
        var fillStyle = (resolved && resolved.fill) || style.fill;
        return {
          fillColor: fillStyle.fillColor,
          fillOpacity: fillStyle.fillOpacity,
          // A "fill-opacity: 0" polygon (e.g. an outline-only ward
          // boundary) is still hit-tested as if solid unless `fill`
          // itself is turned off - otherwise its invisible interior
          // silently steals clicks meant for point markers on top of
          // or near it (spec feedback: clicking near points kept
          // opening the boundary layer's popup instead). `interactive`
          // being false removes it from hit-testing entirely (including
          // its stroke) - the stronger, opt-in version of this same fix.
          // hasFill is QGIS's explicit "塗りつぶしなし" (Qt.NoBrush or an
          // outline-only symbol); the fillOpacity check additionally
          // catches a fill that's merely fully transparent.
          fill: fillStyle.hasFill !== false && fillStyle.fillOpacity > 0,
          color: fillStyle.strokeColor,
          weight: fillStyle.strokeWidth,
          // Fill and outline transparency are separate settings in QGIS
          // and stay separate here - a 20%-opacity fill under a solid
          // border is a very common boundary/zone style.
          opacity: fillStyle.strokeOpacity === undefined ? 1 : fillStyle.strokeOpacity,
          stroke: fillStyle.hasStroke !== false && fillStyle.strokeWidth > 0,
          dashArray: fillStyle.dashArray || null,
          interactive: interactive,
        };
      },
      onEachFeature: function (feature, layer) {
        registerFeature(layerId, feature, layer);
        // Same map-unit scheme as the line branch, for polygon outlines.
        var resolved = resolveCategoryStyle(byCategory, (feature && feature.properties) || {});
        var fillStyle = (resolved && resolved.fill) || style.fill;
        if (fillStyle.strokeWidthMeters) {
          FAG_MAPUNIT_PATHS.push({ path: layer, meters: fillStyle.strokeWidthMeters });
        }
        if (!interactive) return;
        bindPopupIfAny(layer, feature.properties, popupTrigger, popupCtx);
        if (popupTrigger !== 'none') bindHoverHighlight(layer);
      },
    });
  }

  return L.geoJSON(geojson);
}

/* Skips binding a popup entirely when every attribute is hidden (all
   fields unchecked in the plugin's per-layer field picker) - an empty
   `<div class="fag-popup"></div>` box popping up on click reads as a
   bug ("何も出ない"), so absent any content there should be no popup
   at all. `popupTrigger === 'hover'` (表示設定 tab) additionally opens
   the popup on mouseover/closes on mouseout; the default click-to-open
   binding is left in place either way, so hovering never disables
   clicking, it just adds an extra way in. */
function bindPopupIfAny(layer, props, popupTrigger, popupCtx) {
  var html = buildGenericPopupHtml(props, popupCtx, fagFeatureLatLng(layer));
  if (!html) return;
  layer.bindPopup(html);
  if (popupTrigger === 'hover') {
    layer.on('mouseover', function () { layer.openPopup(); });
    layer.on('mouseout', function () { layer.closePopup(); });
  }
}
