/* Shareable view (表示設定 tab's リンク共有): the page keeps what the
   reader is looking at in the address bar's #fragment, and a button
   copies that address. Opening the copied link shows the same view:

     #map=15/34.69350/135.50230   zoom / lat / lng
     &layers=1101                 each layer's checkbox, in config order
     &f0=北区,西区                 a narrowed filter dropdown (by index)
     &r=34.69350,135.50230,500    radius search center and radius (m)
     &lang=ja                     language, when the switch is shown

   Only the fragment changes (history.replaceState), so nothing is
   reloaded and the browser history isn't flooded with one entry per
   pan. A link to a page opened from a file only works for people who
   can open that same file (e.g. a shared folder) - the copy message
   says so. */

var FAG_SHARE_WRITE_DELAY_MS = 400;

function fagReadSharedState() {
  var hash = (window.location.hash || '').replace(/^#/, '');
  if (!hash) return null;
  var state = { filters: {} };
  var found = false;
  hash.split('&').forEach(function (part) {
    var eq = part.indexOf('=');
    if (eq < 0) return;
    var key = part.slice(0, eq);
    var value = part.slice(eq + 1);
    if (key === 'map') {
      var view = value.split('/').map(Number);
      if (view.length === 3 && view.every(isFinite)) {
        state.view = { zoom: view[0], center: [view[1], view[2]] };
        found = true;
      }
    } else if (key === 'layers' && /^[01]+$/.test(value)) {
      state.layers = value;
      found = true;
    } else if (/^f\d+$/.test(key)) {
      state.filters[key.slice(1)] = value === '' ? [] : value.split(',').map(fagDecode);
      found = true;
    } else if (key === 'r') {
      var circle = value.split(',').map(Number);
      if (circle.length === 3 && circle.every(isFinite) && circle[2] > 0) {
        state.radius = { center: [circle[0], circle[1]], radius: circle[2] };
        found = true;
      }
    } else if (key === 'lang' && (value === 'ja' || value === 'en')) {
      state.lang = value;
      found = true;
    }
  });
  return found ? state : null;
}

function fagDecode(text) {
  try {
    return decodeURIComponent(text);
  } catch (e) {
    return text;
  }
}

function fagBuildShareHash(map, config) {
  var center = map.getCenter();
  var parts = ['map=' + map.getZoom() + '/' + center.lat.toFixed(5) + '/' + center.lng.toFixed(5)];

  var layerBits = (config.layers || []).map(function (layerConfig) {
    var checkbox = document.getElementById('layer-toggle-' + layerConfig.id);
    var checked = checkbox ? checkbox.checked : !!layerConfig.defaultVisible;
    return checked ? '1' : '0';
  }).join('');
  if (layerBits) parts.push('layers=' + layerBits);

  var filters = fagFilterShareState();
  Object.keys(filters).forEach(function (index) {
    parts.push('f' + index + '=' + filters[index].map(encodeURIComponent).join(','));
  });

  if (FAG_RADIUS_STATE) {
    parts.push('r=' + FAG_RADIUS_STATE.center.lat.toFixed(5) + ',' +
      FAG_RADIUS_STATE.center.lng.toFixed(5) + ',' + FAG_RADIUS_STATE.radius);
  }
  if (config.display.languageToggle) parts.push('lang=' + FAG_LANG);
  return '#' + parts.join('&');
}

function fagWriteShareHash(map, config) {
  var hash = fagBuildShareHash(map, config);
  if (window.location.hash === hash) return;
  try {
    window.history.replaceState(null, '', hash);
  } catch (e) {
    // Some browsers refuse history changes for file:// pages.
    window.location.replace(hash);
  }
}

/* Layers, filters and the radius search from a shared link - the view
   itself is applied earlier, by main.js, before anything is drawn. */
function fagApplySharedState(map, config, state) {
  if (!state) return;
  if (state.layers) {
    (config.layers || []).forEach(function (layerConfig, index) {
      if (index >= state.layers.length) return;
      var checkbox = document.getElementById('layer-toggle-' + layerConfig.id);
      var wanted = state.layers.charAt(index) === '1';
      if (checkbox && checkbox.checked !== wanted) {
        checkbox.checked = wanted;
        checkbox.dispatchEvent(new Event('change', { bubbles: true }));
      }
    });
  }
  fagApplyFilterShareState(state.filters);
  if (state.radius && FAG_RADIUS_API) {
    FAG_RADIUS_API.show(L.latLng(state.radius.center), state.radius.radius);
  }
}

function initShare(config, map) {
  if (!config.display || !config.display.shareLink) return;

  var timer = null;
  function schedule() {
    clearTimeout(timer);
    timer = setTimeout(function () { fagWriteShareHash(map, config); }, FAG_SHARE_WRITE_DELAY_MS);
  }
  map.on('moveend', schedule);
  var listEl = document.getElementById('layer-panel-list');
  if (listEl) listEl.addEventListener('change', schedule);
  ['fag:filterchange', 'fag:radiuschange', 'fag:langchange'].forEach(function (name) {
    document.addEventListener(name, schedule);
  });
  schedule();

  fagAddMapButton(map, {
    className: 'fag-share-btn',
    html: '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">' +
      '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>' +
      '<path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    titleKey: 'share.title',
    onClick: function () {
      clearTimeout(timer);
      fagWriteShareHash(map, config);
      fagCopyText(window.location.href, function (ok) {
        if (ok) {
          fagToast(fagT(window.location.protocol === 'file:' ? 'share.copiedFile' : 'share.copied'), 6000);
        } else {
          window.prompt(fagT('share.copyFailed'), window.location.href);
        }
      });
    },
  });
}

function fagCopyText(text, done) {
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(function () { done(true); }, function () {
      done(fagCopyTextFallback(text));
    });
    return;
  }
  done(fagCopyTextFallback(text));
}

function fagCopyTextFallback(text) {
  var area = document.createElement('textarea');
  area.value = text;
  area.setAttribute('readonly', '');
  area.style.position = 'fixed';
  area.style.opacity = '0';
  document.body.appendChild(area);
  area.select();
  var ok = false;
  try {
    ok = document.execCommand('copy');
  } catch (e) {
    ok = false;
  }
  document.body.removeChild(area);
  return ok;
}
