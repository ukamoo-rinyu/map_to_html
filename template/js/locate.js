/* "Show my location" button (表示設定 tab's 現在地ボタン, on by
   default): one tap asks the browser for the reader's position, puts a
   blue dot with an accuracy circle on the map and moves there. Tapping
   again refreshes it. Single-shot rather than continuous tracking, so
   the map never pans by itself while someone is reading it.

   Browsers only hand out a position to a page opened over https:// or
   from a file on the same device; plain http:// gets a clear message
   instead of a silent failure. The last fix is kept in
   FAG_LAST_LOCATION so the radius search can start from it. */

var FAG_LAST_LOCATION = null;   // L.LatLng, or null before the first fix
var FAG_LOCATION_LAYER = null;  // dot + accuracy circle

function initLocate(config, map) {
  if (!config.display || !config.display.locate) return;
  fagAddMapButton(map, {
    className: 'fag-locate-btn',
    html: '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">' +
      '<circle cx="12" cy="12" r="4" fill="currentColor"/>' +
      '<circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" stroke-width="2"/>' +
      '<path d="M12 1v4M12 19v4M1 12h4M19 12h4" stroke="currentColor" stroke-width="2"/></svg>',
    titleKey: 'locate.title',
    onClick: function () { fagLocate(map); },
  });
}

/* Calls `done(latlng)` after a successful fix (used by the radius
   search's 現在地から button); errors are reported to the reader. */
function fagLocate(map, done) {
  if (!navigator.geolocation) {
    fagToast(fagT('locate.unsupported'));
    return;
  }
  if (window.isSecureContext === false) {
    fagToast(fagT('locate.insecure'));
    return;
  }
  fagToast(fagT('locate.searching'), 15000);
  navigator.geolocation.getCurrentPosition(function (position) {
    var latlng = L.latLng(position.coords.latitude, position.coords.longitude);
    var accuracy = position.coords.accuracy || 0;
    FAG_LAST_LOCATION = latlng;
    fagShowLocation(map, latlng, accuracy);
    fagToast(fagT('locate.accuracy', [Math.round(accuracy)]));
    if (done) {
      done(latlng);
    } else if (accuracy > 300) {
      map.fitBounds(L.latLng(latlng).toBounds(accuracy * 2));
    } else {
      map.setView(latlng, Math.max(map.getZoom(), 16));
    }
  }, function (error) {
    var key = error.code === 1 ? 'locate.denied'
      : error.code === 3 ? 'locate.timeout'
      : 'locate.unavailable';
    fagToast(fagT(key), 6000);
  }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 30000 });
}

function fagShowLocation(map, latlng, accuracy) {
  if (FAG_LOCATION_LAYER) map.removeLayer(FAG_LOCATION_LAYER);
  // Not interactive: the dot must never swallow a click meant for a
  // facility drawn underneath it.
  FAG_LOCATION_LAYER = L.layerGroup([
    L.circle(latlng, {
      radius: accuracy, interactive: false,
      color: '#1a73e8', weight: 1, opacity: 0.5, fillColor: '#1a73e8', fillOpacity: 0.12,
    }),
    L.circleMarker(latlng, {
      radius: 7, interactive: false,
      color: '#ffffff', weight: 2, fillColor: '#1a73e8', fillOpacity: 1,
    }),
  ]).addTo(map);
}

/* A Leaflet control button with the same leaflet-bar look as the zoom
   and label buttons. `titleKey` is an i18n.js message, so the tooltip
   follows the language switch. Returns the <a> element. */
function fagAddMapButton(map, options) {
  var control = L.control({ position: 'topleft' });
  var button = null;
  control.onAdd = function () {
    var container = L.DomUtil.create('div', 'leaflet-bar fag-map-btn ' + (options.className || ''));
    button = L.DomUtil.create('a', '', container);
    button.href = '#';
    button.innerHTML = options.html;
    button.setAttribute('role', 'button');
    button.title = fagT(options.titleKey);
    button.setAttribute('aria-label', fagT(options.titleKey));
    button.setAttribute('data-i18n-title', options.titleKey);
    button.setAttribute('data-i18n-aria', options.titleKey);
    L.DomEvent.on(button, 'click', function (e) {
      L.DomEvent.stop(e);
      options.onClick(button);
    });
    L.DomEvent.disableClickPropagation(container);
    return container;
  };
  control.addTo(map);
  return button;
}

/* A short message over the bottom of the map (share/locate results). */
var fagToastTimer = null;
function fagToast(message, durationMs) {
  var el = document.getElementById('fag-toast');
  if (!el) return;
  el.textContent = message;
  el.classList.remove('fag-hidden');
  clearTimeout(fagToastTimer);
  fagToastTimer = setTimeout(function () {
    el.classList.add('fag-hidden');
  }, durationMs || 4000);
}
