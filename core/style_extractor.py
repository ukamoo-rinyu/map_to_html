# -*- coding: utf-8 -*-
"""Extract QGIS layer symbology/labeling into the style.json shape
described in spec section 4.2. Single-symbol renderers (spec 4.2.2)
produce just a 'defaultStyle'; categorized renderers (spec 4.2.2,
4.2.3) additionally produce a 'byCategory' table keyed by the
classification field, with 'defaultStyle' as the fallback for values
that don't match any category (e.g. an "all other values" catch-all
or data that predates the category being added).
"""
import math

from qgis.core import (
    QgsProject, QgsSingleSymbolRenderer, QgsCategorizedSymbolRenderer,
    QgsRenderContext, QgsWkbTypes,
    QgsSimpleMarkerSymbolLayerBase, QgsVectorLayerSimpleLabeling,
    QgsExpression, QgsExpressionContext, QgsExpressionContextUtils,
    QgsUnitTypes, QgsMessageLog, Qgis,
    QgsCoordinateTransform, QgsCoordinateReferenceSystem,
)


def _log_extract_warning(context, exc):
    """One style property couldn't be read (typically a symbol-layer
    method this QGIS version/symbol type doesn't expose) - the caller
    already has a sensible default in `style` for it, so export keeps
    going rather than aborting the whole layer, but the failure is
    still surfaced in QGIS's own message log instead of being silently
    discarded."""
    QgsMessageLog.logMessage(f'{context}: {exc}', 'Map to HTML', Qgis.Warning)


# 96 dpi conversions - only units with a fixed physical size can be
# converted without knowing the current render scale.
_PX_PER_UNIT = {
    QgsUnitTypes.RenderMillimeters: 96.0 / 25.4,
    QgsUnitTypes.RenderPoints: 96.0 / 72.0,
    QgsUnitTypes.RenderPixels: 1.0,
    QgsUnitTypes.RenderInches: 96.0,
}


def _to_px(value, unit, fallback):
    """Convert a QGIS size to CSS px. Map units/percentage depend on
    the render scale and have no fixed px equivalent, so those (and
    anything unrecognized) fall back to `fallback` rather than being
    used verbatim - a raw map-unit number used as a px count is what
    previously produced enormous, screen-covering label buffers."""
    factor = _PX_PER_UNIT.get(unit)
    if factor is None:
        return fallback
    return value * factor


def _clamp(value, lo, hi):
    return max(lo, min(hi, value))


# Qt pen styles -> a dash pattern expressed in multiples of the pen
# width, matching Qt's own definition (QPen's predefined patterns are
# specified in units of the pen's width, which is why a thick dashed
# line has proportionally longer dashes in QGIS). Qt.SolidLine (1) and
# Qt.NoPen (0) are deliberately absent - both mean "no dashArray".
_QT_DASH_PATTERNS = {
    2: [4, 2],              # Qt.DashLine
    3: [1, 2],              # Qt.DotLine
    4: [4, 2, 1, 2],        # Qt.DashDotLine
    5: [4, 2, 1, 2, 1, 2],  # Qt.DashDotDotLine
}


def _dash_array_for_pen(pen_style, width_px):
    """SVG/Leaflet `dashArray` string for a Qt pen style, or None for a
    solid (or absent) line. Leaflet takes the pattern in px, so Qt's
    width-relative units are multiplied out here."""
    try:
        pattern = _QT_DASH_PATTERNS.get(int(pen_style))
    except (TypeError, ValueError):
        return None
    if not pattern:
        return None
    # A hairline (or map-unit) width still needs a visible dash rhythm,
    # so the multiplier never drops below 1px.
    unit = max(float(width_px or 0), 1.0)
    return ','.join(str(round(value * unit, 2)) for value in pattern)


def _custom_dash_array(symbol_layer):
    """A QgsSimpleLineSymbolLayer can override the Qt pen style with a
    free-form dash vector ("カスタム破線パターン"). Returns None when
    that's off or unreadable, so the caller falls back to the pen
    style."""
    try:
        if not (hasattr(symbol_layer, 'useCustomDashPattern')
                and symbol_layer.useCustomDashPattern()):
            return None
        unit = (
            symbol_layer.customDashPatternUnit()
            if hasattr(symbol_layer, 'customDashPatternUnit') else QgsUnitTypes.RenderMillimeters
        )
        pattern = [
            round(_clamp(_to_px(float(value), unit, float(value)), 0.1, 500), 2)
            for value in symbol_layer.customDashVector()
        ]
        return ','.join(str(value) for value in pattern) if pattern else None
    except Exception as exc:
        _log_extract_warning('custom dash pattern', exc)
        return None


