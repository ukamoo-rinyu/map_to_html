/* Japanese / English UI text for the published page (spec 10.3).

   The plugin's 表示設定 tab picks the starting language
   (config.display.language: 'auto' = follow the browser, 'ja', 'en')
   and whether readers get a 日本語/EN switch in the header
   (config.display.languageToggle). A reader's own pick is remembered
   in localStorage and wins over the configured default next time.

   Only the page's own wording is translated - layer names, field
   names and values come from the QGIS data and are shown as they are.

   Static text in base.html carries data-i18n (textContent),
   data-i18n-title, data-i18n-placeholder or data-i18n-aria attributes
   and is refreshed by fagApplyI18n. Text other modules build in script
   goes through fagT, and those modules redraw it on the
   'fag:langchange' event this dispatches. Popups are plain HTML bound
   up front, so their translatable bits carry data-i18n too and are
   refreshed whenever one opens (main.js). */

var FAG_I18N = {
  en: {
    'search.placeholder': 'Search by facility name…',
    'search.results': '{0} result(s)',
    'search.more': '{0} more - narrow your search to see them',
    'search.noName': '(no name)',
    'filter.toggle': 'Filter ▾',
    'filter.reset': 'Reset',
    'filter.appliesTo': 'Applies to: {0}',
    'filter.findValue': 'Find a value…',
    'filter.selectAll': 'Select all',
    'filter.clear': 'Clear',
    'filter.blank': '(blank)',
    'filter.all': 'All',
    'filter.none': 'None',
    'filter.someOf': '{0} of {1}',
    'filter.showing': 'Showing {0} of {1}',
    'filter.badge': 'Filter: {0} (showing {1} of {2})',
    'loading': 'Loading…',
    'loading.layers': 'Loading… {0}/{1} layers',
    'thinning.notice': 'Showing some features only — zoom in to see them all',
    'layers.title': 'Layers',
    'layers.toggle': 'Toggle layer panel',
    'legend.other': '(other)',
    'labels.toggle': 'Toggle labels',
    'table.toggle': 'Toggle feature table',
    'table.items': '{0} item(s)',
    'selection.rect': '▭ Select area',
    'selection.rectTitle': 'Drag a rectangle on the map to select features',
    'selection.none': 'None selected',
    'selection.count': '{0} selected',
    'selection.clear': 'Clear',
    'selection.clearTitle': 'Clear the selection',
    'selection.csvSelected': 'CSV (selected)',
    'selection.csvSelectedTitle': 'Export the selected features as CSV',
    'selection.csvAll': 'CSV (layer)',
    'selection.csvAllTitle': 'Export every feature of the layer shown in the table as CSV',
    'selection.geojsonSelected': 'GeoJSON (selected)',
    'selection.geojsonSelectedTitle': 'Export the selected features as GeoJSON',
    'selection.geojsonAll': 'GeoJSON (layer)',
    'selection.geojsonAllTitle': 'Export every feature of the layer shown in the table as GeoJSON',
    'selection.nothing': 'Nothing is selected.',
    'selection.confirmLarge': '{0} features will be exported. This may freeze the page for a few seconds. Continue?',
    'link.googleMaps': 'Google Maps',
    'link.streetView': 'Street View',
    'link.directions': 'Directions',
    'link.nameSearch': 'Search name',
    'link.gsi': 'GSI Maps',
    'lang.switch': '日本語',
    'lang.switchTitle': '日本語で表示',
    'locate.title': 'Show my location',
    'locate.searching': 'Finding your location…',
    'locate.accuracy': 'You are here (within about {0} m)',
    'locate.denied': 'Location access was blocked. Allow it in your browser settings and try again.',
    'locate.unavailable': 'Your location could not be determined.',
    'locate.timeout': 'Finding your location took too long. Please try again.',
    'locate.unsupported': 'This browser cannot report your location.',
    'locate.insecure': 'Location only works when the page is opened over https:// or from a file on this device.',
    'radius.title': 'Radius search',
    'radius.heading': 'Radius search',
    'radius.close': 'Close',
    'radius.radius': 'Radius',
    'radius.hint': 'Click the map to choose the center.',
    'radius.fromLocation': 'From my location',
    'radius.fromCenter': 'From map center',
    'radius.clear': 'Clear',
    'radius.count': '{0} within {1}',
    'radius.countMore': '{0} within {1} (nearest {2} listed)',
    'radius.none': 'Nothing within {0}.',
    'radius.layerOff': 'Only layers shown on the map are searched.',
    'share.title': 'Copy a link to this view',
    'share.copied': 'Link copied. Opening it shows this same view (position, layers and filters).',
    'share.copiedFile': 'Link copied. It only works for people who can open this same file (for example, in a shared folder).',
    'share.copyFailed': 'Copy this link:',
  },
  ja: {
    'search.placeholder': '施設名などで検索…',
    'search.results': '{0} 件',
    'search.more': 'ほか {0} 件 — 検索語を絞り込むと表示されます',
    'search.noName': '（名称なし）',
    'filter.toggle': '絞り込み ▾',
    'filter.reset': 'リセット',
    'filter.appliesTo': '対象: {0}',
    'filter.findValue': '値を検索…',
    'filter.selectAll': 'すべて選択',
    'filter.clear': 'すべて解除',
    'filter.blank': '（空欄）',
    'filter.all': 'すべて',
    'filter.none': 'なし',
    'filter.someOf': '{1} 件中 {0} 件',
    'filter.showing': '{1} 件中 {0} 件を表示',
    'filter.badge': '絞り込み: {0}（{2} 件中 {1} 件を表示）',
    'loading': '読み込み中…',
    'loading.layers': '読み込み中… {0}/{1} レイヤー',
    'thinning.notice': '一部の地物のみ表示中 — 拡大するとすべて表示されます',
    'layers.title': 'レイヤー',
    'layers.toggle': 'レイヤー一覧の開閉',
    'legend.other': '（その他）',
    'labels.toggle': 'ラベルの表示／非表示',
    'table.toggle': '一覧表の開閉',
    'table.items': '{0} 件',
    'selection.rect': '▭ 範囲で選択',
    'selection.rectTitle': '地図上で四角形をドラッグして地物を選択します',
    'selection.none': '選択なし',
    'selection.count': '{0} 件選択中',
    'selection.clear': '選択解除',
    'selection.clearTitle': '選択をすべて解除します',
    'selection.csvSelected': 'CSV（選択分）',
    'selection.csvSelectedTitle': '選択した地物をCSVで保存します',
    'selection.csvAll': 'CSV（レイヤー全体）',
    'selection.csvAllTitle': '一覧表に表示中のレイヤーの全地物をCSVで保存します',
    'selection.geojsonSelected': 'GeoJSON（選択分）',
    'selection.geojsonSelectedTitle': '選択した地物をGeoJSONで保存します',
    'selection.geojsonAll': 'GeoJSON（レイヤー全体）',
    'selection.geojsonAllTitle': '一覧表に表示中のレイヤーの全地物をGeoJSONで保存します',
    'selection.nothing': '何も選択されていません。',
    'selection.confirmLarge': '{0} 件を出力します。数秒間、画面が固まることがあります。続けますか？',
    'link.googleMaps': 'Googleマップ',
    'link.streetView': 'ストリートビュー',
    'link.directions': 'ここへの経路',
    'link.nameSearch': '名称で検索',
    'link.gsi': '地理院地図',
    'lang.switch': 'EN',
    'lang.switchTitle': 'Show in English',
    'locate.title': '現在地を表示',
    'locate.searching': '現在地を取得しています…',
    'locate.accuracy': '現在地（誤差 約 {0} m）',
    'locate.denied': '位置情報の利用が許可されていません。ブラウザの設定で許可してから、もう一度お試しください。',
    'locate.unavailable': '現在地を取得できませんでした。',
    'locate.timeout': '現在地の取得に時間がかかりすぎました。もう一度お試しください。',
    'locate.unsupported': 'このブラウザは現在地の取得に対応していません。',
    'locate.insecure': '現在地は、https:// のページか、この端末上のファイルとして開いたときだけ使えます。',
    'radius.title': '半径検索',
    'radius.heading': '半径検索',
    'radius.close': '閉じる',
    'radius.radius': '半径',
    'radius.hint': '地図をクリックして中心を決めてください。',
    'radius.fromLocation': '現在地から',
    'radius.fromCenter': '地図の中心から',
    'radius.clear': 'クリア',
    'radius.count': '{1} 以内に {0} 件',
    'radius.countMore': '{1} 以内に {0} 件（近い順に {2} 件を表示）',
    'radius.none': '{0} 以内には見つかりませんでした。',
    'radius.layerOff': '地図に表示中のレイヤーだけが対象です。',
    'share.title': 'この表示のリンクをコピー',
    'share.copied': 'リンクをコピーしました。開くと、今と同じ表示（位置・レイヤー・絞り込み）になります。',
    'share.copiedFile': 'リンクをコピーしました。同じファイルを開ける人（共有フォルダなど）だけが使えます。',
    'share.copyFailed': '次のリンクをコピーしてください:',
  },
};

