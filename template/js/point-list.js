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
var FAG_TABLE_MIN_COL_WIDTH = 48;
var FAG_TABLE_MAX_AUTO_COL_WIDTH = 320;

// Column auto-fit needs real pixel text width, not a per-character
// estimate - a fixed px/char guess (the original approach) is tuned for
// Latin glyphs and badly undercounts full-width CJK text, so a column
// like "第二種住居地域" came out narrower than its own rendered text and
// spilled into the row below. ctx.measureText gives the actual width
// for whatever font is really in effect (same technique label-layer.js
// uses for its own text sizing). Fonts are resolved lazily from the
// live DOM the first time a layer loads, not hardcoded, so a theme's
// custom font_family (main.js::applyTheme) is measured correctly too.
var fagTableMeasureCtx = document.createElement('canvas').getContext('2d');
var fagTableNormalFont = null;
var fagTableBoldFont = null;
function fagTableTextWidth(text, bold) {
  if (!fagTableNormalFont) {
    var cs = getComputedStyle(document.getElementById('feature-table-scroll') || document.body);
    fagTableNormalFont = cs.fontSize + ' ' + cs.fontFamily;
    fagTableBoldFont = '700 ' + cs.fontSize + ' ' + cs.fontFamily;
  }
  fagTableMeasureCtx.font = bold ? fagTableBoldFont : fagTableNormalFont;
  return fagTableMeasureCtx.measureText(text).width;
}

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

  // showPopup === false means the layer's own マップ上でのクリック/ホバーが
  // 無効化されている（layer-control.jsのlayerInteractive）ので、一覧表から
  // その行をクリックしても何も起きない = 一覧表に出す意味がない。search.jsも
  // 同じ理由で同じ判定を使っている。
  var tableLayers = (config.layers || []).filter(function (layerConfig) {
    return !!FAG_FEATURES_BY_LAYER[layerConfig.id] && layerConfig.showPopup !== false;
  });
  if (!tableLayers.length) return; // nothing with attributes to list (e.g. tile-only project)

  panel.classList.remove('fag-hidden');

  tableLayers.forEach(function (layerConfig) {
    var opt = document.createElement('option');
    opt.value = layerConfig.id;
    opt.textContent = layerConfig.label;
    select.appendChild(opt);
  });

  var state = {
    layerId: null, columns: [], colWidths: [], rows: [],
    sortColumn: null, sortDirection: 1 // 1 = 昇順, -1 = 降順
  };

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
    // Sort criteria don't carry over across a layer switch - each layer
    // has its own column set, so a previously-sorted column name may not
    // even exist on the new layer.
    state.sortColumn = null;
    state.sortDirection = 1;
    // Auto-fit from both the column name AND its longest value (capped
    // at FAG_TABLE_MAX_AUTO_COL_WIDTH - a single outlier value shouldn't
    // blow up the whole column; the user can still drag it wider via
    // the resize handle). Measuring every row's real text width is
    // still cheap at 1,000+ rows (measureText is pure math, no
    // rendering), unlike actually laying out that many rows up front.
    // The header is measured in bold since that's how it actually
    // renders (.fag-table-row-head), and a little extra room over the
    // plain-cell formula so the sort arrow (header only) doesn't crowd
    // the column name.
    state.colWidths = columns.map(function (col) {
      var maxWidth = fagTableTextWidth(col, true);
      for (var i = 0; i < rows.length; i++) {
        var value = (rows[i].feature.properties || {})[col];
        if (value === undefined || value === null) continue;
        var width = fagTableTextWidth(String(value), false);
        if (width > maxWidth) maxWidth = width;
      }
      return Math.min(FAG_TABLE_MAX_AUTO_COL_WIDTH, Math.max(FAG_TABLE_MIN_COL_WIDTH + 42, maxWidth + 34));
    });

    countEl.textContent = rows.length + ' item' + (rows.length === 1 ? '' : 's');
    renderHeader();
    spacerEl.style.height = (rows.length * FAG_TABLE_ROW_HEIGHT) + 'px';
    scrollEl.scrollTop = 0;
    renderVisibleRows();
  }

  // Column header click = sort by that column. Only two states (asc/desc,
  // spec: "昇順・降順のみでよい") - no third "back to original order" click,
  // clicking a different column just starts that column at ascending.
  function sortByColumn(col) {
    if (state.sortColumn === col) {
      state.sortDirection = -state.sortDirection;
    } else {
      state.sortColumn = col;
      state.sortDirection = 1;
    }
    state.rows = state.rows.slice().sort(function (a, b) {
      var aVal = (a.feature.properties || {})[col];
      var bVal = (b.feature.properties || {})[col];
      return state.sortDirection * compareValues(aVal, bVal);
    });
    renderHeader();
    scrollEl.scrollTop = 0;
    renderVisibleRows();
  }

  // Numeric compare when both sides parse as numbers (so 2 sorts before
  // 10, not after it as plain strings would), otherwise locale-aware
  // string compare.
  function compareValues(a, b) {
    var aStr = (a === undefined || a === null) ? '' : String(a);
    var bStr = (b === undefined || b === null) ? '' : String(b);
    var aNum = aStr === '' ? NaN : Number(aStr);
    var bNum = bStr === '' ? NaN : Number(bStr);
    if (!isNaN(aNum) && !isNaN(bNum)) return aNum - bNum;
    return aStr.localeCompare(bStr, 'ja');
  }

  function renderHeader() {
    colsEl.innerHTML = '';
    var fragment = document.createDocumentFragment();
    state.columns.forEach(function (col, i) {
      fragment.appendChild(buildHeaderCell(col, state.colWidths[i]));
    });
    colsEl.appendChild(fragment);
  }

  function buildHeaderCell(col, width) {
    var cell = document.createElement('span');
    cell.className = 'fag-table-cell fag-table-cell-head';
    cell.style.width = width + 'px';
    var label = document.createElement('span');
    label.className = 'fag-table-head-label';
    label.textContent = col;
    cell.appendChild(label);
    if (state.sortColumn === col) {
      var arrow = document.createElement('span');
      arrow.className = 'fag-table-sort-arrow';
      arrow.textContent = state.sortDirection === 1 ? '▲' : '▼';
      cell.appendChild(arrow);
    }
    cell.addEventListener('click', function () { sortByColumn(col); });

    var handle = document.createElement('span');
    handle.className = 'fag-table-col-resize';
    handle.addEventListener('mousedown', function (e) { startColumnResize(e, col); });
    handle.addEventListener('click', function (e) { e.stopPropagation(); });
    cell.appendChild(handle);

    return cell;
  }

  // Drag-to-resize (spec feedback: auto-fit still ellipsis-truncates
  // whatever value is longer than FAG_TABLE_MAX_AUTO_COL_WIDTH allows -
  // a manual override covers that outlier without widening every other
  // column to match it). Writes into the same state.colWidths the
  // auto-fit sizing produces, so a manual resize sticks until the next
  // layer switch recomputes widths from scratch.
  function startColumnResize(e, col) {
    e.preventDefault();
    e.stopPropagation();
    var index = state.columns.indexOf(col);
    if (index === -1) return;
    var startX = e.clientX;
    var startWidth = state.colWidths[index];

    function onMove(moveEvent) {
      state.colWidths[index] = Math.max(FAG_TABLE_MIN_COL_WIDTH, startWidth + (moveEvent.clientX - startX));
      renderHeader();
      renderVisibleRows();
    }
    function onUp() {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    }
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
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
    var fid = props._fid;
    var row = document.createElement('div');
    row.className = 'fag-table-row';
    // The map->list half of the spec's two-way selection sync (item 9):
    // rows are recycled by the virtual scroller, so the selected state
    // is re-read from FAG_SELECTION on every build rather than being
    // stored on the element.
    if (typeof fagIsSelected === 'function' && fagIsSelected(state.layerId, fid)) {
      row.className += ' fag-row-selected';
    }
    row.style.height = FAG_TABLE_ROW_HEIGHT + 'px';
    var fragment = document.createDocumentFragment();
    state.columns.forEach(function (col, i) {
      var value = props[col];
      fragment.appendChild(buildCell(
        value === undefined || value === null ? '' : String(value), state.colWidths[i]
      ));
    });
    row.appendChild(fragment);
    row.addEventListener('click', function (event) {
      // The list->map half: Ctrl/Cmd/Shift-click selects without moving
      // the map, so a multi-row selection can be built up by scrolling
      // the list. A plain click keeps its original "zoom to it and open
      // its popup" behavior, and selects it too.
      var additive = event.ctrlKey || event.metaKey || event.shiftKey;
      if (typeof window.fagToggleSelectionFromTable === 'function' && fid !== undefined) {
        window.fagToggleSelectionFromTable(state.layerId, fid, additive);
      }
      if (!additive) focusFeature(map, state.layerId, entry);
    });
    return row;
  }

  // Repaint row highlighting when the selection changes on the map.
  if (typeof fagOnSelectionChange === 'function') {
    fagOnSelectionChange(scheduleRowRender);
  }

  function buildCell(text, width) {
    var cell = document.createElement('span');
    cell.className = 'fag-table-cell';
    cell.style.width = width + 'px';
    cell.textContent = text;
    return cell;
  }
}