# Qt::BrushStyle values -> the pattern vocabulary the template's SVG
# <pattern> definitions implement (spec item 10-A). These cover the
# fixed set QGIS's "塗りつぶしスタイル" dropdown offers, which the spec
# notes is ~80% of real hatched-polygon usage. 0 (NoBrush) and 1
# (SolidPattern) are handled separately - they mean "no fill" and "the
# existing plain fill" rather than a pattern.
_QT_BRUSH_PATTERNS = {
    2: 'dense1', 3: 'dense2', 4: 'dense3', 5: 'dense4',
    6: 'dense5', 7: 'dense6', 8: 'dense7',
    9: 'hor', 10: 'ver', 11: 'cross',
    12: 'bdiag', 13: 'fdiag', 14: 'diagcross',
}

# 1mm at 96dpi, for converting QGIS's mm-based pattern spacing to the
# px the SVG <pattern> tile is measured in.
_MM_TO_PX = 96.0 / 25.4


def _color_alpha(color):
    """A QGIS color's own alpha channel (塗りつぶし色/枠線色の
    アルファ値) as 0.0-1.0."""
    try:
        return float(color.alphaF()) if color is not None else 1.0
    except Exception as exc:
        _log_extract_warning('color alpha', exc)
        return 1.0


def _symbol_opacity(symbol):
    """QgsSymbol.opacity() - the "シンボルの不透明度" slider, separate
    from both the color's alpha and the layer's own opacity."""
    try:
        return float(symbol.opacity()) if symbol is not None else 1.0
    except Exception as exc:
        _log_extract_warning('symbol opacity', exc)
        return 1.0


def _layer_opacity(layer):
    """QgsMapLayer.opacity() - レイヤプロパティ > レンダリング の
    不透明度. Applies on top of every symbol in the layer."""
    try:
        return float(layer.opacity())
    except Exception as exc:
        _log_extract_warning('layer opacity', exc)
        return 1.0


def _meters_per_map_unit(layer):
    """How many real-world meters one map (project-CRS) unit represents
    around this layer, or None when that isn't a fixed number (project
    CRS in degrees). Needed to export マップ単位 line widths as real
    meters: in Web Mercator (EPSG:3857) a "map unit meter" is inflated
    by 1/cos(latitude), so a 20-unit-wide road drawn on a 3857 canvas
    at Osaka is really only 20*cos(34.7°) ≈ 16.4m of ground - the
    web-map side re-applies the same cos factor dynamically, so real
    meters is the common currency between the two."""
    try:
        crs = QgsProject.instance().crs()
        if crs.mapUnits() != QgsUnitTypes.DistanceMeters:
            return None
        if crs.authid() != 'EPSG:3857':
            return 1.0  # a genuine metric CRS: map units are real meters
        center = layer.extent().center()
        transform = QgsCoordinateTransform(
            layer.crs(), QgsCoordinateReferenceSystem('EPSG:4326'), QgsProject.instance()
        )
        lat = transform.transform(center).y()
        return math.cos(math.radians(_clamp(lat, -85.0, 85.0)))
    except Exception as exc:
        _log_extract_warning('meters per map unit', exc)
        return 1.0


def _width_in_meters(value, unit, meters_per_map_unit):
    """Real-world meters for a map-based width, or None when the width
    isn't map-based at all (mm/pt/px - the fixed-size units handled by
    _to_px) or can't be converted (map units under a degrees CRS)."""
    if unit == QgsUnitTypes.RenderMetersInMapUnits:
        return value
    if unit == QgsUnitTypes.RenderMapUnits and meters_per_map_unit is not None:
        return value * meters_per_map_unit
    return None


# QGIS shape names -> the small shape vocabulary the Leaflet template understands.
SHAPE_NAME_MAP = {
    'circle': 'circle',
    'square': 'square', 'rectangle': 'square',
    'diamond': 'diamond', 'rhombus': 'diamond',
    'triangle': 'triangle', 'equilateral_triangle': 'triangle',
    'star': 'star',
    'cross': 'cross', 'cross2': 'cross', 'x': 'cross', 'line': 'cross',
    'pentagon': 'diamond', 'hexagon': 'diamond',
}

DEFAULT_MARKER = {
    'color': '#4a4a4a', 'size': 8, 'shape': 'circle', 'opacity': 1.0,
    'strokeColor': '#2b2b2b', 'strokeWidth': 1, 'strokeOpacity': 1.0,
}
DEFAULT_LABEL = {
    'fontFamily': 'sans-serif', 'fontSize': 12, 'color': '#333333',
    'bold': False, 'buffer': {'color': '#ffffff', 'width': 2},
}
DEFAULT_LINE = {'color': '#3b6fb0', 'width': 2, 'opacity': 1.0, 'dashArray': None}
DEFAULT_FILL = {
    'fillColor': '#cccccc', 'fillOpacity': 0.3, 'hasFill': True,
    'strokeColor': '#888888', 'strokeWidth': 1, 'strokeOpacity': 1.0,
    'hasStroke': True, 'dashArray': None,
}


