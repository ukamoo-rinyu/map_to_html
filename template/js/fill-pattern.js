/* Hatch / pattern polygon fills (spec item 10).

   SVG <pattern> is the only practical way to draw these, and it can't
   be used with Leaflet's Canvas renderer - so a layer whose symbology
   needs a pattern is rendered with L.svg() while every other layer
   keeps the Canvas renderer that makes large point layers fast. The
   spec's own recommendation, and it holds up in practice because
   hatched layers (zoning, districts, study areas) are almost always
   small feature counts.

   Pattern-rendered layers go in a dedicated map pane sitting just
   below the normal overlay pane. Without that, an SVG layer and the
   shared canvas are sibling elements in one pane and their stacking
   depends on DOM creation order rather than the configured layer
   order - so a hatched background polygon could end up over the points
   and take their clicks. Pinning it below makes the outcome
   predictable: hatched areas read as the background they almost always
   are. */

var FAG_PATTERN_PANE = 'fagPatternPane';
var FAG_PATTERN_RENDERER = null;
var FAG_PATTERN_DEFS = null;
var FAG_PATTERN_IDS = {};
var FAG_PATTERN_SEQ = 0;

function fagStyleNeedsPattern(styleData) {
  if (!styleData) return false;
  if (styleData.defaultStyle && styleData.defaultStyle.fill &&
      styleData.defaultStyle.fill.fillPattern) return true;
  var byCategory = styleData.byCategory;
  if (!byCategory) return false;
  return Object.keys(byCategory).some(function (field) {
    var table = byCategory[field];
    return Object.keys(table).some(function (value) {
      return table[value].fill && table[value].fill.fillPattern;
    });
  });
}

/* The shared L.svg() renderer for every pattern-filled layer, created
   lazily so a project without any hatched polygon never pays for it. */
function fagPatternRenderer(map) {
  if (FAG_PATTERN_RENDERER) return FAG_PATTERN_RENDERER;
  if (!map.getPane(FAG_PATTERN_PANE)) {
    var pane = map.createPane(FAG_PATTERN_PANE);
    // Just under the default overlayPane's 400.
    pane.style.zIndex = 395;
  }
  FAG_PATTERN_RENDERER = L.svg({ pane: FAG_PATTERN_PANE });
  FAG_PATTERN_RENDERER.addTo(map);
  return FAG_PATTERN_RENDERER;
}

function fagPatternDefs(map) {
  if (FAG_PATTERN_DEFS && FAG_PATTERN_DEFS.ownerSVGElement) return FAG_PATTERN_DEFS;
  var renderer = fagPatternRenderer(map);
  var svg = renderer._container;
  if (!svg) return null;
  FAG_PATTERN_DEFS = svg.querySelector('defs');
  if (!FAG_PATTERN_DEFS) {
    FAG_PATTERN_DEFS = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
    svg.insertBefore(FAG_PATTERN_DEFS, svg.firstChild);
  }
  return FAG_PATTERN_DEFS;
}

/* Geometry of each Qt brush style, as a tile size plus the lines drawn
   across it. Angles are applied with patternTransform, so the line
   definitions themselves stay axis-aligned and simple.
   `dense1`..`dense7` are Qt's stipples, densest first - approximated
   with a cross-hatch whose spacing widens as the density drops, which
   reads the same at map scale without needing seven dot rasters. */
function fagPatternGeometry(type) {
  switch (type) {
    case 'hor': return { size: 8, lines: ['h'], angle: 0 };
    case 'ver': return { size: 8, lines: ['v'], angle: 0 };
    case 'cross': return { size: 8, lines: ['h', 'v'], angle: 0 };
    case 'bdiag': return { size: 8, lines: ['h'], angle: -45 };
    case 'fdiag': return { size: 8, lines: ['h'], angle: 45 };
    case 'diagcross': return { size: 8, lines: ['h', 'v'], angle: 45 };
    case 'dense1': return { size: 3, lines: ['h', 'v'], angle: 0 };
    case 'dense2': return { size: 4, lines: ['h', 'v'], angle: 0 };
    case 'dense3': return { size: 5, lines: ['h', 'v'], angle: 0 };
    case 'dense4': return { size: 6, lines: ['h', 'v'], angle: 0 };
    case 'dense5': return { size: 8, lines: ['h', 'v'], angle: 0 };
    case 'dense6': return { size: 10, lines: ['h', 'v'], angle: 0 };
    case 'dense7': return { size: 13, lines: ['h', 'v'], angle: 0 };
    default: return null;
  }
}

/* The <pattern> element's inner markup for a resolved pattern spec.
   Returns null for an unrecognized type so the caller falls back to a
   plain fill rather than drawing nothing. */
