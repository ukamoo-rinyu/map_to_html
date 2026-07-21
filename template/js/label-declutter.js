/* Thins out overlapping permanent labels once the map gets dense
   (spec feedback: at low zoom, labels from every visible point stack
   on top of each other and become unreadable). There's no built-in
   Leaflet mechanism for this, so this does a simple screen-space
   pass: walk every labeled marker currently on the map, in
   registration order (see FAG_LABEL_REGISTRY in style-renderer.js),
   measuring its tooltip's bounding box exactly once per pass and
   hiding it if that box overlaps one already kept visible.

   Markers flagged `fagLabelMultiDirection` (points that
   spreadOverlappingPointsAcrossLayers had to nudge apart from an
   exact-duplicate coordinate - see layer-control.js) get a second
   chance: instead of only ever being hidden outright when they collide
   with a neighbor at their default position (directly above the
   marker), the *same already-measured box* is checked again shifted
   right/left/below (FAG_NUDGE_OFFSETS) before giving up. Critically
   this reuses the one `getBoundingClientRect()` call via simple
   arithmetic - it does NOT re-measure or rebind the tooltip per
   direction. An earlier version tried every direction by unbinding and
   rebinding the tooltip (destroying/recreating its DOM node) and
   re-measuring each time; profiled against this app's real ~570-feature
   dataset (234 of ~526 labels turned out to need multi-direction - far
   from a rare case) that took 4+ *seconds* per pass. This version's
   per-marker cost is one measurement either way, so this doesn't
   regress the fast path.

   Labels aren't removed - they reappear (back at their default
   position first) on their own once zooming in gives them room again,
   since the pass reruns on every view change. */
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
  // Generous padding (in map-bounds fractions) so a label anchored near
  // the edge of the viewport, whose text extends further than its point,
  // isn't pre-filtered out before it even gets a chance to be measured.
  var viewBounds = map.getBounds().pad(0.25);

  FAG_LABEL_REGISTRY.forEach(function (marker) {
    if (!marker._map) return; // layer currently toggled off

    // Skip the expensive tooltip DOM measurement entirely for markers
    // nowhere near the current view - checking a plain lat/lng against
    // the map bounds is cheap, unlike getBoundingClientRect (forces a
    // layout). With several hundred labels on a dataset-wide layer,
    // doing that for every one of them on every pan/zoom (most of
    // which are off-screen at any given time) was the main cause of
    // panning/zooming feeling sluggish (spec feedback: "たどり着けない"
    // trying to navigate a large dataset).
    if (marker.getLatLng && !viewBounds.contains(marker.getLatLng())) {
      var offscreenTooltip = marker.getTooltip && marker.getTooltip();
      var offscreenEl = offscreenTooltip && offscreenTooltip.getElement && offscreenTooltip.getElement();
      if (offscreenEl) offscreenEl.style.visibility = 'hidden';
      return;
    }

    var tooltip = marker.getTooltip && marker.getTooltip();
    var el = tooltip && tooltip.getElement && tooltip.getElement();
    if (!el) return;

    // Clear any nudge applied on a previous pass before measuring, so
    // this pass's collision check starts from the tooltip's true
    // default position (directly above the marker) rather than
    // compounding an old offset - Leaflet re-applies its own base
    // transform on every reposition, but our nudge is layered on top
    // via a separate wrapping element (see fagNudgeLabelElement) that
    // Leaflet doesn't touch, so it has to be reset explicitly here.
    fagNudgeLabelElement(el, 0, 0);
    var baseRect = el.getBoundingClientRect();

    var candidates = [{ dx: 0, dy: 0 }];
    if (marker.fagLabelMultiDirection) {
      var dx = baseRect.width * 0.85 + 6;
      var dy = baseRect.height * 1.3 + 4;
      candidates.push({ dx: dx, dy: 0 }, { dx: -dx, dy: 0 }, { dx: 0, dy: dy });
    }

    var placed = false;
    for (var i = 0; i < candidates.length; i++) {
      var off = candidates[i];
      var rect = {
        left: baseRect.left + off.dx, right: baseRect.right + off.dx,
        top: baseRect.top + off.dy, bottom: baseRect.bottom + off.dy,
      };

      var outOfView = rect.right < mapRect.left || rect.left > mapRect.right ||
        rect.bottom < mapRect.top || rect.top > mapRect.bottom;
      if (outOfView) continue;

      var overlaps = kept.some(function (other) {
        return !(rect.right < other.left - pad || rect.left > other.right + pad ||
          rect.bottom < other.top - pad || rect.top > other.bottom + pad);
      });

      if (!overlaps) {
        fagNudgeLabelElement(el, off.dx, off.dy);
        el.style.visibility = '';
        kept.push(rect);
        placed = true;
        break;
      }
    }

    if (!placed) el.style.visibility = 'hidden';
  });
}

/* Applies (or clears, with dx=dy=0) a plain pixel offset on top of
   wherever Leaflet itself positioned the tooltip - a single style write,
   not a tooltip rebind. Leaflet repositions `el` directly on every
   pan/zoom, so this must be re-applied (or re-cleared) every
   declutterLabels pass rather than set once. */
function fagNudgeLabelElement(el, dx, dy) {
  el.style.marginLeft = dx ? dx + 'px' : '';
  el.style.marginTop = dy ? dy + 'px' : '';
}