def _extract_marker_style(symbol, layer_opacity=1.0, fill_opacity_override=None):
    """`size` is the marker's full width/diameter (QGIS's own convention
    for QgsMarkerSymbol.size()) - callers that draw a radius-based
    circle (Leaflet's L.circleMarker) must halve it themselves; this
    module doesn't halve it here so divIcon shapes (which want a full
    width/height) can keep using it as-is.

    `opacity` (the fill) and `strokeOpacity` are independent, and each
    is the product of three separate QGIS settings - see
    _final_opacity."""
    style = dict(DEFAULT_MARKER)
    if symbol is None:
        return style
    opacity_scale = _symbol_opacity(symbol) * layer_opacity
    # Seeded from the symbol/layer opacities alone so that a failure to
    # read the color below still keeps those two factors, rather than
    # silently falling back to fully opaque.
    style['opacity'] = round(_clamp(opacity_scale, 0.0, 1.0), 3)
    style['strokeOpacity'] = style['opacity']
    try:
        color = symbol.color()
        if color is not None:
            style['color'] = color.name()
            style['opacity'] = round(_clamp(_color_alpha(color) * opacity_scale, 0.0, 1.0), 3)
    except Exception as exc:
        _log_extract_warning('marker color', exc)
    try:
        size_px = _to_px(float(symbol.size()), symbol.sizeUnit(), DEFAULT_MARKER['size'])
        style['size'] = round(_clamp(size_px, 2, 40), 1)
    except Exception as exc:
        _log_extract_warning('marker size', exc)
    if fill_opacity_override is not None:
        style['opacity'] = round(_clamp(float(fill_opacity_override), 0.0, 1.0), 3)
    try:
        symbol_layer = symbol.symbolLayer(0)
    except Exception as exc:
        _log_extract_warning('marker symbol layer', exc)
        symbol_layer = None

    if symbol_layer is not None and hasattr(symbol_layer, 'shape'):
        try:
            shape_name = QgsSimpleMarkerSymbolLayerBase.encodeShape(symbol_layer.shape())
            style['shape'] = SHAPE_NAME_MAP.get(shape_name, 'circle')
        except Exception as exc:
            _log_extract_warning('marker shape', exc)

    if symbol_layer is not None and hasattr(symbol_layer, 'strokeColor'):
        # Simple marker symbol layers keep fill and stroke as separate
        # settings (same as polygons) - reading only symbol.color()
        # for both meant the stroke silently matched the fill and
        # looked like "no border" in dense/opaque markers.
        try:
            stroke_color = symbol_layer.strokeColor()
            if stroke_color is not None:
                style['strokeColor'] = stroke_color.name()
                style['strokeOpacity'] = round(
                    _clamp(_color_alpha(stroke_color) * opacity_scale, 0.0, 1.0), 3
                )
        except Exception as exc:
            _log_extract_warning('marker stroke color', exc)
        try:
            width_unit = (
                symbol_layer.strokeWidthUnit()
                if hasattr(symbol_layer, 'strokeWidthUnit') else QgsUnitTypes.RenderMillimeters
            )
            width_px = _to_px(float(symbol_layer.strokeWidth()), width_unit, DEFAULT_MARKER['strokeWidth'])
            style['strokeWidth'] = round(_clamp(width_px, 0, 10), 2)
        except Exception as exc:
            _log_extract_warning('marker stroke width', exc)
        try:
            if int(symbol_layer.strokeStyle()) == 0:  # Qt.NoPen == 0 across Qt versions
                style['strokeWidth'] = 0
        except Exception as exc:
            _log_extract_warning('marker stroke style', exc)

    return style


def _extract_line_style(symbol, meters_per_map_unit=None, layer_opacity=1.0):
    """Reference-layer line symbology (spec 4.2.1 'ライン').

    A map-based width (マップ単位 / メートル(地図単位) - e.g. a road
    layer whose line width IS the road's real width, so zooming out
    shrinks it instead of keeping a constant screen thickness) exports
    as `widthMeters` (real-world meters); the web side recomputes the
    px weight per zoom level from it (style-renderer.js). `width` (px)
    is still always set as the fallback for that recomputation being
    unavailable. Fixed-size units (mm/pt/px) export as px `width` only,
    same as before."""
    style = dict(DEFAULT_LINE)
    if symbol is None:
        return style
    opacity_scale = _symbol_opacity(symbol) * layer_opacity
    style['opacity'] = round(_clamp(opacity_scale, 0.0, 1.0), 3)
    try:
        color = symbol.color()
        if color is not None:
            style['color'] = color.name()
            style['opacity'] = round(_clamp(_color_alpha(color) * opacity_scale, 0.0, 1.0), 3)
    except Exception as exc:
        _log_extract_warning('line color', exc)
    try:
        symbol_layer = symbol.symbolLayer(0)
    except Exception as exc:
        _log_extract_warning('line symbol layer', exc)
        symbol_layer = None
    try:
        # The unit lives on the symbol LAYER (QgsSimpleLineSymbolLayer.
        # widthUnit()), not on QgsLineSymbol itself - reading it off the
        # symbol always fell back to "millimeters", which turned e.g. a
        # 19.5 map-unit road width into 19.5mm ≈ 74px of screen-covering
        # line (spec feedback: exported roads came out enormous).
        if symbol_layer is not None and hasattr(symbol_layer, 'widthUnit'):
            width_unit = symbol_layer.widthUnit()
        else:
            width_unit = QgsUnitTypes.RenderMillimeters
        width_value = float(symbol.width())
        width_meters = _width_in_meters(width_value, width_unit, meters_per_map_unit)
        if width_meters is not None:
            style['widthMeters'] = round(width_meters, 2)
        else:
            width_px = _to_px(width_value, width_unit, DEFAULT_LINE['width'])
            style['width'] = round(_clamp(width_px, 0.5, 20), 2)
    except Exception as exc:
        _log_extract_warning('line width', exc)
    try:
        if symbol_layer is not None and hasattr(symbol_layer, 'penStyle'):
            pen_style = int(symbol_layer.penStyle())
            if pen_style == 0:  # Qt.NoPen - the line isn't drawn at all
                style['opacity'] = 0.0
            else:
                style['dashArray'] = (
                    _custom_dash_array(symbol_layer)
                    or _dash_array_for_pen(pen_style, style.get('width'))
                )
    except Exception as exc:
        _log_extract_warning('line dash style', exc)
    return style


