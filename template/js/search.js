/* Keyword search over config.fields.searchFields (spec 3.1 Tab 3
   "search box"). Filters both the map markers and the facility list. */
function initSearch(config, sitesData) {
  var input = document.getElementById('search-input');
  var countEl = document.getElementById('search-count');
  if (!input) return;

  function runSearch() {
    var keyword = input.value.trim().toLowerCase();
    var searchFields = config.fields.searchFields || [];
    var filtered = (sitesData.features || []).filter(function (feature) {
      if (!keyword) return true;
      var props = feature.properties || {};
      return searchFields.some(function (key) {
        var value = props[key];
        return value !== undefined && value !== null &&
          String(value).toLowerCase().indexOf(keyword) !== -1;
      });
    });

    applyFacilityFilter(filtered);
    if (countEl) countEl.textContent = filtered.length + ' 件';
  }

  input.addEventListener('input', runSearch);
  runSearch();
}

/* Shared by search.js: shows/hides markers on the map and re-renders
   the facility list to match the current filtered feature set. */
function applyFacilityFilter(filteredFeatures) {
  var idField = FAG.config.fields.idField;
  var visibleIds = {};
  filteredFeatures.forEach(function (feature) {
    var id = idField ? (feature.properties || {})[idField] : undefined;
    if (id !== undefined && id !== null) visibleIds[id] = true;
  });

  Object.keys(FAG.markersById).forEach(function (id) {
    var marker = FAG.markersById[id];
    var shouldShow = visibleIds[id] === true;
    var isShown = FAG.map.hasLayer(marker);
    if (shouldShow && !isShown) marker.addTo(FAG.map);
    if (!shouldShow && isShown) FAG.map.removeLayer(marker);
  });

  if (typeof updatePointList === 'function') {
    updatePointList(filteredFeatures);
  }
}
