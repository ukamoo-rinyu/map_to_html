/* Filter bar (表示設定 tab's "フィルターバーを表示する", off by default):
   one checklist dropdown per filter field, under the header - modelled
   on the user's earlier facility map (区/用途/局 dropdowns, each a
   checklist with Select all / Clear).

   Which fields are offered is decided per layer in the plugin (データ設定
   tab, ポップアップ・フィルター項目 設定…) and arrives as
   layers[].filterFields = [{name, key}]: `name` is the QGIS field name,
   `key` the GeoJSON attribute that holds its value (a '_flt_' copy when
   the field is hidden from the popup). Layers sharing a field NAME share
   one dropdown - the common case is one dataset split into several
   legend layers (e.g. 事業予定地/処分検討地/継続保有地), which should
   filter together. A layer without a given field is unaffected by that
   dropdown.

   A feature is shown when, for every dropdown that applies to its
   layer, its value is ticked. Hidden features are removed from their
   L.geoJSON group, so the map, the canvas labels (they skip anything
   not on the map) and rectangle selection follow on their own; search,
   the feature table and CSV/GeoJSON export ask fagFeaturePassesFilter
   and listen for the 'fag:filterchange' event this dispatches. */

/* null until initFilter builds it - fagFeaturePassesFilter then lets
   everything through, so the other modules can call it unconditionally. */
var FAG_FILTER_STATE = null;

var FAG_FILTER_BLANK = '';

function fagFilterValue(props, key) {
  var value = props ? props[key] : undefined;
  if (value === undefined || value === null) return FAG_FILTER_BLANK;
  return String(value);
}

function fagFeaturePassesFilter(layerId, feature) {
  if (!FAG_FILTER_STATE) return true;
  var props = (feature && feature.properties) || {};
  var filters = FAG_FILTER_STATE.filters;
  for (var i = 0; i < filters.length; i++) {
    var key = filters[i].layers[layerId];
    if (key === undefined) continue;
    if (!filters[i].selected[fagFilterValue(props, key)]) return false;
  }
  return true;
}

function initFilter(config, map) {
  var bar = document.getElementById('filter-bar');
  if (!bar || !config.display || !config.display.filterEnabled) return;

  var filters = fagBuildFilters(config.layers || []);
  if (!filters.length) return; // turned on, but no layer picked any filter field

  FAG_FILTER_STATE = { filters: filters };
  var itemsEl = document.getElementById('filter-bar-items');
  var countEl = document.getElementById('filter-bar-count');
  var resetBtn = document.getElementById('filter-bar-reset');
  var toggleBtn = document.getElementById('filter-bar-toggle');
  bar.classList.remove('fag-hidden');

  var scheduled = false;
  function changed() {
    filters.forEach(fagUpdateFilterButton);
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(function () {
      scheduled = false;
      fagApplyFilter(map, config.display);
      fagUpdateFilterCount(countEl);
    });
  }

  filters.forEach(function (filter) {
    itemsEl.appendChild(fagBuildFilterControl(filter, changed));
  });

  resetBtn.addEventListener('click', function () {
    filters.forEach(function (filter) { fagSetAllValues(filter, true); });
    changed();
  });

  // Narrow screens: the dropdowns fold away behind a "Filter" button so
  // they don't eat the map (CSS shows the button only there).
  toggleBtn.addEventListener('click', function () {
    var open = bar.classList.toggle('fag-open');
    toggleBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
  });

  // One menu open at a time; a click anywhere else closes it.
  document.addEventListener('click', function (event) {
    filters.forEach(function (filter) {
      if (!filter.el.contains(event.target)) filter.menu.classList.add('fag-hidden');
    });
  });

  fagUpdateFilterCount(countEl);
  // The bar takes height from the map pane, which Leaflet measured
  // before it appeared.
  setTimeout(function () { map.invalidateSize(); }, 0);
}

/* [{name, label, layers: {layerId: key}, values: [{value, count}],
     selected: {value: true}}], in first-seen order across config.layers. */
