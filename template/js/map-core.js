/* Basemap tile sources the user can pick on the 表示設定 tab. GSI
   (国土地理院) tiles only go up to z18, so their layer definition caps
   maxZoom there even if the user set a higher global max - Leaflet
   still lets you zoom further, it just upscales the last tile. */
var BASEMAP_DEFS = {
  carto_light: {
    url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    options: {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
      subdomains: 'abcd',
    },
  },
  osm: {
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    options: {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      subdomains: 'abc',
    },
  },
  gsi_pale: {
    url: 'https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png',
    options: {
      attribution: '&copy; <a href="https://maps.gsi.go.jp/development/ichiran.html">国土地理院</a>',
      maxNativeZoom: 18,
    },
  },
  gsi_standard: {
    url: 'https://cyberjapandata.gsi.go.jp/xyz/std/{z}/{x}/{y}.png',
    options: {
      attribution: '&copy; <a href="https://maps.gsi.go.jp/development/ichiran.html">国土地理院</a>',
      maxNativeZoom: 18,
    },
  },
};

/* Map initialization (core, always runs - spec 5.2). */
function initMap(config) {
  var display = (config && config.display) || {};
  var map = L.map('map', {
    minZoom: display.minZoom || 1,
    maxZoom: display.maxZoom || 19,
  });

  var basemap = BASEMAP_DEFS[display.basemap] || BASEMAP_DEFS.carto_light;
  L.tileLayer(basemap.url, Object.assign({
    maxZoom: display.maxZoom || 19,
  }, basemap.options)).addTo(map);

  // Appended, not replacing the basemap's own attribution() above -
  // that one's required by its provider's terms of use (spec 出力設定
  // "帰属表示" adds the user's own credit alongside it, not instead).
  if (display.attribution) {
    map.attributionControl.addAttribution(display.attribution);
  }

  return map;
}