def _extract_fill_style(symbol, meters_per_map_unit=None, layer_opacity=1.0,
                        fill_opacity_override=None, warnings=None, layer_name=''):
    """Reference-layer polygon symbology (spec 4.2.1 'ポリゴン').
    A map-based stroke width exports as `strokeWidthMeters` alongside
    the px fallback, same scheme as _extract_line_style's widthMeters.

    Fill and stroke carry *independent* opacities, each the product of
    three separate QGIS settings that all have to be multiplied
    together or the exported polygon comes out as a flat opaque block:
    the color's own alpha channel, QgsSymbol.opacity() ("シンボルの
    不透明度"), and QgsMapLayer.opacity() (レイヤプロパティ >
    レンダリング). Reading only the first of the three is what
    previously made every transparent polygon export solid.

    A polygon symbol's first (and often only) symbol layer can be a
    genuine fill (QgsSimpleFillSymbolLayer, with its own fill color/
    brush plus a stroke) or - a common way to draw an outline-only
    boundary like a ward/district line - a QgsSimpleLineSymbolLayer
    with no fill layer at all ("Outline: Simple Line" in the QGIS
    symbol editor). Those two need different handling: reading
    `symbol.color()` unconditionally treats the *line's* color as an
    opaque fill in the second case, painting a solid block over
    everything underneath it.
    """
    style = dict(DEFAULT_FILL)
    if symbol is None:
        return style
    opacity_scale = _symbol_opacity(symbol) * layer_opacity
    style['fillOpacity'] = round(_clamp(opacity_scale, 0.0, 1.0), 3)
    style['strokeOpacity'] = style['fillOpacity']
    try:
        symbol_layer = symbol.symbolLayer(0)
    except Exception as exc:
        _log_extract_warning('fill symbol layer', exc)
        symbol_layer = None

    warnings_list = warnings if warnings is not None else []
    line_pattern = (
        _line_pattern_fill(symbol_layer, opacity_scale)
        if symbol_layer is not None and type(symbol_layer).__name__ == 'QgsLinePatternFillSymbolLayer'
        else None
    )

    if line_pattern:
        # 線パターン塗りつぶし: this symbol layer IS the hatch - it has no
        # brushStyle and no stroke of its own. Note only symbolLayer(0)
        # is read, so a polygon that stacks a separate outline layer
        # under/over the hatch exports without that outline.
        style['fillPattern'] = line_pattern
        style['hasFill'] = True
        style['fillColor'] = line_pattern.get('color', style['fillColor'])
        style['fillOpacity'] = line_pattern.get('opacity', 1.0)
        style['hasStroke'] = False
        style['strokeWidth'] = 0
    elif symbol_layer is not None and hasattr(symbol_layer, 'brushStyle'):
        # Genuine fill layer.
        try:
            color = symbol.color()
            if color is not None:
                style['fillColor'] = color.name()
                style['fillOpacity'] = round(
                    _clamp(_color_alpha(color) * opacity_scale, 0.0, 1.0), 3
                )
        except Exception as exc:
            _log_extract_warning('fill color', exc)
        try:
            if int(symbol_layer.brushStyle()) == 0:  # Qt.NoBrush == 0 across Qt versions
                # Not just "invisible": an explicit no-fill, which the web
                # side turns into Leaflet's `fill: false` so the polygon's
                # interior doesn't hit-test either.
                style['hasFill'] = False
                style['fillOpacity'] = 0
        except Exception as exc:
            _log_extract_warning('fill brush style', exc)
        # A hatch/pattern fill (spec item 10). Qt's brush patterns paint
        # the FILL color as the hatch itself over a transparent
        # background, which is why fillColor doubles as the hatch color
        # on the web side rather than needing a separate key.
        pattern = _extract_fill_pattern(symbol_layer, opacity_scale, warnings_list, layer_name)
        if pattern:
            style['fillPattern'] = pattern
    elif symbol_layer is not None and type(symbol_layer).__name__ in (
            'QgsPointPatternFillSymbolLayer', 'QgsSVGFillSymbolLayer',
            'QgsRasterFillSymbolLayer', 'QgsRandomMarkerFillSymbolLayer'):
        # Out of scope, and the fallback must not be silent (spec 10-C).
        _extract_fill_pattern(symbol_layer, opacity_scale, warnings_list, layer_name)
        try:
            stroke_color = symbol_layer.strokeColor()
            if stroke_color is not None:
                style['strokeColor'] = stroke_color.name()
                style['strokeOpacity'] = round(
                    _clamp(_color_alpha(stroke_color) * opacity_scale, 0.0, 1.0), 3
                )
        except Exception as exc:
            _log_extract_warning('fill stroke color', exc)
        try:
            width_unit = (
                symbol_layer.strokeWidthUnit()
                if hasattr(symbol_layer, 'strokeWidthUnit') else QgsUnitTypes.RenderMillimeters
            )
            width_value = float(symbol_layer.strokeWidth())
            width_meters = _width_in_meters(width_value, width_unit, meters_per_map_unit)
            if width_meters is not None:
                style['strokeWidthMeters'] = round(width_meters, 2)
            else:
                width_px = _to_px(width_value, width_unit, DEFAULT_FILL['strokeWidth'])
                style['strokeWidth'] = round(_clamp(width_px, 0.5, 20), 2)
        except Exception as exc:
            _log_extract_warning('fill stroke width', exc)
        try:
            stroke_style = int(symbol_layer.strokeStyle())
            if stroke_style == 0:  # Qt.NoPen == 0
                style['hasStroke'] = False
                style['strokeWidth'] = 0
            else:
                style['dashArray'] = _dash_array_for_pen(stroke_style, style.get('strokeWidth'))
        except Exception as exc:
            _log_extract_warning('fill stroke style', exc)

    elif symbol_layer is not None and hasattr(symbol_layer, 'color'):
        # Outline-only polygon: the sole symbol layer is a line layer.
        # There is no fill to draw at all.
        style['hasFill'] = False
        style['fillOpacity'] = 0
        try:
            color = symbol_layer.color()
            if color is not None:
                style['strokeColor'] = color.name()
                style['strokeOpacity'] = round(
                    _clamp(_color_alpha(color) * opacity_scale, 0.0, 1.0), 3
                )
        except Exception as exc:
            _log_extract_warning('outline color', exc)
        try:
            width_unit = (
                symbol_layer.widthUnit()
                if hasattr(symbol_layer, 'widthUnit') else QgsUnitTypes.RenderMillimeters
            )
            width_value = float(symbol_layer.width())
            width_meters = _width_in_meters(width_value, width_unit, meters_per_map_unit)
            if width_meters is not None:
                style['strokeWidthMeters'] = round(width_meters, 2)
            else:
                width_px = _to_px(width_value, width_unit, DEFAULT_FILL['strokeWidth'])
                style['strokeWidth'] = round(_clamp(width_px, 0.5, 20), 2)
        except Exception as exc:
            _log_extract_warning('outline width', exc)
        try:
            if hasattr(symbol_layer, 'penStyle'):
                pen_style = int(symbol_layer.penStyle())
                if pen_style == 0:  # Qt.NoPen
                    style['hasStroke'] = False
                    style['strokeWidth'] = 0
                else:
                    style['dashArray'] = (
                        _custom_dash_array(symbol_layer)
                        or _dash_array_for_pen(pen_style, style.get('strokeWidth'))
                    )
        except Exception as exc:
            _log_extract_warning('outline dash style', exc)

    # 表示設定 tab's "塗りの透過率を上書きする" - deliberately applied
    # last and only to the fill, so the user's one slider can make every
    # overlapping polygon see-through without also washing out the
    # outlines that make each shape readable. A no-fill polygon
    # (NoBrush/outline-only) stays no-fill: the override sets how
    # transparent a fill is, not whether there is one.
    if fill_opacity_override is not None and style['hasFill']:
        style['fillOpacity'] = round(_clamp(float(fill_opacity_override), 0.0, 1.0), 3)

    return style