function fagBuildFilters(layersConfig) {
  var byName = {};
  var filters = [];
  layersConfig.forEach(function (layerConfig) {
    var byFid = FAG_FEATURES_BY_LAYER[layerConfig.id];
    if (!byFid) return;
    (layerConfig.filterFields || []).forEach(function (field) {
      var filter = byName[field.name];
      if (!filter) {
        filter = {
          name: field.name,
          label: (layerConfig.fieldAliases || {})[field.name] || field.name,
          layers: {}, layerLabels: [], counts: {}, values: [], selected: {},
        };
        byName[field.name] = filter;
        filters.push(filter);
      }
      filter.layers[layerConfig.id] = field.key;
      filter.layerLabels.push(layerConfig.label);
      Object.keys(byFid).forEach(function (fid) {
        var value = fagFilterValue(byFid[fid].feature.properties, field.key);
        filter.counts[value] = (filter.counts[value] || 0) + 1;
      });
    });
  });

  filters.forEach(function (filter) {
    var values = Object.keys(filter.counts);
    var nonBlank = values.filter(function (v) { return v !== FAG_FILTER_BLANK; });
    var numeric = nonBlank.length > 0 && nonBlank.every(function (v) { return !isNaN(Number(v)); });
    nonBlank.sort(function (a, b) {
      return numeric ? Number(a) - Number(b) : a.localeCompare(b, 'ja');
    });
    if (filter.counts[FAG_FILTER_BLANK]) nonBlank.push(FAG_FILTER_BLANK); // blanks last
    filter.values = nonBlank.map(function (v) { return { value: v, count: filter.counts[v] }; });
    filter.values.forEach(function (item) { filter.selected[item.value] = true; });
  });
  return filters;
}

var FAG_FILTER_SEARCH_THRESHOLD = 12;

function fagBuildFilterControl(filter, onChange) {
  var wrap = document.createElement('div');
  wrap.className = 'fag-filter';

  var button = document.createElement('button');
  button.type = 'button';
  button.className = 'fag-filter-btn';
  wrap.appendChild(button);

  var menu = document.createElement('div');
  menu.className = 'fag-filter-menu fag-hidden';
  wrap.appendChild(menu);

  // Which layers this dropdown narrows - without it a reader can't
  // tell why some points ignore the filter (they belong to a layer the
  // plugin didn't give this field as a filter).
  var target = document.createElement('div');
  target.className = 'fag-filter-target';
  target.textContent = 'Applies to: ' + filter.layerLabels.join(', ');
  menu.appendChild(target);

  var search = null;
  if (filter.values.length > FAG_FILTER_SEARCH_THRESHOLD) {
    search = document.createElement('input');
    search.type = 'search';
    search.className = 'fag-filter-search';
    search.placeholder = 'Find a value…';
    menu.appendChild(search);
  }

  var actions = document.createElement('div');
  actions.className = 'fag-filter-actions';
  var allBtn = document.createElement('button');
  allBtn.type = 'button';
  allBtn.textContent = 'Select all';
  var noneBtn = document.createElement('button');
  noneBtn.type = 'button';
  noneBtn.textContent = 'Clear';
  actions.appendChild(allBtn);
  actions.appendChild(noneBtn);
  menu.appendChild(actions);

  var list = document.createElement('div');
  list.className = 'fag-filter-options';
  filter.checkboxes = {};
  filter.values.forEach(function (item) {
    var label = document.createElement('label');
    label.className = 'fag-filter-option';
    var box = document.createElement('input');
    box.type = 'checkbox';
    box.checked = true;
    box.addEventListener('change', function () {
      filter.selected[item.value] = box.checked;
      onChange();
    });
    var text = document.createElement('span');
    text.className = 'fag-filter-option-text';
    text.textContent = item.value === FAG_FILTER_BLANK ? '(blank)' : item.value;
    var count = document.createElement('span');
    count.className = 'fag-filter-option-count';
    count.textContent = item.count;
    label.appendChild(box);
    label.appendChild(text);
    label.appendChild(count);
    list.appendChild(label);
    filter.checkboxes[item.value] = { box: box, label: label, text: text.textContent.toLowerCase() };
  });
  menu.appendChild(list);

  button.addEventListener('click', function () {
    var opening = menu.classList.contains('fag-hidden');
    document.querySelectorAll('.fag-filter-menu').forEach(function (other) {
      other.classList.add('fag-hidden');
    });
    if (opening) {
      menu.classList.remove('fag-hidden');
      // A dropdown near the right edge would spill off screen (narrow
      // windows especially) - shift it back left just enough.
      menu.style.left = '';
      var overflow = menu.getBoundingClientRect().right - (window.innerWidth - 8);
      if (overflow > 0) menu.style.left = (-overflow) + 'px';
      if (search) search.focus();
    }
  });

  // Select all / Clear act on the values currently listed, so typing in
  // the search box first narrows what they apply to.
  function listedValues() {
    return filter.values.map(function (item) { return item.value; }).filter(function (value) {
      return filter.checkboxes[value].label.style.display !== 'none';
    });
  }
  allBtn.addEventListener('click', function () {
    listedValues().forEach(function (value) { fagSetValue(filter, value, true); });
    onChange();
  });
  noneBtn.addEventListener('click', function () {
    listedValues().forEach(function (value) { fagSetValue(filter, value, false); });
    onChange();
  });
  if (search) {
    search.addEventListener('input', function () {
      var query = search.value.trim().toLowerCase();
      Object.keys(filter.checkboxes).forEach(function (value) {
        var entry = filter.checkboxes[value];
        entry.label.style.display = !query || entry.text.indexOf(query) !== -1 ? '' : 'none';
      });
    });
  }

  filter.el = wrap;
  filter.button = button;
  filter.menu = menu;
  fagUpdateFilterButton(filter);
  return wrap;
}

