/* Basemap tile sources the user can pick on the 表示設定 tab.

   `maxNativeZoom` is the deepest zoom each provider actually serves
   tiles for. It is NOT the same as Leaflet's `maxZoom`, which is the
   zoom past which a tile layer stops being displayed at all - setting
   that to the provider's depth makes the basemap disappear when the
   user zooms in further, instead of staying visible as upscaled tiles.
   initMap below always takes maxZoom from the map's own limit for
   exactly that reason. */
var BASEMAP_DEFS = {
  // Listed/selected first (v0.5.0): CARTO now requires an API key for
  // any real traffic, so a plain OSM tile source - no key, no quota -
  // is the safer default. CARTO stays available below for anyone who
  // already has a key/plan for it.
  osm: {
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    options: {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      subdomains: 'abc',
      maxNativeZoom: 19,
    },
  },
  gsi_photo: {
    url: 'https://cyberjapandata.gsi.go.jp/xyz/seamlessphoto/{z}/{x}/{y}.jpg',
    options: {
      attribution: '&copy; <a href="https://maps.gsi.go.jp/development/ichiran.html">国土地理院</a>',
      maxNativeZoom: 18,
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
  carto_light: {
    url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    options: {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
      subdomains: 'abcd',
      maxNativeZoom: 20,
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
    // v0.5.0: re-enabled (spec feedback: every zoom step "jump-cut"
    // instead of transitioning, which read as choppy). This was
    // turned off earlier after profiling an 8+ second hang on a real
    // ~570-feature dataset - but that was a multi-level *animated*
    // jump; Leaflet's own zoomAnimationThreshold (its default is 4,
    // kept explicit here) already makes any zoom bigger than that an
    // instant jump with no animation at all, regardless of this flag,
    // so the specific case that hung stays just as fast as before.
    // Ordinary single-step zooming (scroll wheel, +/- buttons,
    // double-click) is what actually gets smoother.
    // NOT yet re-verified against a real large dataset since the
    // original hang was found - if zooming feels heavy again after
    // this change, that threshold is the first thing to reconsider.
    zoomAnimation: true,
    zoomAnimationThreshold: 4,
  });

  // v0.3.0 task 2-2: whether to publish a basemap at all is decided in
  // the plugin BEFORE generating the site (表示設定 tab's "背景地図を
  // 表示する" checkbox), not as a runtime on/off toggle in the output
  // itself - so when disabled, no tile layer is created here at all.
  if (display.basemapEnabled !== false) {
    var basemap = BASEMAP_DEFS[display.basemap] || BASEMAP_DEFS.osm;
    // maxZoom is applied AFTER the basemap's own options, not before -
    // spreading the definition last let it clamp the display limit
    // below the map's, which is the same "basemap disappears when you
    // zoom all the way in" failure the XYZ layers had. The provider's
    // real tile depth is expressed as maxNativeZoom instead, so the
    // deepest tiles are upscaled rather than the layer being dropped.
    L.tileLayer(basemap.url, Object.assign({}, basemap.options, {
      minZoom: map.getMinZoom(),
      maxZoom: map.getMaxZoom(),
    })).addTo(map);
  }

  // Appended, not replacing the basemap's own attribution() above -
  // that one's required by its provider's terms of use (spec 出力設定
  // "帰属表示" adds the user's own credit alongside it, not instead).
  if (display.attribution) {
    map.attributionControl.addAttribution(display.attribution);
  }

  return map;
}
