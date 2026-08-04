/* Applies Tab 2 (display settings) to the DOM and the initial map view.
   Always runs, regardless of which layers are configured (spec 5.2). */
function applyDisplaySettings(map, layersData, displayConfig) {
  var appEl = document.getElementById('app');
  displayConfig = displayConfig || {};

  if (displayConfig.sizeMode === 'fixed' && displayConfig.fixedSize) {
    appEl.classList.add('fixed-size');
    appEl.style.width = displayConfig.fixedSize.width + 'px';
    appEl.style.height = displayConfig.fixedSize.height + 'px';
  }

  // Default ON per spec 3.1 Tab 2 "responsive"; only opt out if explicitly false.
  if (displayConfig.responsive !== false) {
    appEl.classList.add('responsive');
  }

  applyInitialView(map, layersData, displayConfig.initialView);
  applyScaleBar(map, displayConfig.scaleBar);
}

/* Metric-only scale bar (spec item 1). Absent from config entirely when
   the plugin's checkbox is off, so nothing is added to the map. */
function applyScaleBar(map, scaleBar) {
  if (!scaleBar) return;
  L.control.scale({
    metric: true,
    imperial: false,
    position: scaleBar.position || 'bottomleft',
  }).addTo(map);
}

function applyInitialView(map, layersData, initialView) {
  initialView = initialView || { mode: 'autoFit' };

  if (initialView.mode === 'manual' && initialView.center) {
    map.setView(initialView.center, initialView.zoom || 13);
    return;
  }

  // The QGIS map canvas's own extent at export time, already converted
  // to WGS84 [[south, west], [north, east]] by dialog.py. fitBounds
  // rather than a center+zoom: Leaflet's zoom levels are whole steps,
  // so asking it to fit a rectangle lands much closer to what the user
  // saw in QGIS than rounding QGIS's continuous scale to a zoom level
  // would. The aspect ratios still differ, so the result is "at least
  // this area, usually a bit more" - noted in the tab's tooltip.
  if (initialView.mode === 'bounds' && initialView.bounds) {
    map.fitBounds(initialView.bounds);
    return;
  }

  var bounds = getCombinedBounds(layersData);
  if (bounds) {
    map.fitBounds(bounds, { padding: [24, 24] });
  } else {
    map.setView([35.681, 139.767], 10); // fallback: Tokyo, in case there is no data yet
  }
}

/* Union of every configured layer's extent (any geometry type), so
   "auto fit" still works now that there's no single designated
   "sites" layer to measure against. */
function getCombinedBounds(layersData) {
  var bounds = null;
  Object.keys(layersData || {}).forEach(function (id) {
    var geojson = layersData[id];
    if (!geojson || !geojson.features || !geojson.features.length) return;
    var layerBounds = L.geoJSON(geojson).getBounds();
    if (layerBounds.isValid()) {
      bounds = bounds ? bounds.extend(layerBounds) : layerBounds;
    }
  });
  return bounds;
}
