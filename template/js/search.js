/* Cross-layer text search (v0.3.0 task 3-1), lives inside #app-header
   next to the title. Reuses whichever attributes are already visible
   in each layer's ポップアップ項目 picker (ui/field_dialog.py) rather
   than adding a separate field picker for search -
   core/geojson_writer.py never writes hidden fields to the GeoJSON in
   the first place, so Object.keys(properties) already *is* "the
   fields configured as visible" for that layer.

   Matches only features whose OWNING LAYER IS CURRENTLY VISIBLE ON THE
   MAP (checked in #layer-panel) - a result for a hidden layer would
   zoom there but the facility wouldn't actually be on the map, which
   reads as broken. point-list.js's feature table is the opposite
   choice on purpose (any layer, visible or not) since a table has no
   equivalent "found something invisible" confusion.

   Also excludes layers with showPopup === false (データ設定 tab's
   per-layer "ポップアップ表示" checkbox, same layerInteractive flag
   layer-control.js uses to make a layer click/hover-inert): selecting
   a search result normally opens that feature's popup via
   focusFeature(), so surfacing a facility whose layer can never show
   one would zoom the map for no visible result. point-list.js applies
   the same restriction to the feature table for the same reason (a row
   click there does nothing on a non-interactive layer). */
function initSearch(config, map) {
  if (!config.display || !config.display.searchEnabled) return;

  var panel = document.getElementById('search-panel');
  var input = document.getElementById('search-input');
  var dropdown = document.getElementById('search-dropdown');
  var countEl = document.getElementById('search-count');
  var resultsEl = document.getElementById('search-results');
  if (!panel || !input || !resultsEl) return;

  var searchableLayers = (config.layers || []).filter(function (layerConfig) {
    return !!FAG_FEATURES_BY_LAYER[layerConfig.id] && layerConfig.showPopup !== false;
  });
  if (!searchableLayers.length) return; // nothing with attributes to search (e.g. tile-only project)

  panel.classList.remove('fag-hidden');

  var RESULT_LIMIT = 50;
  var DEBOUNCE_MS = 120;
  var debounceTimer = null;

  input.addEventListener('input', function () {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(runSearch, DEBOUNCE_MS);
  });

  function runSearch() {
    var keyword = input.value.trim().toLowerCase();
    if (!keyword) {
      renderResults([]);
      countEl.classList.add('fag-hidden');
      dropdown.classList.add('fag-hidden');
      return;
    }
    renderResults(findMatches(keyword));
    countEl.classList.remove('fag-hidden');
    dropdown.classList.remove('fag-hidden');
  }

  function findMatches(keyword) {
    var matches = [];
    searchableLayers.forEach(function (layerConfig) {
      var byFid = FAG_FEATURES_BY_LAYER[layerConfig.id];
      Object.keys(byFid).forEach(function (fid) {
        var entry = byFid[fid];
        if (!entry.layer._map) return; // layer currently unchecked in #layer-panel
        if (featureMatches(entry.feature.properties, keyword)) {
          matches.push({ layerConfig: layerConfig, entry: entry });
        }
      });
    });
    return matches;
  }

  function featureMatches(props, keyword) {
    props = props || {};
    for (var key in props) {
      if (key === 'label_text' || key === '_fid') continue;
      var value = props[key];
      if (value !== undefined && value !== null &&
        String(value).toLowerCase().indexOf(keyword) !== -1) {
        return true;
      }
    }
    return false;
  }

  function renderResults(matches) {
    countEl.textContent = matches.length + ' 件';
    resultsEl.innerHTML = '';
    resultsEl.classList.toggle('fag-hidden', matches.length === 0);
    if (!matches.length) return;

    var fragment = document.createDocumentFragment();
    matches.slice(0, RESULT_LIMIT).forEach(function (match) {
      fragment.appendChild(buildResultItem(match));
    });
    if (matches.length > RESULT_LIMIT) {
      var more = document.createElement('li');
      more.className = 'fag-search-more';
      more.textContent = 'ほか ' + (matches.length - RESULT_LIMIT) + ' 件 - 検索語を絞り込んでください';
      fragment.appendChild(more);
    }
    resultsEl.appendChild(fragment);
  }

  function buildResultItem(match) {
    var props = match.entry.feature.properties || {};
    var keys = Object.keys(props).filter(function (k) { return k !== 'label_text' && k !== '_fid'; });
    var name = props.label_text || (keys.length ? props[keys[0]] : '') || '(名称なし)';
    var sub = keys
      .filter(function (k) { return String(props[k]) !== String(name); })
      .map(function (k) { return props[k]; })
      .filter(function (v) { return v !== undefined && v !== null && v !== ''; })
      .slice(0, 2)
      .join(' / ');

    var li = document.createElement('li');
    li.className = 'fag-search-result';
    li.innerHTML = '<div class="fag-search-result-name"></div><div class="fag-search-result-sub"></div>';
    li.querySelector('.fag-search-result-name').textContent = name;
    li.querySelector('.fag-search-result-sub').textContent =
      match.layerConfig.label + (sub ? ' ・ ' + sub : '');
    li.addEventListener('click', function () {
      focusFeature(map, match.layerConfig.id, match.entry);
      dropdown.classList.add('fag-hidden');
    });
    return li;
  }

  // Now that the dropdown floats below the header instead of being
  // its own always-visible map panel, it needs to close itself when
  // the user clicks anywhere else (the map, another panel) - a click
  // on the input itself re-opens it via runSearch if there's already
  // a keyword.
  document.addEventListener('click', function (e) {
    if (!panel.contains(e.target)) dropdown.classList.add('fag-hidden');
  });
  input.addEventListener('focus', function () {
    if (input.value.trim()) dropdown.classList.remove('fag-hidden');
  });
}