var FAG_LANG = 'en';
var FAG_LANG_STORAGE_KEY = 'fag-map-language';

function fagT(key, params) {
  var table = FAG_I18N[FAG_LANG] || FAG_I18N.en;
  var text = table[key];
  if (text === undefined) text = FAG_I18N.en[key];
  if (text === undefined) return key;
  if (params) {
    text = text.replace(/\{(\d+)\}/g, function (match, index) {
      var value = params[Number(index)];
      return value === undefined ? match : String(value);
    });
  }
  return text;
}

/* "500 m" / "1.5 km" - shared by the radius search and its result list. */
function fagFormatDistance(meters) {
  if (meters >= 1000) {
    var km = meters / 1000;
    return (Math.round(km * 10) / 10) + ' km';
  }
  return Math.round(meters) + ' m';
}

function fagReadStoredLanguage() {
  try {
    var stored = window.localStorage.getItem(FAG_LANG_STORAGE_KEY);
    return stored === 'ja' || stored === 'en' ? stored : null;
  } catch (e) {
    return null; // storage blocked (private window, file:// policy)
  }
}

function fagStoreLanguage(lang) {
  try {
    window.localStorage.setItem(FAG_LANG_STORAGE_KEY, lang);
  } catch (e) { /* not remembered - harmless */ }
}

