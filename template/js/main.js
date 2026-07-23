/* Entry point: wires the modules above together once config/layersData/
   layersStyleData have been loaded (either inlined or via <script
   src>, spec 5.3). Every layer the user added is shown with its own
   QGIS symbology (qgis2web-style "show everything" model) - search
   and the facility list are a deliberately deferred next step. */
var FAG = {
  map: null,
  config: null,
  layersData: null,
  layersStyleData: null,
};

/* Overrides the CSS custom properties style.css defines for the
   header (--header-bg/--header-text/--font-family), when the user
   picked a title/header color or font on the 出力設定 tab. Left
   unset (null/undefined) falls through to style.css's own defaults,
   so an unconfigured install looks exactly as before. */
function applyTheme(theme) {
  if (!theme) return;
  var root = document.documentElement;
  if (theme.headerBgColor) root.style.setProperty('--header-bg', theme.headerBgColor);
  if (theme.titleColor) root.style.setProperty('--header-text', theme.titleColor);
  if (theme.fontFamily) {
    root.style.setProperty(
      '--font-family',
      '"' + theme.fontFamily + '", "Noto Sans JP", "Hiragino Sans", "Yu Gothic", sans-serif'
    );
  }
}

(function () {
  FAG.config = config;
  FAG.layersData = layersData;
  FAG.layersStyleData = layersStyleData;

  document.title = config.meta.title;
  document.getElementById('app-title').textContent = config.meta.title;
  applyTheme(config.theme);

  FAG.map = initMap(config);
  applyDisplaySettings(FAG.map, layersData, config.display);
  initLayerControl(FAG.map, config.layers, layersData, layersStyleData, config.display.popupTrigger);
  initLabelLayer(FAG.map);

  // Panels/CSS can change the map container size after Leaflet measured it once.
  setTimeout(function () { FAG.map.invalidateSize(); }, 150);
})();
