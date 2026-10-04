/* Radius search (表示設定 tab's 半径検索): pick a center - a click on
   the map, the reader's current location, or the middle of the screen -
   and a radius, and the panel lists every feature within it, nearest
   first, with the circle drawn on the map. A row click zooms to the
   feature and opens its popup, like the search results.

   What is searched matches what the reader can see: layers checked in
   the layer panel (whatever the zoom), features the filter bar lets
   through, and only layers whose popup is on (the same rule search.js
   uses - a row for a non-clickable background layer would lead
   nowhere). A line or polygon is measured to the mean of its vertices
   (style-renderer.js's fagFeatureLatLng), the same point its map links
   use. */

var FAG_RADIUS_STATE = null;    // {center: L.LatLng, radius: meters} while a search is shown
// While the panel is open: function(latlng) that sets the center. A
// feature click calls it instead of opening a popup (bindPopupIfAny).
var FAG_RADIUS_PICK = null;
var FAG_RADIUS_LIST_LIMIT = 100;

function initRadiusSearch(config, map) {
  var settings = config.display && config.display.radiusSearch;
  if (!settings) return;

  var radii = (settings.radii || [250, 500, 1000, 2000]).slice();
  var defaultRadius = settings.defaultRadius || 500;
  if (radii.indexOf(defaultRadius) === -1) radii.push(defaultRadius);
  radii.sort(function (a, b) { return a - b; });

  var panel = fagBuildRadiusPanel(radii, defaultRadius);
  document.getElementById('map-pane').appendChild(panel.el);
  L.DomEvent.disableClickPropagation(panel.el);
  L.DomEvent.disableScrollPropagation(panel.el);

  var drawn = null;
  var open = false;

  function setOpen(value) {
    open = value;
    panel.el.classList.toggle('fag-hidden', !open);
    map.getContainer().classList.toggle('fag-radius-picking', open);
    FAG_RADIUS_PICK = open ? function (latlng) { run(latlng, false); } : null;
    if (open) map.closePopup();
    if (button) button.classList.toggle('fag-map-btn-active', open);
  }

  var button = fagAddMapButton(map, {
    className: 'fag-radius-btn',
    html: '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">' +
      '<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2" stroke-dasharray="3 2"/>' +
      '<circle cx="12" cy="12" r="2.5" fill="currentColor"/></svg>',
    titleKey: 'radius.title',
    onClick: function () { setOpen(!open); },
  });

  function run(center, fit) {
    var radius = Number(panel.select.value) || defaultRadius;
    FAG_RADIUS_STATE = { center: L.latLng(center), radius: radius };
    if (drawn) map.removeLayer(drawn);
    drawn = L.layerGroup([
      L.circle(center, {
        radius: radius, interactive: false,
        color: '#3b6fb0', weight: 2, dashArray: '6 4', fillColor: '#3b6fb0', fillOpacity: 0.06,
      }),
      L.circleMarker(center, {
        radius: 5, interactive: false, color: '#ffffff', weight: 2, fillColor: '#3b6fb0', fillOpacity: 1,
      }),
    ]).addTo(map);
    if (fit) map.fitBounds(FAG_RADIUS_STATE.center.toBounds(radius * 2), { padding: [20, 20] });
    fagRenderRadiusResults(map, config, panel);
    document.dispatchEvent(new Event('fag:radiuschange'));
  }

  function clear() {
    FAG_RADIUS_STATE = null;
    if (drawn) map.removeLayer(drawn);
    drawn = null;
    fagRenderRadiusResults(map, config, panel);
    document.dispatchEvent(new Event('fag:radiuschange'));
  }

  map.on('click', function (e) {
    if (!open) return;
    if (Date.now() - FAG_RECT_SELECT_ENDED_AT < 400) return; // end of a rectangle selection
    // A click on a label's text centers on the feature it labels.
    var hit = typeof hitTestLabelPlacement === 'function' ? hitTestLabelPlacement(e.containerPoint) : null;
    run(hit && hit.marker.getLatLng ? hit.marker.getLatLng() : e.latlng, false);
  });
  panel.select.addEventListener('change', function () {
    if (FAG_RADIUS_STATE) run(FAG_RADIUS_STATE.center, true);
  });
  panel.fromLocation.addEventListener('click', function () {
    fagLocate(map, function (latlng) { run(latlng, true); });
  });
  panel.fromCenter.addEventListener('click', function () { run(map.getCenter(), true); });
  panel.clear.addEventListener('click', clear);
  panel.close.addEventListener('click', function () { setOpen(false); });

  // The result list follows the layer panel and the filter bar.
  var listEl = document.getElementById('layer-panel-list');
  if (listEl) {
    listEl.addEventListener('change', function () {
      if (FAG_RADIUS_STATE) fagRenderRadiusResults(map, config, panel);
    });
  }
  document.addEventListener('fag:filterchange', function () {
    if (FAG_RADIUS_STATE) fagRenderRadiusResults(map, config, panel);
  });
  document.addEventListener('fag:langchange', function () {
    panel.relabel();
    fagRenderRadiusResults(map, config, panel);
  });

  // share.js restores a shared search through this.
  FAG_RADIUS_API = {
    show: function (center, radius) {
      if (radius) {
        if (radii.indexOf(radius) === -1) {
          panel.addOption(radius);
          radii.push(radius);
        }
        panel.select.value = String(radius);
      }
      setOpen(true);
      run(center, false);
    },
  };
}

