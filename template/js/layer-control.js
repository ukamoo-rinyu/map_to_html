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
function initLayerControl(map, layersConfig, layersData, layersStyleData, popupTrigger) {
  var hasBasemap = !!map.fagBasemapLayer;
  var hasLayers = !!(layersConfig && layersConfig.length);
  if (!hasBasemap && !hasLayers) return;

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

  // v0.3.0 task 2-2: the single background basemap tile layer (chosen
  // on 表示設定 - see map-core.js's BASEMAP_DEFS) previously had no way
  // to hide it once published. Its own toggle entry sits at the top of
  // this panel, above the per-layer list, whenever a basemap exists.
  if (hasBasemap) {
    addBasemapToggleItem(map, listEl);
  }

  if (!hasLayers) return;

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
  var tree = { children: {}, order: [], items: [] };
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
    var layerGroup = buildStyledLayer(geojson, styleData, popupTrigger, layerInteractive);
    if (layerConfig.defaultVisible) layerGroup.addTo(map);

    var node = tree;
    (layerConfig.groupPath || []).forEach(function (groupName) {
      if (!node.children[groupName]) {
        node.children[groupName] = { children: {}, order: [], items: [] };
        node.order.push(groupName);
      }
      node = node.children[groupName];
    });
    node.items.push({ config: layerConfig, layerGroup: layerGroup, style: styleData.defaultStyle || {} });
  });

  renderLayerTree(tree, listEl, map);
}

/* v0.3.0 task 2-2: on/off toggle for the single background basemap
   tile layer (map.fagBasemapLayer, set by map-core.js's initMap).
   Reuses the existing checkerboard `.fag-legend-tile` swatch style
   already used for raster/XYZ tile legend entries, so it looks
   consistent with the rest of the panel without new CSS. */
function addBasemapToggleItem(map, listEl) {
  var li = document.createElement('li');
  li.innerHTML = '<input type="checkbox" id="layer-toggle-basemap" checked>' +
    '<span class="fag-legend-swatch fag-legend-tile"></span>' +
    '<label for="layer-toggle-basemap"></label>';
  li.querySelector('label').textContent = '背景地図';
  li.querySelector('input').addEventListener('change', function (e) {
    if (e.target.checked) {
      map.fagBasemapLayer.addTo(map);
    } else {
      map.removeLayer(map.fagBasemapLayer);
    }
  });
  listEl.appendChild(li);
}

function renderLayerTree(node, containerEl, map) {
  node.order.forEach(function (groupName) {
    var child = node.children[groupName];
    var groupLi = document.createElement('li');
    groupLi.className = 'fag-layer-group';

    var groupTitle = document.createElement('div');
    groupTitle.className = 'fag-layer-group-title';
    groupTitle.textContent = groupName;
    groupLi.appendChild(groupTitle);

    var subUl = document.createElement('ul');
    subUl.className = 'fag-layer-sublist';
    groupLi.appendChild(subUl);

    containerEl.appendChild(groupLi);
    renderLayerTree(child, subUl, map);
  });

  // v0.3.0 task 2-4: within this group level, display items in the
  // reverse of `layersConfig` order - node.items[last] was added to
  // the map LAST (drawn on top of its siblings), so listing it FIRST
  // here makes "top of this panel" mean "top of the map" for the
  // items sharing this group, matching data_tab.py's same reversal on
  // the plugin's own table. Sibling GROUP order (node.order, just
  // above) is intentionally left untouched - that mirrors QGIS's own
  // layer-tree group order, a separate concern from this stacking fix.
  node.items.slice().reverse().forEach(function (item) {
    var layerConfig = item.config;
    var layerGroup = item.layerGroup;
    var checkboxId = 'layer-toggle-' + layerConfig.id;
    var li = document.createElement('li');
    li.innerHTML = '<input type="checkbox" id="' + checkboxId + '"' +
      (layerConfig.defaultVisible ? ' checked' : '') + '>' +
      buildLegendSwatchHtml(item.style) +
      '<label for="' + checkboxId + '"></label>';
    li.querySelector('label').textContent = layerConfig.label;
    li.querySelector('input').addEventListener('change', function (e) {
      if (e.target.checked) {
        layerGroup.addTo(map);
      } else {
        map.removeLayer(layerGroup);
      }
    });
    containerEl.appendChild(li);
  });
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
      var strokeColor = m.strokeColor || m.color;
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
    return '<span class="fag-legend-swatch fag-legend-line" style="background:' + style.line.color + ';"></span>';
  }
  if (style.fill) {
    return '<span class="fag-legend-swatch fag-legend-box" style="background:' + hexToRgba(style.fill.fillColor, style.fill.fillOpacity) +
      ';border:' + style.fill.strokeWidth + 'px solid ' + style.fill.strokeColor + ';"></span>';
  }
  if (style.tile) {
    return '<span class="fag-legend-swatch fag-legend-tile"></span>';
  }
  return '';
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

function buildStyledLayer(geojson, styleData, popupTrigger, interactive) {
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
        if (interactive) {
          bindPopupIfAny(hit, props, popupTrigger);
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
          dashArray: lineStyle.dashed ? '6,4' : null,
          interactive: interactive,
        };
      },
      onEachFeature: function (feature, layer) {
        if (!interactive) return;
        bindPopupIfAny(layer, feature.properties, popupTrigger);
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
          fill: fillStyle.fillOpacity > 0,
          color: fillStyle.strokeColor,
          weight: fillStyle.strokeWidth,
          interactive: interactive,
        };
      },
      onEachFeature: function (feature, layer) {
        if (!interactive) return;
        bindPopupIfAny(layer, feature.properties, popupTrigger);
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
function bindPopupIfAny(layer, props, popupTrigger) {
  var html = buildGenericPopupHtml(props);
  if (!html) return;
  layer.bindPopup(html);
  if (popupTrigger === 'hover') {
    layer.on('mouseover', function () { layer.openPopup(); });
    layer.on('mouseout', function () { layer.closePopup(); });
  }
}
