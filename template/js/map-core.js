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
    // Circle/line/polygon layers default to Leaflet's SVG renderer,
    // which draws one DOM node per feature - with several hundred
    // points across a few layers that's a lot of individual elements
    // for the browser to re-layout/re-paint on every pan or zoom (spec
    // feedback: the map stayed "激重" even after halving the marker
    // count and skipping off-screen labels). Canvas draws every vector
    // feature onto one shared <canvas> element instead - Leaflet's
    // click/hover/popup event handling on canvas-rendered layers works
    // the same as SVG (it does its own hit-testing), so nothing else in
    // style-renderer.js/layer-control.js needs to change for this.
    renderer: L.canvas(),
    // Measured directly against a real ~570-feature dataset: a single
    // zoom *level* redraws in ~150-200ms (noticeable but fine), but
    // Leaflet's animated zoom interpolates through every intermediate
    // frame of a multi-level jump (a fast scroll/pinch commonly asks
    // for 3-5 levels at once) - that compounded to 8+ *seconds* with
    // no redraw ever completing, which is what "激重い" actually was.
    // Turning animation off makes every zoom - single or multi-level -
    // take the fast one-shot redraw path instead.
    zoomAnimation: false,
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