var FAG_RADIUS_API = null;

function fagBuildRadiusPanel(radii, defaultRadius) {
  var el = document.createElement('div');
  el.id = 'radius-panel';
  el.className = 'fag-hidden';
  el.innerHTML =
    '<div class="fag-radius-head">' +
      '<span class="fag-radius-heading" data-i18n="radius.heading"></span>' +
      '<button type="button" class="fag-radius-close" data-i18n-title="radius.close" data-i18n-aria="radius.close">×</button>' +
    '</div>' +
    '<label class="fag-radius-row"><span data-i18n="radius.radius"></span> <select class="fag-radius-select"></select></label>' +
    '<div class="fag-radius-hint" data-i18n="radius.hint"></div>' +
    '<div class="fag-radius-actions">' +
      '<button type="button" class="fag-radius-from-location" data-i18n="radius.fromLocation"></button>' +
      '<button type="button" class="fag-radius-from-center" data-i18n="radius.fromCenter"></button>' +
      '<button type="button" class="fag-radius-clear" data-i18n="radius.clear"></button>' +
    '</div>' +
    '<div class="fag-radius-summary"></div>' +
    '<ul class="fag-radius-results"></ul>';

  var select = el.querySelector('.fag-radius-select');
  function addOption(radius) {
    var option = document.createElement('option');
    option.value = String(radius);
    option.textContent = fagFormatDistance(radius);
    var before = null;
    for (var i = 0; i < select.options.length; i++) {
      if (Number(select.options[i].value) > radius) { before = select.options[i]; break; }
    }
    select.insertBefore(option, before);
  }
  radii.forEach(addOption);
  select.value = String(defaultRadius);

  // The 現在地から button needs the browser's geolocation.
  var fromLocation = el.querySelector('.fag-radius-from-location');
  if (!navigator.geolocation) fromLocation.classList.add('fag-hidden');

  fagApplyI18n(el);
  return {
    el: el,
    select: select,
    addOption: addOption,
    fromLocation: fromLocation,
    fromCenter: el.querySelector('.fag-radius-from-center'),
    clear: el.querySelector('.fag-radius-clear'),
    close: el.querySelector('.fag-radius-close'),
    summary: el.querySelector('.fag-radius-summary'),
    results: el.querySelector('.fag-radius-results'),
    relabel: function () { fagApplyI18n(el); },
  };
}

function fagRadiusSearchableLayers(config) {
  var checked = {};
  FAG_LAYER_VISIBILITY.forEach(function (record) {
    checked[record.config.id] = record.checked;
  });
  return (config.layers || []).filter(function (layerConfig) {
    return !!FAG_FEATURES_BY_LAYER[layerConfig.id] && layerConfig.showPopup !== false &&
      checked[layerConfig.id];
  });
}

function fagRenderRadiusResults(map, config, panel) {
  panel.results.innerHTML = '';
  if (!FAG_RADIUS_STATE) {
    panel.summary.textContent = '';
    return;
  }
  var center = FAG_RADIUS_STATE.center;
  var radius = FAG_RADIUS_STATE.radius;
  var matches = [];
  fagRadiusSearchableLayers(config).forEach(function (layerConfig) {
    var byFid = FAG_FEATURES_BY_LAYER[layerConfig.id];
    Object.keys(byFid).forEach(function (fid) {
      var entry = byFid[fid];
      if (!fagFeaturePassesFilter(layerConfig.id, entry.feature)) return;
      var latlng = fagFeatureLatLng(entry.layer);
      if (!latlng) return;
      var distance = map.distance(center, latlng);
      if (distance <= radius) {
        matches.push({ layerConfig: layerConfig, entry: entry, distance: distance });
      }
    });
  });
  matches.sort(function (a, b) { return a.distance - b.distance; });

  var radiusText = fagFormatDistance(radius);
  if (!matches.length) {
    panel.summary.textContent = fagT('radius.none', [radiusText]) + ' ' + fagT('radius.layerOff');
    return;
  }
  panel.summary.textContent = matches.length > FAG_RADIUS_LIST_LIMIT
    ? fagT('radius.countMore', [matches.length, radiusText, FAG_RADIUS_LIST_LIMIT])
    : fagT('radius.count', [matches.length, radiusText]);

  var fragment = document.createDocumentFragment();
  matches.slice(0, FAG_RADIUS_LIST_LIMIT).forEach(function (match) {
    var li = document.createElement('li');
    li.className = 'fag-radius-result';
    li.innerHTML = '<span class="fag-radius-result-name"></span>' +
      '<span class="fag-radius-result-distance"></span>' +
      '<span class="fag-radius-result-layer"></span>';
    li.querySelector('.fag-radius-result-name').textContent =
      fagFeatureName(match.entry.feature.properties);
    li.querySelector('.fag-radius-result-distance').textContent = fagFormatDistance(match.distance);
    li.querySelector('.fag-radius-result-layer').textContent = match.layerConfig.label;
    li.addEventListener('click', function () {
      focusFeature(map, match.layerConfig.id, match.entry);
    });
    fragment.appendChild(li);
  });
  panel.results.appendChild(fragment);
}