def _line_pattern_fill(symbol_layer, opacity_scale):
    """A QgsLinePatternFillSymbolLayer ("線パターン塗りつぶし"), where
    the angle/spacing/width/color are all free-form rather than one of
    Qt's fixed brush styles (spec item 10-B). Returns the dict the
    template turns into a generated <pattern>, or None if this isn't
    that kind of symbol layer."""
    if not hasattr(symbol_layer, 'lineAngle'):
        return None
    pattern = {'type': 'lines'}
    try:
        # QGIS measures lineAngle clockwise from horizontal (0 = a
        # horizontal line). SVG's patternTransform rotate() is also
        # clockwise in screen coordinates (y grows downward), so the
        # angle carries over with the same sign - no negation.
        pattern['angle'] = round(float(symbol_layer.lineAngle()), 2)
    except Exception as exc:
        _log_extract_warning('line pattern angle', exc)
        pattern['angle'] = 45.0
    try:
        unit = (
            symbol_layer.distanceUnit()
            if hasattr(symbol_layer, 'distanceUnit') else QgsUnitTypes.RenderMillimeters
        )
        spacing = _to_px(float(symbol_layer.distance()), unit, 2.0 * _MM_TO_PX)
        pattern['spacing'] = round(_clamp(spacing, 2.0, 100.0), 2)
    except Exception as exc:
        _log_extract_warning('line pattern spacing', exc)
        pattern['spacing'] = 8.0
    try:
        unit = (
            symbol_layer.lineWidthUnit()
            if hasattr(symbol_layer, 'lineWidthUnit') else QgsUnitTypes.RenderMillimeters
        )
        width = _to_px(float(symbol_layer.lineWidth()), unit, 1.0)
        pattern['lineWidth'] = round(_clamp(width, 0.3, 20.0), 2)
    except Exception as exc:
        _log_extract_warning('line pattern width', exc)
        pattern['lineWidth'] = 1.0
    try:
        color = symbol_layer.color()
        if color is not None:
            pattern['color'] = color.name()
            pattern['opacity'] = round(
                _clamp(_color_alpha(color) * opacity_scale, 0.0, 1.0), 3
            )
    except Exception as exc:
        _log_extract_warning('line pattern color', exc)
    return pattern


