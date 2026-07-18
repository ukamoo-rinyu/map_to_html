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
  if (!layersConfig || !layersConfig.length) return;

  var panel = document.getElementById('layer-panel');
  var listEl = document.getElementById('layer-panel-list');
  panel.classList.remove('fag-hidden');

  // Group layers by their QGIS layer-tree group path (spec feedback:
  // a flat checkbox list got hard to read once there were many
  // layers, so this mirrors the QGIS panel's group/subgroup nesting).
  var tree = { children: {}, order: [], items: [] };
  layersConfig.forEach(function (layerConfig) {
    var geojson = layersData[layerConfig.id];
    var styleData = layersStyleData[layerConfig.id] || {};
    var layerGroup = buildStyledLayer(geojson, styleData, popupTrigger);
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

  node.items.forEach(function (item) {
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
    var strokeColor = m.strokeColor || m.color;
    var strokeWidth = (m.strokeWidth === undefined || m.strokeWidth === null) ? 1 : m.strokeWidth;
    var shapeClass = (!m.shape || m.shape === 'circle') ? 'fag-legend-circle' : 'fag-legend-box';
    return '<span class="fag-legend-swatch ' + shapeClass + '" style="background:' + hexToRgba(m.color, m.opacity) +
      ';border:' + strokeWidth + 'px solid ' + strokeColor + ';"></span>';
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

function buildStyledLayer(geojson, styleData, popupTrigger) {
  var style = (styleData && styleData.defaultStyle) || {};
  var byCategory = (styleData && styleData.byCategory) || null;

  if (style.tile) {
    // A raster/XYZ layer already present in the QGIS project (e.g. a
    // 国土地理院 basemap), published as-is rather than styled GeoJSON.
    return L.tileLayer(style.tile.url, {
      minZoom: style.tile.minZoom,
      maxZoom: style.tile.maxNativeZoom,
      maxNativeZoom: style.tile.maxNativeZoom,
    });
  }

  if (!geojson) return L.layerGroup();

  if (style.marker) {
    return L.geoJSON(geojson, {
      pointToLayer: function (feature, latlng) {
        var props = feature.properties || {};
        var resolved = resolveCategoryStyle(byCategory, props);
        var markerStyle = (resolved && resolved.marker) || style.marker;
        var labelStyle = (resolved && resolved.label) || style.label;
        var marker = createStyledMarker([latlng.lat, latlng.lng], markerStyle);
        bindStyledLabel(marker, props.label_text, markerStyle, labelStyle);
        bindPopupIfAny(marker, props, popupTrigger);
        bindHoverHighlight(marker);
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
        };
      },
      onEachFeature: function (feature, layer) {
        bindPopupIfAny(layer, feature.properties, popupTrigger);
        bindHoverHighlight(layer);
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
          // opening the boundary layer's popup instead).
          fill: fillStyle.fillOpacity > 0,
          color: fillStyle.strokeColor,
          weight: fillStyle.strokeWidth,
        };
      },
      onEachFeature: function (feature, layer) {
        bindPopupIfAny(layer, feature.properties, popupTrigger);
        bindHoverHighlight(layer);
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