function fagPatternBody(pattern, color, opacity) {
  var stroke = ' stroke="' + color + '" stroke-opacity="' + opacity + '"';
  if (pattern.type === 'lines') {
    // 線パターン塗りつぶし: spacing and width come straight from QGIS.
    var size = Math.max(pattern.spacing || 8, 1);
    var width = pattern.lineWidth || 1;
    return {
      size: size,
      angle: pattern.angle || 0,
      // One horizontal line per tile; patternTransform rotates it.
      markup: '<line x1="0" y1="' + (size / 2) + '" x2="' + size + '" y2="' + (size / 2) + '"' +
        stroke + ' stroke-width="' + width + '"/>',
    };
  }
  var geometry = fagPatternGeometry(pattern.type);
  if (!geometry) return null;
  var s = geometry.size;
  var w = pattern.type.indexOf('dense') === 0 ? 1 : 1.2;
  var markup = '';
  if (geometry.lines.indexOf('h') !== -1) {
    markup += '<line x1="0" y1="' + (s / 2) + '" x2="' + s + '" y2="' + (s / 2) + '"' +
      stroke + ' stroke-width="' + w + '"/>';
  }
  if (geometry.lines.indexOf('v') !== -1) {
    markup += '<line x1="' + (s / 2) + '" y1="0" x2="' + (s / 2) + '" y2="' + s + '"' +
      stroke + ' stroke-width="' + w + '"/>';
  }
  return { size: s, angle: geometry.angle, markup: markup };
}

/* Registers a <pattern> for this fill style (once per distinct style -
   keyed by its own values, so a thousand features sharing one symbol
   share one definition) and returns its id, or null if the pattern
   type isn't one we can draw. */
function fagEnsurePattern(map, fillStyle) {
  var pattern = fillStyle && fillStyle.fillPattern;
  if (!pattern) return null;
  var color = pattern.color || fillStyle.fillColor || '#333333';
  var opacity = pattern.opacity !== undefined ? pattern.opacity
    : (fillStyle.fillOpacity === undefined ? 1 : fillStyle.fillOpacity);

  var key = [pattern.type, pattern.angle, pattern.spacing, pattern.lineWidth,
    color, opacity].join('|');
  if (FAG_PATTERN_IDS[key]) return FAG_PATTERN_IDS[key];

  var body = fagPatternBody(pattern, color, opacity);
  if (!body) return null;
  var defs = fagPatternDefs(map);
  if (!defs) return null;

  var id = 'fag-pat-' + (FAG_PATTERN_SEQ++);
  var el = document.createElementNS('http://www.w3.org/2000/svg', 'pattern');
  el.setAttribute('id', id);
  el.setAttribute('width', body.size);
  el.setAttribute('height', body.size);
  // userSpaceOnUse keeps the hatch the same visual size at every zoom,
  // which is how QGIS draws it on screen - objectBoundingBox would
  // stretch the pattern to each polygon's own size instead.
  el.setAttribute('patternUnits', 'userSpaceOnUse');
  if (body.angle) el.setAttribute('patternTransform', 'rotate(' + body.angle + ')');
  el.innerHTML = body.markup;
  defs.appendChild(el);

  FAG_PATTERN_IDS[key] = id;
  return id;
}

/* Applies a registered pattern to one rendered path. Leaflet rewrites
   the `fill` attribute inside its own _updateStyle, so setStyle is
   wrapped to re-apply afterwards - otherwise a hover highlight or a
   map-unit weight recalculation would silently drop the hatch back to
   a flat color. */
function fagApplyPatternToPath(layer, patternId) {
  if (!patternId) return;
  var paint = function () {
    var el = layer.getElement && layer.getElement();
    if (el) el.setAttribute('fill', 'url(#' + patternId + ')');
  };
  paint();
  layer.on('add', paint);
  if (layer.setStyle && !layer._fagPatternPatched) {
    layer._fagPatternPatched = true;
    var original = layer.setStyle.bind(layer);
    layer.setStyle = function (style) {
      var result = original(style);
      paint();
      return result;
    };
  }
}

/* A standalone inline SVG swatch for the legend, carrying its own copy
   of the pattern definition. The legend lives in ordinary page DOM, not
   inside the map's <svg>, so it can't reference the map's <defs> -
   without this the legend and the map would disagree about what a
   hatched layer looks like, which the spec flags as easy to forget. */
function fagPatternSwatchHtml(fillStyle) {
  var pattern = fillStyle && fillStyle.fillPattern;
  if (!pattern) return null;
  var color = pattern.color || fillStyle.fillColor || '#333333';
  var opacity = pattern.opacity !== undefined ? pattern.opacity
    : (fillStyle.fillOpacity === undefined ? 1 : fillStyle.fillOpacity);
  var body = fagPatternBody(pattern, color, opacity);
  if (!body) return null;

  var id = 'fag-legend-pat-' + (FAG_PATTERN_SEQ++);
  var transform = body.angle ? ' patternTransform="rotate(' + body.angle + ')"' : '';
  var stroke = fillStyle.hasStroke === false ? 'none' : (fillStyle.strokeColor || '#888');
  return '<svg class="fag-legend-swatch" width="12" height="12" viewBox="0 0 12 12">' +
    '<defs><pattern id="' + id + '" width="' + body.size + '" height="' + body.size +
    '" patternUnits="userSpaceOnUse"' + transform + '>' + body.markup + '</pattern></defs>' +
    '<rect x="0.5" y="0.5" width="11" height="11" fill="url(#' + id + ')" ' +
    'stroke="' + stroke + '" stroke-width="1"/></svg>';
}