def _extract_fill_pattern(symbol_layer, opacity_scale, warnings, layer_name):
    """The hatch/pattern fill for one polygon symbol layer, or None for
    a plain solid fill (spec item 10).

    Anything not covered - point-pattern fills, SVG fills, raster image
    fills - deliberately falls back to a plain fill AND records a
    warning. Silently changing how a layer looks is the outcome the
    spec calls out as worst ("黙って見た目が変わるのが一番困る")."""
    class_name = type(symbol_layer).__name__

    if class_name == 'QgsLinePatternFillSymbolLayer':
        return _line_pattern_fill(symbol_layer, opacity_scale)

    if class_name in ('QgsPointPatternFillSymbolLayer', 'QgsSVGFillSymbolLayer',
                      'QgsRasterFillSymbolLayer', 'QgsRandomMarkerFillSymbolLayer'):
        warnings.append(
            '「{0}」の塗りつぶし（{1}）はHTMLに変換できないため、'
            'べた塗りで出力しました。'.format(layer_name, class_name)
        )
        return None

    if hasattr(symbol_layer, 'brushStyle'):
        try:
            name = _QT_BRUSH_PATTERNS.get(int(symbol_layer.brushStyle()))
        except Exception as exc:
            _log_extract_warning('fill brush pattern', exc)
            return None
        if name:
            return {'type': name}
    return None


def _extract_label_style(layer, meters_per_map_unit=None):
    """Returns (style_dict, labels_enabled).

    A font size set in マップ単位/メートル(地図単位) is exported as
    `fontSizeMeters` (real-world meters, same currency as the line
    widths above) in addition to the fixed `fontSize` px fallback, so
    the web map can grow/shrink the text with the zoom level exactly
    like QGIS does instead of freezing it at one screen size. Same for
    the halo/buffer width (`buffer.widthMeters`)."""
    if not layer.labelsEnabled():
        return dict(DEFAULT_LABEL), False
    labeling = layer.labeling()
    if not isinstance(labeling, QgsVectorLayerSimpleLabeling):
        return dict(DEFAULT_LABEL), False

    style = dict(DEFAULT_LABEL)
    settings = labeling.settings()
    fmt = settings.format()
    font = fmt.font()

    style['fontFamily'] = font.family() or DEFAULT_LABEL['fontFamily']
    try:
        raw_size = fmt.size() if fmt.size() else font.pointSize()
        size_unit = fmt.sizeUnit()
        size_px = _to_px(float(raw_size), size_unit, DEFAULT_LABEL['fontSize'])
        style['fontSize'] = round(_clamp(size_px, 6, 60), 1)
        size_meters = _width_in_meters(float(raw_size), size_unit, meters_per_map_unit)
        if size_meters:
            style['fontSizeMeters'] = round(size_meters, 3)
    except Exception as exc:
        _log_extract_warning('label font size', exc)
    style['bold'] = bool(font.bold())

    color = fmt.color()
    if color is not None:
        style['color'] = color.name()

    buffer_settings = fmt.buffer()
    if buffer_settings.enabled():
        bcolor = buffer_settings.color()
        buffer_meters = None
        try:
            buffer_unit = buffer_settings.sizeUnit()
            width_px = _to_px(float(buffer_settings.size()), buffer_unit, 2)
            # Clamped tighter than other sizes on purpose: with hundreds of
            # densely-packed permanent labels, even a legitimately large
            # halo compounds into a solid block obscuring the whole map.
            width_px = _clamp(width_px, 0, 4)
            buffer_meters = _width_in_meters(
                float(buffer_settings.size()), buffer_unit, meters_per_map_unit
            )
        except Exception:
            width_px = 2
        style['buffer'] = {
            'color': bcolor.name() if bcolor is not None else '#ffffff',
            'width': round(width_px, 2),
        }
        if buffer_meters:
            style['buffer']['widthMeters'] = round(buffer_meters, 3)
    else:
        style['buffer'] = None

    return style, True


