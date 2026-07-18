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
}

function applyInitialView(map, layersData, initialView) {
  initialView = initialView || { mode: 'autoFit' };

  if (initialView.mode === 'manual' && initialView.center) {
    map.setView(initialView.center, initialView.zoom || 13);
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
