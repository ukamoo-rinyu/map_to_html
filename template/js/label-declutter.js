/* Thins out overlapping permanent labels once the map gets dense
   (spec feedback: at low zoom, labels from every visible point stack
   on top of each other and become unreadable). There's no built-in
   Leaflet mechanism for this, so this does a simple screen-space
   pass: walk every labeled marker currently on the map, in
   registration order (see FAG_LABEL_REGISTRY in style-renderer.js),
   and hide a label if its bounding box overlaps one already kept
   visible. Labels aren't removed - they reappear on their own once
   zooming in gives them room again, since the pass reruns on every
   view change. */
function initLabelDeclutter(map) {
  var scheduled = false;
  function run() {
    scheduled = false;
    declutterLabels(map);
  }
  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(run);
  }
  map.on('zoomend moveend layeradd layerremove', schedule);
  schedule();
}

function declutterLabels(map) {
  var mapRect = map.getContainer().getBoundingClientRect();
  var kept = [];
  var pad = 2;

  FAG_LABEL_REGISTRY.forEach(function (marker) {
    if (!marker._map) return; // layer currently toggled off

    var tooltip = marker.getTooltip && marker.getTooltip();
    var el = tooltip && tooltip.getElement && tooltip.getElement();
    if (!el) return;

    // visibility (not display) keeps the box measurable next pass,
    // instead of collapsing to a 0x0 rect while hidden.
    var rect = el.getBoundingClientRect();

    var outOfView = rect.right < mapRect.left || rect.left > mapRect.right ||
      rect.bottom < mapRect.top || rect.top > mapRect.bottom;
    if (outOfView) {
      el.style.visibility = 'hidden';
      return;
    }

    var overlaps = kept.some(function (other) {
      return !(rect.right < other.left - pad || rect.left > other.right + pad ||
        rect.bottom < other.top - pad || rect.top > other.bottom + pad);
    });

    if (overlaps) {
      el.style.visibility = 'hidden';
    } else {
      el.style.visibility = '';
      kept.push(rect);
    }
  });
}