def _style_for_symbol(symbol, geometry_type, meters_per_map_unit=None,
                      layer_opacity=1.0, fill_opacity_override=None,
                      warnings=None, layer_name=''):
    """Build the marker/line/fill sub-object for one symbol, matching
    whichever key `extract_style` uses for this geometry type. This is
    the single "one QGIS symbol -> one web style" seam every renderer
    goes through - single-symbol, each category of a categorized
    renderer, and (when it's added) each class of a graduated one.
    """
    if geometry_type == QgsWkbTypes.LineGeometry:
        return {'line': _extract_line_style(symbol, meters_per_map_unit, layer_opacity)}
    if geometry_type == QgsWkbTypes.PolygonGeometry:
        return {'fill': _extract_fill_style(
            symbol, meters_per_map_unit, layer_opacity, fill_opacity_override,
            warnings, layer_name
        )}
    return {'marker': _extract_marker_style(symbol, layer_opacity, fill_opacity_override)}


def _is_null(value):
    """True for a QGIS NULL attribute. A NULL doesn't arrive as Python's
    None - it's a QVariant that stringifies to "NULL", so a plain
    str() would classify it under a category literally named NULL."""
    if value is None:
        return True
    try:
        return bool(value.isNull())
    except AttributeError:
        return False


def _category_key(value):
    """The lookup key for one category value, as a string.

    The JS side looks a feature up with String(props[field]), so
    everything is stringified here too - otherwise a numeric
    classification field (a code like 3, exported to JSON as the number
    3) would never match a category whose value came out of QGIS as the
    Python int 3 but got written as a JSON object key anyway. Booleans
    are special-cased because Python renders them "True"/"False" while
    JSON/JS render them "true"/"false".
    """
    if _is_null(value):
        return ''
    if isinstance(value, bool):
        return 'true' if value else 'false'
    return str(value)


def build_render_filter(layer):
    """Return callable(feature) -> bool for "does QGIS actually draw
    this feature", or None when every feature is drawn (the common
    case, so the caller can skip the per-feature check entirely).

    Only unchecked categories of a categorized renderer are handled:
    those features are invisible in QGIS, so exporting them would make
    them reappear on the web map - and since an unchecked category's
    style is deliberately absent from `byCategory`, they'd come back
    wearing the fallback style rather than their own. Dropping them at
    export time also keeps them out of the search index and the feature
    table, which is what "hidden in QGIS" should mean everywhere.
    """
    renderer = layer.renderer()
    if not isinstance(renderer, QgsCategorizedSymbolRenderer):
        return None

    hidden = set()
    for category in renderer.categories():
        try:
            if not category.renderState():
                hidden.add(_category_key(category.value()))
        except Exception as exc:
            _log_extract_warning('category render state', exc)
    if not hidden:
        return None

    field = renderer.classAttribute()
    if field not in layer.fields().names():
        # An expression-based classification rather than a plain field -
        # evaluating it per feature is out of scope here, so nothing is
        # filtered rather than filtering the wrong things.
        return None

    def keep(feature):
        try:
            return _category_key(feature[field]) not in hidden
        except (KeyError, IndexError):
            return True

    return keep


def _extract_category_styles(renderer, geometry_type, meters_per_map_unit=None,
                             layer_opacity=1.0, fill_opacity_override=None,
                             warnings=None, layer_name=''):
    """Return (field, {value_as_str: style}, fallback_style, legend) for
    a QgsCategorizedSymbolRenderer (spec 4.2.2/4.2.3).

    Three QGIS behaviors have to be reproduced here, not just the
    color/size of each category:

    * An unchecked category (`renderState()` False) is hidden in QGIS,
      so it must not be exported at all - otherwise features the user
      deliberately turned off reappear on the web map.
    * QGIS's "その他すべての値" catch-all is a real category whose value
      is an empty string, not a wildcard. It's pulled out as the
      explicit `fallback` so unmatched *and* NULL values render the way
      QGIS renders them, instead of falling through to the renderer's
      first symbol (which is just some unrelated category's style).
    * `label()` is what the QGIS legend shows for a category, and it's
      routinely different from the raw value ("1" -> "小学校"), so the
      web legend carries it separately from the lookup key.
    """
    field = renderer.classAttribute()
    table = {}
    fallback = None
    legend = []
    for category in renderer.categories():
        try:
            if not category.renderState():
                continue
        except Exception as exc:
            _log_extract_warning('category render state', exc)
        style = _style_for_symbol(
            category.symbol(), geometry_type, meters_per_map_unit,
            layer_opacity, fill_opacity_override, warnings, layer_name,
        )
        key = _category_key(category.value())
        try:
            label = category.label()
        except Exception as exc:
            _log_extract_warning('category label', exc)
            label = key
        if key == '':
            # The catch-all. Its own key stays in the table too, since a
            # feature can legitimately hold an empty string.
            fallback = style
        table[key] = style
        legend.append({'value': key, 'label': label or key, 'style': style})
    return field, table, fallback, legend