function fagSetValue(filter, value, checked) {
  filter.selected[value] = checked;
  filter.checkboxes[value].box.checked = checked;
}

function fagSetAllValues(filter, checked) {
  filter.values.forEach(function (item) { fagSetValue(filter, item.value, checked); });
}

/* "Label: All" / "Label: <the one value>" / "Label: 3 of 12" / "Label: None",
   highlighted whenever the dropdown is actually narrowing something. */
function fagUpdateFilterButton(filter) {
  var picked = filter.values.filter(function (item) { return filter.selected[item.value]; });
  var summary;
  if (picked.length === filter.values.length) summary = 'All';
  else if (!picked.length) summary = 'None';
  else if (picked.length === 1) summary = picked[0].value === FAG_FILTER_BLANK ? '(blank)' : picked[0].value;
  else summary = picked.length + ' of ' + filter.values.length;
  filter.button.textContent = filter.label + ': ' + summary + ' ▾';
  filter.button.title = filter.label + ': ' + summary + '\nApplies to: ' + filter.layerLabels.join(', ');
  filter.button.classList.toggle('fag-filter-active', picked.length !== filter.values.length);
}

/* Shows/hides every feature of every filtered layer to match the
   current selection, then tells the other modules. */
function fagApplyFilter(map, display) {
  var filteredLayerIds = {};
  FAG_FILTER_STATE.filters.forEach(function (filter) {
    Object.keys(filter.layers).forEach(function (layerId) { filteredLayerIds[layerId] = true; });
  });

  Object.keys(filteredLayerIds).forEach(function (layerId) {
    var group = FAG_GEOJSON_GROUPS[layerId];
    var byFid = FAG_FEATURES_BY_LAYER[layerId] || {};
    if (!group) return;
    Object.keys(byFid).forEach(function (fid) {
      var entry = byFid[fid];
      var top = entry.top || entry.layer;
      var pass = fagFeaturePassesFilter(layerId, entry.feature);
      top.__fagFiltered = !pass;
      var present = group.hasLayer(top);
      if (pass && !present) group.addLayer(top);
      else if (!pass && present) group.removeLayer(top);
    });
  });

  // Thinning (layer-control.js) re-decides which of the remaining
  // markers to show; it skips __fagFiltered ones.
  if (display && display.thinning) fagApplyThinning(map, display.thinning);

  // A popup left open on a feature that just disappeared would float
  // over nothing.
  var popup = map._popup;
  if (popup && popup._source && !popup._source._map) map.closePopup();

  // Hidden features can't stay selected (the export would include
  // things the reader can no longer see).
  if (typeof FAG_SELECTION !== 'undefined') {
    var deselected = false;
    Object.keys(FAG_SELECTION).forEach(function (layerId) {
      var byFid = FAG_FEATURES_BY_LAYER[layerId] || {};
      Object.keys(FAG_SELECTION[layerId]).forEach(function (fid) {
        if (byFid[fid] && !fagFeaturePassesFilter(layerId, byFid[fid].feature)) {
          fagSetSelected(layerId, Number(fid), false);
          deselected = true;
        }
      });
    });
    if (deselected) fagSelectionChanged(map);
  }

  document.dispatchEvent(new Event('fag:filterchange'));
}

