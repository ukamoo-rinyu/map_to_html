/* Feature selection + CSV/GeoJSON export (spec item 9). Everything
   here runs entirely in the browser - no server, no external service -
   so it works from a shared folder, a file:// path or SharePoint alike.

   Selection state is {layerId: {fid: true}}. The highlight is drawn as
   a SEPARATE overlay layer rather than by restyling the selected
   feature: style-renderer.js's hover highlight snapshots each layer's
   baseline options and restores them on mouseout, and
   fagUpdateMapUnitWeights rewrites `weight` on every zoom - a
   selection that mutated the same options would be silently undone by
   either of them. An overlay sidesteps both. */
var FAG_SELECTION = {};
var FAG_SELECTION_HIGHLIGHT = null;
var FAG_SELECTION_CHANGE_HOOKS = [];

var FAG_SELECT_COLOR = '#ffd400';
var FAG_SELECT_HALO = '#7a5c00';
// Exporting tens of thousands of rows blocks the main thread for a few
// seconds while the string is built; past this many the user gets a
// chance to back out first.
var FAG_EXPORT_CONFIRM_THRESHOLD = 5000;

function fagSelectionCount() {
  var total = 0;
  Object.keys(FAG_SELECTION).forEach(function (layerId) {
    total += Object.keys(FAG_SELECTION[layerId]).length;
  });
  return total;
}

function fagIsSelected(layerId, fid) {
  return !!(FAG_SELECTION[layerId] && FAG_SELECTION[layerId][fid]);
}

function fagSetSelected(layerId, fid, selected) {
  if (selected) {
    if (!FAG_SELECTION[layerId]) FAG_SELECTION[layerId] = {};
    FAG_SELECTION[layerId][fid] = true;
  } else if (FAG_SELECTION[layerId]) {
    delete FAG_SELECTION[layerId][fid];
    if (!Object.keys(FAG_SELECTION[layerId]).length) delete FAG_SELECTION[layerId];
  }
}

function fagClearSelection() {
  FAG_SELECTION = {};
}

/* Registered by point-list.js so the table can repaint its rows'
   selected state whenever the map's selection changes (the map->list
   half of the spec's "双方向に同期"; the list->map half is the row
   click handler over there). */
function fagOnSelectionChange(hook) {
  FAG_SELECTION_CHANGE_HOOKS.push(hook);
}

function fagSelectionChanged(map) {
  fagRedrawSelectionHighlight(map);
  var countEl = document.getElementById('selection-count');
  if (countEl) {
    var n = fagSelectionCount();
    countEl.textContent = n ? (n + ' selected') : 'None selected';
  }
  FAG_SELECTION_CHANGE_HOOKS.forEach(function (hook) {
    try { hook(); } catch (e) { /* a listener must not break selection */ }
  });
}

function fagRedrawSelectionHighlight(map) {
  if (FAG_SELECTION_HIGHLIGHT) map.removeLayer(FAG_SELECTION_HIGHLIGHT);
  FAG_SELECTION_HIGHLIGHT = L.layerGroup();

  Object.keys(FAG_SELECTION).forEach(function (layerId) {
    var byFid = FAG_FEATURES_BY_LAYER[layerId] || {};
    Object.keys(FAG_SELECTION[layerId]).forEach(function (fid) {
      var entry = byFid[fid];
      if (!entry) return;
      var geometry = entry.feature && entry.feature.geometry;
      if (!geometry) return;
      if (geometry.type === 'Point') {
        var coords = geometry.coordinates;
        // A ring around the marker rather than over it, so the feature's
        // own color stays readable while selected.
        FAG_SELECTION_HIGHLIGHT.addLayer(L.circleMarker([coords[1], coords[0]], {
          radius: 11, color: FAG_SELECT_COLOR, weight: 3, opacity: 1,
          fill: false, interactive: false,
        }));
        FAG_SELECTION_HIGHLIGHT.addLayer(L.circleMarker([coords[1], coords[0]], {
          radius: 13, color: FAG_SELECT_HALO, weight: 1, opacity: 0.9,
          fill: false, interactive: false,
        }));
      } else {
        FAG_SELECTION_HIGHLIGHT.addLayer(L.geoJSON(entry.feature, {
          style: { color: FAG_SELECT_COLOR, weight: 5, opacity: 1, fill: false },
          interactive: false,
        }));
      }
    });
  });

  FAG_SELECTION_HIGHLIGHT.addTo(map);
  // A plain L.layerGroup has no bringToFront of its own - reuse
  // layer-control.js's recursive helper, which walks down to the actual
  // Path children. These are all interactive:false, so moving them to
  // the end of the canvas draw order puts the highlight on top without
  // disturbing the click-priority order that helper set up at load.
  bringLayerToFront(FAG_SELECTION_HIGHLIGHT);
}