def extract_style(layer, fill_opacity_override=None, warnings=None):
    """Build the style.json block for a single layer: 'defaultStyle'
    always, plus 'byCategory' when the layer uses a
    QgsCategorizedSymbolRenderer (spec 4.2.2/4.2.3). Branches on
    geometry type so this covers point/line/polygon layers alike
    (spec 3.1/4.2.1: point -> marker+label, line -> line, polygon ->
    fill). Renderers other than single-symbol/categorized (rule-based,
    graduated, ...) fall back to their first symbol as 'defaultStyle'
    so export still succeeds rather than failing outright (spec 4.2.2,
    deferred to a later phase).

    `fill_opacity_override` (0.0-1.0, from 表示設定 tab's "塗りの透過率
    を上書きする") replaces every extracted fill opacity with one flat
    value instead of using what QGIS says.

    `warnings` is an optional list this appends human-readable messages
    to for symbology that had to be approximated - currently
    point-pattern/SVG/raster fills, which fall back to a plain fill.
    dialog.py surfaces them in the completion dialog so a changed
    appearance is never a silent surprise (spec item 10-C).
    """
    renderer = layer.renderer()
    symbol = None
    category_field = None
    category_table = None
    category_fallback = None
    category_legend = None
    # Computed once per layer (it does a CRS transform) and shared by
    # the default symbol and every category symbol alike.
    meters_per_map_unit = _meters_per_map_unit(layer)
    # Layer-wide opacity multiplies into every symbol of this layer, so
    # it's read once here rather than per symbol.
    layer_opacity = _layer_opacity(layer)
    if warnings is None:
        warnings = []
    layer_name = layer.name()
    if renderer is not None:
        if isinstance(renderer, QgsSingleSymbolRenderer):
            symbol = renderer.symbol()
        else:
            try:
                symbols = renderer.symbols(QgsRenderContext())
                if symbols:
                    symbol = symbols[0]
            except Exception:
                symbol = None
        if isinstance(renderer, QgsCategorizedSymbolRenderer):
            try:
                category_field, category_table, category_fallback, category_legend = (
                    _extract_category_styles(
                        renderer, layer.geometryType(), meters_per_map_unit,
                        layer_opacity, fill_opacity_override, warnings, layer_name,
                    )
                )
            except Exception as exc:
                _log_extract_warning('categorized renderer', exc)
                category_field, category_table = None, None

    geometry_type = layer.geometryType()
    default_style = _style_for_symbol(
        symbol, geometry_type, meters_per_map_unit, layer_opacity, fill_opacity_override,
        warnings, layer_name
    )
    # QGIS's "その他すべての値" category is what an unmatched feature
    # actually renders as, so when the layer defines one it - not the
    # renderer's arbitrary first symbol - is the right fallback.
    if category_fallback:
        default_style = dict(category_fallback)
    if geometry_type not in (QgsWkbTypes.LineGeometry, QgsWkbTypes.PolygonGeometry):
        label_style, labels_enabled = _extract_label_style(layer, meters_per_map_unit)
        if labels_enabled:
            default_style['label'] = label_style
            if category_table:
                # QGIS's simple labeling is layer-level, not per-category,
                # so every category shares the one label style.
                for cat_style in category_table.values():
                    cat_style['label'] = label_style

    result = {'defaultStyle': default_style}
    if category_field and category_table:
        result['byCategory'] = {category_field: category_table}
        result['categoryLegend'] = {'field': category_field, 'entries': category_legend}
    return result


def build_label_text_evaluator(layer):
    """Return a callable(feature) -> str giving the pre-evaluated label
    text for a feature (spec 4.2.1.1). Handles both a QGIS label
    expression (isExpression=True) and a plain single-field label, so
    the template only ever needs to read one 'label_text' attribute.
    """
    if not layer.labelsEnabled():
        return lambda feature: ''
    labeling = layer.labeling()
    if not isinstance(labeling, QgsVectorLayerSimpleLabeling):
        return lambda feature: ''

    settings = labeling.settings()

    if settings.isExpression:
        expression = QgsExpression(settings.fieldName)
        context = QgsExpressionContext()
        context.appendScope(QgsExpressionContextUtils.globalScope())
        context.appendScope(QgsExpressionContextUtils.projectScope(QgsProject.instance()))
        context.appendScope(QgsExpressionContextUtils.layerScope(layer))

        def evaluator(feature):
            context.setFeature(feature)
            value = expression.evaluate(context)
            return '' if value is None else str(value)

        return evaluator

    field_name = settings.fieldName

    def evaluator(feature):
        if field_name not in feature.fields().names():
            return ''
        value = feature[field_name]
        return '' if value is None else str(value)

    return evaluator