/* A badge next to each filtered layer in #layer-panel: a funnel mark on
   every layer the filter bar can narrow (so it's clear which ones it
   applies to and which it doesn't), plus "shown/total" in the accent
   color while it is actually narrowing that layer. */
var FAG_FUNNEL_SVG = '<svg viewBox="0 0 16 16" width="11" height="11" aria-hidden="true">' +
  '<path d="M1 2h14l-5.5 6.5V14l-3-1.5V8.5z" fill="currentColor"/></svg>';

function fagUpdateLayerBadges() {
  var namesByLayer = {};
  FAG_FILTER_STATE.filters.forEach(function (filter) {
    Object.keys(filter.layers).forEach(function (layerId) {
      (namesByLayer[layerId] = namesByLayer[layerId] || []).push(filter.label);
    });
  });
  Object.keys(namesByLayer).forEach(function (layerId) {
    var checkbox = document.getElementById('layer-toggle-' + layerId);
    if (!checkbox || !checkbox.parentNode) return;
    var row = checkbox.parentNode;
    var badge = row.querySelector('.fag-layer-filter-badge');
    if (!badge) {
      badge = document.createElement('span');
      badge.className = 'fag-layer-filter-badge';
      row.appendChild(badge);
    }
    var byFid = FAG_FEATURES_BY_LAYER[layerId] || {};
    var total = 0;
    var shown = 0;
    Object.keys(byFid).forEach(function (fid) {
      total += 1;
      if (fagFeaturePassesFilter(layerId, byFid[fid].feature)) shown += 1;
    });
    var narrowed = shown !== total;
    badge.innerHTML = FAG_FUNNEL_SVG + (narrowed ? '<span>' + shown + '/' + total + '</span>' : '');
    badge.classList.toggle('fag-layer-filter-active', narrowed);
    badge.title = 'Filter: ' + namesByLayer[layerId].join(', ') +
      ' (showing ' + shown + ' of ' + total + ')';
  });
}

/* "Showing 42 of 120" across every layer that has a filter. */
function fagUpdateFilterCount(countEl) {
  fagUpdateLayerBadges();
  if (!countEl) return;
  var shown = 0;
  var total = 0;
  var layerIds = {};
  FAG_FILTER_STATE.filters.forEach(function (filter) {
    Object.keys(filter.layers).forEach(function (layerId) { layerIds[layerId] = true; });
  });
  Object.keys(layerIds).forEach(function (layerId) {
    var byFid = FAG_FEATURES_BY_LAYER[layerId] || {};
    Object.keys(byFid).forEach(function (fid) {
      total += 1;
      if (fagFeaturePassesFilter(layerId, byFid[fid].feature)) shown += 1;
    });
  });
  countEl.textContent = 'Showing ' + shown + ' of ' + total;
}