/* ------------------------------------------------------------------
   Value formatting shared by both export formats.
   ------------------------------------------------------------------ */

/* Attribute keys to export, in the GeoJSON's own property order (which
   core/geojson_writer.py already wrote in the user's chosen field
   order). The plugin's synthetic attributes are excluded, matching the
   popup. */
function fagExportFields(rows) {
  var seen = {};
  var fields = [];
  rows.forEach(function (entry) {
    Object.keys(entry.feature.properties || {}).forEach(function (key) {
      if (key === '_fid' || key === 'label_text' || seen[key]) return;
      seen[key] = true;
      fields.push(key);
    });
  });
  return fields;
}

/* A representative lat/lng for a row - the spec requires coordinate
   columns in the CSV, using the centroid for lines and polygons.
   Reuses style-renderer.js's fagFeatureLatLng so a CSV coordinate and
   the popup's Google Maps link can never disagree. */
function fagExportLatLng(entry) {
  var geometry = entry.feature && entry.feature.geometry;
  if (geometry && geometry.type === 'Point') {
    return { lat: geometry.coordinates[1], lng: geometry.coordinates[0] };
  }
  return fagFeatureLatLng(entry.layer);
}

function fagCsvCell(value, forceText) {
  if (value === null || value === undefined) return '';
  var text = String(value);
  if (forceText && /^0\d/.test(text)) {
    // Excel strips the leading zero from a facility/ward code like
    // "0123" unless it's handed a formula-quoted literal.
    text = '="' + text.replace(/"/g, '""') + '"';
  }
  if (/[",\r\n]/.test(text)) {
    return '"' + text.replace(/"/g, '""') + '"';
  }
  return text;
}

function fagBuildCsv(rows, aliases, options) {
  options = options || {};
  var fields = fagExportFields(rows);
  var header = fields.map(function (name) {
    return fagCsvCell(aliases[name] || name, false);
  });
  header.push('latitude', 'longitude');

  var lines = [header.join(',')];
  rows.forEach(function (entry) {
    var props = entry.feature.properties || {};
    var cells = fields.map(function (name) {
      return fagCsvCell(props[name], options.forceTextCodes);
    });
    var latlng = fagExportLatLng(entry);
    cells.push(latlng ? latlng.lat.toFixed(6) : '');
    cells.push(latlng ? latlng.lng.toFixed(6) : '');
    lines.push(cells.join(','));
  });
  // CRLF: Excel is the overwhelmingly common consumer here and is
  // happiest with it, and every other tool accepts it.
  return lines.join('\r\n') + '\r\n';
}

function fagBuildGeoJson(rows, indent) {
  var features = rows.map(function (entry) {
    var props = {};
    Object.keys(entry.feature.properties || {}).forEach(function (key) {
      if (key === '_fid' || key === 'label_text') return;
      props[key] = entry.feature.properties[key];
    });
    return { type: 'Feature', properties: props, geometry: entry.feature.geometry };
  });
  // No "crs" member: the data is already WGS84, which RFC 7946 makes
  // the assumed and only CRS - emitting one is deprecated.
  var collection = { type: 'FeatureCollection', features: features };
  return JSON.stringify(collection, null, indent ? 2 : 0);
}

/* ------------------------------------------------------------------
   Download
   ------------------------------------------------------------------ */

function fagTimestamp() {
  var now = new Date();
  function pad(value) { return (value < 10 ? '0' : '') + value; }
  return now.getFullYear() + pad(now.getMonth() + 1) + pad(now.getDate()) +
    '_' + pad(now.getHours()) + pad(now.getMinutes());
}

function fagDownload(filename, text, mime, addBom) {
  // The BOM is what stops Excel from rendering a UTF-8 CSV of Japanese
  // text as mojibake - by far the most common complaint about
  // browser-generated CSVs, so it is on for every CSV export.
  var parts = addBom ? ['﻿', text] : [text];
  var blob = new Blob(parts, { type: mime });
  var url = URL.createObjectURL(blob);
  var link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  // Revoking immediately can cancel the download in some browsers.
  setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
}

function fagSafeFilename(name) {
  return String(name || 'layer').replace(/[\\/:*?"<>|]/g, '_').slice(0, 80);
}

/* ------------------------------------------------------------------
   Wiring
   ------------------------------------------------------------------ */

function initSelection(config, map) {
  var settings = (config.display && config.display.selection) || null;
  if (!settings) return;
  var bar = document.getElementById('selection-bar');
  if (!bar) return;

  var layersById = {};
  (config.layers || []).forEach(function (layerConfig) {
    layersById[layerConfig.id] = layerConfig;
  });

  // Only layers whose features were registered can be selected or
  // exported - the same set the feature table and search cover.
  function selectableLayerIds() {
    return Object.keys(FAG_FEATURES_BY_LAYER).filter(function (layerId) {
      var layerConfig = layersById[layerId];
      return layerConfig && layerConfig.showPopup !== false;
    });
  }

  function activeLayerId() {
    var select = document.getElementById('feature-table-layer-select');
    if (select && select.value) return select.value;
    return selectableLayerIds()[0];
  }

  function rowsFor(layerId, selectedOnly) {
    var byFid = FAG_FEATURES_BY_LAYER[layerId] || {};
    return Object.keys(byFid)
      .map(Number)
      .sort(function (a, b) { return a - b; })
      .filter(function (fid) { return !selectedOnly || fagIsSelected(layerId, fid); })
      .map(function (fid) { return byFid[fid]; });
  }

  function selectedRowsAllLayers() {
    var result = [];
    selectableLayerIds().forEach(function (layerId) {
      rowsFor(layerId, true).forEach(function (entry) {
        result.push({ layerId: layerId, entry: entry });
      });
    });
    return result;
  }

  bar.classList.remove('fag-hidden');

  // --- click selection ---------------------------------------------
  // Clicking a feature fires that layer's 'click' AND then the map's
  // own 'click' for the same physical click (layer first). Without
  // this, the map handler below would clear the selection the feature
  // handler just made. Comparing the underlying DOM event identifies
  // "same click" exactly, with no timer or flag left in a stale state
  // when propagation is stopped and no map click ever arrives.
  var lastFeatureClickEvent = null;

  // Bound per feature rather than via a map-level hit test so it uses
  // exactly the same hit target (and therefore the same click priority)
  // that popups already resolve through.
  selectableLayerIds().forEach(function (layerId) {
    var byFid = FAG_FEATURES_BY_LAYER[layerId];
    Object.keys(byFid).forEach(function (fid) {
      var entry = byFid[fid];
      if (!entry.layer || !entry.layer.on) return;
      entry.layer.on('click', function (event) {
        lastFeatureClickEvent = event.originalEvent || null;
        var additive = event.originalEvent &&
          (event.originalEvent.ctrlKey || event.originalEvent.metaKey ||
           event.originalEvent.shiftKey);
        if (additive) {
          // Ctrl/Cmd-click builds a multi-feature selection, and must
          // not also pop up a popup for each one.
          L.DomEvent.stopPropagation(event);
          if (entry.layer.closePopup) entry.layer.closePopup();
          fagSetSelected(layerId, fid, !fagIsSelected(layerId, fid));
        } else {
          fagClearSelection();
          fagSetSelected(layerId, fid, true);
        }
        fagSelectionChanged(map);
      });
    });
  });

  // Clicking empty map clears, matching how selection works basically
  // everywhere else - but not when this same click was already handled
  // by a feature above.
  map.on('click', function (event) {
    if (event.originalEvent && event.originalEvent === lastFeatureClickEvent) return;
    if (!fagSelectionCount()) return;
    fagClearSelection();
    fagSelectionChanged(map);
  });

  // --- rectangle selection -----------------------------------------
  var rectButton = document.getElementById('selection-rect-btn');
  var rectMode = false;
  var dragStart = null;
  var rubberBand = null;

  function setRectMode(on) {
    rectMode = on;
    rectButton.classList.toggle('fag-active', on);
    map.getContainer().style.cursor = on ? 'crosshair' : '';
    if (on) {
      map.dragging.disable();
      map.boxZoom.disable();
    } else {
      map.dragging.enable();
      map.boxZoom.enable();
    }
  }

  rectButton.addEventListener('click', function () { setRectMode(!rectMode); });

  map.on('mousedown', function (event) {
    if (!rectMode) return;
    dragStart = event.latlng;
    rubberBand = L.rectangle(L.latLngBounds(dragStart, dragStart), {
      color: FAG_SELECT_COLOR, weight: 2, dashArray: '5,4', fill: true,
      fillOpacity: 0.1, interactive: false,
    }).addTo(map);
  });

  map.on('mousemove', function (event) {
    if (!rectMode || !dragStart || !rubberBand) return;
    rubberBand.setBounds(L.latLngBounds(dragStart, event.latlng));
  });

  map.on('mouseup', function (event) {
    if (!rectMode || !dragStart) return;
    var bounds = L.latLngBounds(dragStart, event.latlng);
    if (rubberBand) { map.removeLayer(rubberBand); rubberBand = null; }
    dragStart = null;
    setRectMode(false);

    fagClearSelection();
    selectableLayerIds().forEach(function (layerId) {
      var byFid = FAG_FEATURES_BY_LAYER[layerId];
      Object.keys(byFid).forEach(function (fid) {
        var entry = byFid[fid];
        // Only what's actually on the map right now - a layer toggled
        // off in the panel isn't something the user can see to select.
        if (!map.hasLayer(entry.layer) && !(entry.layer._map)) return;
        var geometry = entry.feature.geometry;
        if (!geometry) return;
        var hit;
        if (geometry.type === 'Point') {
          hit = bounds.contains(L.latLng(geometry.coordinates[1], geometry.coordinates[0]));
        } else if (entry.layer.getBounds) {
          // Bounding-box intersection, which is what the spec asks for
          // ("面・線は矩形と交差で判定") - a true geometry intersection
          // would need a polygon-clipping library.
          hit = bounds.intersects(entry.layer.getBounds());
        }
        if (hit) fagSetSelected(layerId, fid, true);
      });
    });
    fagSelectionChanged(map);
  });

  // --- export buttons ----------------------------------------------
  function confirmLargeExport(count) {
    if (count <= FAG_EXPORT_CONFIRM_THRESHOLD) return true;
    return window.confirm(
      count + ' features will be exported. This may freeze the page for a few ' +
      'seconds. Continue?'
    );
  }

  function aliasesFor(layerId) {
    return (layersById[layerId] && layersById[layerId].fieldAliases) || {};
  }

  function labelFor(layerId) {
    return (layersById[layerId] && layersById[layerId].label) || layerId;
  }

  function exportCsv(selectedOnly) {
    var stamp = fagTimestamp();
    if (selectedOnly) {
      // A selection can span layers, and their columns differ - one
      // file per layer keeps each CSV's header meaningful rather than
      // producing a union of every layer's fields with mostly blanks.
      var byLayer = {};
      selectedRowsAllLayers().forEach(function (item) {
        (byLayer[item.layerId] = byLayer[item.layerId] || []).push(item.entry);
      });
      var layerIds = Object.keys(byLayer);
      if (!layerIds.length) { window.alert('Nothing is selected.'); return; }
      if (!confirmLargeExport(fagSelectionCount())) return;
      layerIds.forEach(function (layerId) {
        var csv = fagBuildCsv(byLayer[layerId], aliasesFor(layerId),
          { forceTextCodes: settings.forceTextCodes });
        fagDownload(fagSafeFilename(labelFor(layerId)) + '_selected_' + stamp + '.csv',
          csv, 'text/csv;charset=utf-8;', true);
      });
      return;
    }
    var layerId = activeLayerId();
    if (!layerId) return;
    var rows = rowsFor(layerId, false);
    if (!confirmLargeExport(rows.length)) return;
    fagDownload(fagSafeFilename(labelFor(layerId)) + '_' + stamp + '.csv',
      fagBuildCsv(rows, aliasesFor(layerId), { forceTextCodes: settings.forceTextCodes }),
      'text/csv;charset=utf-8;', true);
  }

  function exportGeoJson(selectedOnly) {
    var stamp = fagTimestamp();
    var rows;
    var name;
    if (selectedOnly) {
      rows = selectedRowsAllLayers().map(function (item) { return item.entry; });
      if (!rows.length) { window.alert('Nothing is selected.'); return; }
      name = 'selected_' + stamp;
    } else {
      var layerId = activeLayerId();
      if (!layerId) return;
      rows = rowsFor(layerId, false);
      name = fagSafeFilename(labelFor(layerId)) + '_' + stamp;
    }
    if (!confirmLargeExport(rows.length)) return;
    fagDownload(name + '.geojson', fagBuildGeoJson(rows, settings.prettyGeoJson),
      'application/geo+json', false);
  }

  document.getElementById('export-csv-selected')
    .addEventListener('click', function () { exportCsv(true); });
  document.getElementById('export-csv-all')
    .addEventListener('click', function () { exportCsv(false); });
  document.getElementById('export-geojson-selected')
    .addEventListener('click', function () { exportGeoJson(true); });
  document.getElementById('export-geojson-all')
    .addEventListener('click', function () { exportGeoJson(false); });

  var clearBtn = document.getElementById('selection-clear-btn');
  if (clearBtn) {
    clearBtn.addEventListener('click', function () {
      fagClearSelection();
      fagSelectionChanged(map);
    });
  }

  // point-list.js needs a way to push a row click back into the map's
  // selection; exposing it here keeps that module free of selection
  // bookkeeping.
  window.fagToggleSelectionFromTable = function (layerId, fid, additive) {
    if (!additive) fagClearSelection();
    fagSetSelected(layerId, fid, additive ? !fagIsSelected(layerId, fid) : true);
    fagSelectionChanged(map);
  };

  fagSelectionChanged(map);
}
