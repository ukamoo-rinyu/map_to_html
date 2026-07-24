/* Per-layer feature attribute table (v0.3.0 task 3-2). Reuses
   whichever fields are visible in each layer's ポップアップ項目
   picker as the table's columns - same reasoning as search.js:
   core/geojson_writer.py never writes a hidden field to the GeoJSON at
   all, so Object.keys(feature.properties) already *is* "the fields
   configured as visible" for that layer, with no separate column
   picker needed here.

   Rendering is virtualized by hand (only the rows currently scrolled
   into view actually exist in the DOM) rather than laying out one
   <div> per feature up front - label-layer.js's canvas rewrite hit
   exactly this same wall at real-dataset scale (1,530 permanent
   DOM tooltips made every zoom step block for ~1 second), and a plain
   table of 1,000+ rows risks the same kind of first-paint/reflow cost
   for no benefit, since only ~10-15 rows are ever visible at once. */

var FAG_TABLE_ROW_HEIGHT = 30;

function initFeatureTable(config, map) {
  if (!config.display || !config.display.featureTableEnabled) return;

  var panel = document.getElementById('feature-table-panel');
  var select = document.getElementById('feature-table-layer-select');
  var countEl = document.getElementById('feature-table-count');
  var toggleBtn = document.getElementById('feature-table-toggle');
  var scrollEl = document.getElementById('feature-table-scroll');
  var colsEl = document.getElementById('feature-table-cols');
  var spacerEl = document.getElementById('feature-table-spacer');
  var rowsEl = document.getElementById('feature-table-rows');
  if (!panel || !select || !scrollEl) return;

  var tableLayers = (config.layers || []).filter(function (layerConfig) {
    return !!FAG_FEATURES_BY_LAYER[layerConfig.id];
  });
  if (!tableLayers.length) return; // nothing with attributes to list (e.g. tile-only project)

  panel.classList.remove('fag-hidden');

  tableLayers.forEach(function (layerConfig) {
    var opt = document.createElement('option');
    opt.value = layerConfig.id;
    opt.textContent = layerConfig.label;
    select.appendChild(opt);
  });

  var state = { layerId: null, columns: [], colWidths: [], rows: [] };

  select.addEventListener('change', function () {
    loadLayer(select.value);
  });

  if (toggleBtn) {
    toggleBtn.addEventListener('click', function () {
      panel.classList.toggle('fag-collapsed');
      // #feature-table-scroll has zero height while .fag-collapsed
      // hides it, so any render attempted before now would have laid
      // out ~0 rows - refresh once the real viewport size is back.
      if (!panel.classList.contains('fag-collapsed')) scheduleRowRender();
    });
  }

  var scrollScheduled = false;
  function scheduleRowRender() {
    if (scrollScheduled) return;
    scrollScheduled = true;
    requestAnimationFrame(function () {
      scrollScheduled = false;
      renderVisibleRows();
    });
  }
  scrollEl.addEventListener('scroll', scheduleRowRender);
  window.addEventListener('resize', scheduleRowRender);

  loadLayer(tableLayers[0].id);

  function loadLayer(layerId) {
    var byFid = FAG_FEATURES_BY_LAYER[layerId] || {};
    // Object.keys on a plain object with numeric-looking keys is
    // returned in ascending numeric order by the JS spec, which
    // happens to already be _fid (registration) order - sorting
    // again would be redundant, but doing it explicitly here doesn't
    // rely on that spec detail holding for whatever iterates this next.
    var fids = Object.keys(byFid).map(Number).sort(function (a, b) { return a - b; });
    var rows = fids.map(function (fid) { return byFid[fid]; });

    var columns = rows.length
      ? Object.keys(rows[0].feature.properties || {}).filter(function (key) {
        return key !== 'label_text' && key !== '_fid';
      })
      : [];

    state.layerId = layerId;
    state.rows = rows;
    state.columns = columns;
    // Width from the column NAME only (not scanning every value across
    // possibly 1,000+ rows just to auto-fit) - long cell values simply
    // ellipsis, same trade-off as the rest of this app's popups/labels.
    state.colWidths = columns.map(function (col) {
      return Math.min(260, Math.max(90, col.length * 9 + 24));
    });

    countEl.textContent = rows.length + ' 件';
    renderHeader();
    spacerEl.style.height = (rows.length * FAG_TABLE_ROW_HEIGHT) + 'px';
    scrollEl.scrollTop = 0;
    renderVisibleRows();
  }

  function renderHeader() {
    colsEl.innerHTML = '';
    var fragment = document.createDocumentFragment();
    state.columns.forEach(function (col, i) {
      fragment.appendChild(buildCell(col, state.colWidths[i]));
    });
    colsEl.appendChild(fragment);
  }

  function renderVisibleRows() {
    // The sticky header row occupies exactly one row's worth of space
    // ahead of the spacer in normal flow (see style.css - same
    // .fag-table-row height on both) - scrollTop counts that space
    // too, so it has to be subtracted before mapping scroll position
    // to a row index, or the very first bit of scrolling would be
    // mistaken for having scrolled past row 0.
    var headerHeight = FAG_TABLE_ROW_HEIGHT;
    var viewportHeight = Math.max(0, scrollEl.clientHeight - headerHeight);
    var scrollTop = Math.max(0, scrollEl.scrollTop - headerHeight);
    var totalRows = state.rows.length;

    var buffer = 6;
    var startIndex = Math.max(0, Math.floor(scrollTop / FAG_TABLE_ROW_HEIGHT) - buffer);
    var visibleCount = Math.ceil(viewportHeight / FAG_TABLE_ROW_HEIGHT) + buffer * 2;
    var endIndex = Math.min(totalRows, startIndex + visibleCount);

    rowsEl.style.transform = 'translateY(' + (startIndex * FAG_TABLE_ROW_HEIGHT) + 'px)';
    rowsEl.innerHTML = '';
    var fragment = document.createDocumentFragment();
    for (var i = startIndex; i < endIndex; i++) {
      fragment.appendChild(buildRow(state.rows[i]));
    }
    rowsEl.appendChild(fragment);
  }

  function buildRow(entry) {
    var props = entry.feature.properties || {};
    var row = document.createElement('div');
    row.className = 'fag-table-row';
    row.style.height = FAG_TABLE_ROW_HEIGHT + 'px';
    var fragment = document.createDocumentFragment();
    state.columns.forEach(function (col, i) {
      var value = props[col];
      fragment.appendChild(buildCell(
        value === undefined || value === null ? '' : String(value), state.colWidths[i]
      ));
    });
    row.appendChild(fragment);
    row.addEventListener('click', function () {
      focusFeature(map, state.layerId, entry);
    });
    return row;
  }

  function buildCell(text, width) {
    var cell = document.createElement('span');
    cell.className = 'fag-table-cell';
    cell.style.width = width + 'px';
    cell.textContent = text;
    return cell;
  }
}