/* The configured default, unless a shared link (share.js) or the
   reader's earlier pick says otherwise. */
function fagResolveLanguage(display, requested) {
  if (requested === 'ja' || requested === 'en') return requested;
  if (display && display.languageToggle) {
    var stored = fagReadStoredLanguage();
    if (stored) return stored;
  }
  var setting = (display && display.language) || 'en';
  if (setting === 'ja' || setting === 'en') return setting;
  var browser = (navigator.languages && navigator.languages[0]) || navigator.language || '';
  return browser.toLowerCase().indexOf('ja') === 0 ? 'ja' : 'en';
}

function fagApplyI18n(root) {
  root = root || document;
  root.querySelectorAll('[data-i18n]').forEach(function (el) {
    el.textContent = fagT(el.getAttribute('data-i18n'));
  });
  root.querySelectorAll('[data-i18n-title]').forEach(function (el) {
    el.title = fagT(el.getAttribute('data-i18n-title'));
  });
  root.querySelectorAll('[data-i18n-placeholder]').forEach(function (el) {
    el.placeholder = fagT(el.getAttribute('data-i18n-placeholder'));
  });
  root.querySelectorAll('[data-i18n-aria]').forEach(function (el) {
    el.setAttribute('aria-label', fagT(el.getAttribute('data-i18n-aria')));
  });
}

function fagSetLanguage(lang, remember) {
  FAG_LANG = lang === 'ja' ? 'ja' : 'en';
  document.documentElement.lang = FAG_LANG;
  if (remember) fagStoreLanguage(FAG_LANG);
  fagApplyI18n(document);
  document.dispatchEvent(new Event('fag:langchange'));
}

/* Runs before anything else is drawn (main.js), so every module builds
   its text in the right language from the start. */
function initLanguage(display, requested) {
  FAG_LANG = fagResolveLanguage(display, requested);
  document.documentElement.lang = FAG_LANG;
  fagApplyI18n(document);

  var button = document.getElementById('lang-toggle');
  if (!button || !display || !display.languageToggle) return;
  button.classList.remove('fag-hidden');
  button.addEventListener('click', function () {
    fagSetLanguage(FAG_LANG === 'ja' ? 'en' : 'ja', true);
  });
}
