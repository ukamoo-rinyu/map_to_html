/* Facility list panel (spec 3.1 Tab 3 "表示中施設一覧表示", fixed ON in
   phase 1). Clicking a row pans/zooms the map to that facility and
   opens its popup. */
function initPointList(config, sitesData) {
  updatePointList(sitesData.features || []);
}

function updatePointList(features) {
  var listEl = document.getElementById('facility-list');
  var emptyEl = document.getElementById('list-empty');
  var countEl = document.getElementById('list-count');
  if (!listEl) return;

  listEl.innerHTML = '';
  countEl.textContent = features.length;
  emptyEl.classList.toggle('fag-hidden', features.length > 0);

  var config = FAG.config;
  var fragment = document.createDocumentFragment();

  features.forEach(function (feature) {
    var props = feature.properties || {};
    var id = config.fields.idField ? props[config.fields.idField] : undefined;
    var name = props[config.fields.nameField] || '(no name)';
    var sub = (config.fields.listFields || [])
      .map(function (f) { return props[f.key]; })
      .filter(function (v) { return v !== undefined && v !== null && v !== ''; })
      .slice(0, 2)
      .join(' / ');

    var item = document.createElement('li');
    item.className = 'fag-list-item';
    item.innerHTML = '<div class="fag-list-item-name"></div><div class="fag-list-item-sub"></div>';
    item.querySelector('.fag-list-item-name').textContent = name;
    item.querySelector('.fag-list-item-sub').textContent = sub;
    item.addEventListener('click', function () {
      focusFacility(id);
    });
    fragment.appendChild(item);
  });

  listEl.appendChild(fragment);
}

function focusFacility(id) {
  var marker = FAG.markersById[id];
  if (!marker) return;
  var latlng = marker.getLatLng ? marker.getLatLng() : null;
  if (latlng) {
    FAG.map.setView(latlng, Math.max(FAG.map.getZoom(), 16));
  }
  if (marker.openPopup) marker.openPopup();

  document.querySelectorAll('.fag-list-item.is-active').forEach(function (el) {
    el.classList.remove('is-active');
  });
}
