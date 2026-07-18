# -*- coding: utf-8 -*-
"""Extract QGIS layer symbology/labeling into the style.json shape
described in spec section 4.2. Single-symbol renderers (spec 4.2.2)
produce just a 'defaultStyle'; categorized renderers (spec 4.2.2,
4.2.3) additionally produce a 'byCategory' table keyed by the
classification field, with 'defaultStyle' as the fallback for values
that don't match any category (e.g. an "all other values" catch-all
or data that predates the category being added).
"""
from qgis.core import (
    QgsProject, QgsSingleSymbolRenderer, QgsCategorizedSymbolRenderer,
    QgsRenderContext, QgsWkbTypes,
    QgsSimpleMarkerSymbolLayerBase, QgsVectorLayerSimpleLabeling,
    QgsExpression, QgsExpressionContext, QgsExpressionContextUtils,
    QgsUnitTypes,
)

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
    'strokeColor': '#2b2b2b', 'strokeWidth': 1,
}
DEFAULT_LABEL = {
    'fontFamily': 'sans-serif', 'fontSize': 12, 'color': '#333333',
    'bold': False, 'buffer': {'color': '#ffffff', 'width': 2},
}
DEFAULT_LINE = {'color': '#3b6fb0', 'width': 2, 'dashed': False}
DEFAULT_FILL = {'fillColor': '#cccccc', 'fillOpacity': 0.3, 'strokeColor': '#888888', 'strokeWidth': 1}


def _extract_marker_style(symbol):
    """`size` is the marker's full width/diameter (QGIS's own convention
    for QgsMarkerSymbol.size()) - callers that draw a radius-based
    circle (Leaflet's L.circleMarker) must halve it themselves; this
    module doesn't halve it here so divIcon shapes (which want a full
    width/height) can keep using it as-is."""
    style = dict(DEFAULT_MARKER)
    if symbol is None:
        return style
    try:
        color = symbol.color()
        if color is not None:
            style['color'] = color.name()
    except Exception:
        pass
    try:
        size_px = _to_px(float(symbol.size()), symbol.sizeUnit(), DEFAULT_MARKER['size'])
        style['size'] = round(_clamp(size_px, 2, 40), 1)
    except Exception:
        pass
    try:
        style['opacity'] = round(float(symbol.opacity()), 2)
    except Exception:
        pass
    try:
        symbol_layer = symbol.symbolLayer(0)
    except Exception:
        symbol_layer = None

    if symbol_layer is not None and hasattr(symbol_layer, 'shape'):
        try:
            shape_name = QgsSimpleMarkerSymbolLayerBase.encodeShape(symbol_layer.shape())
            style['shape'] = SHAPE_NAME_MAP.get(shape_name, 'circle')
        except Exception:
            pass

    if symbol_layer is not None and hasattr(symbol_layer, 'strokeColor'):
        # Simple marker symbol layers keep fill and stroke as separate
        # settings (same as polygons) - reading only symbol.color()
        # for both meant the stroke silently matched the fill and
        # looked like "no border" in dense/opaque markers.
        try:
            stroke_color = symbol_layer.strokeColor()
            if stroke_color is not None:
                style['strokeColor'] = stroke_color.name()
        except Exception:
            pass
        try:
            width_unit = (
                symbol_layer.strokeWidthUnit()
                if hasattr(symbol_layer, 'strokeWidthUnit') else QgsUnitTypes.RenderMillimeters
            )
            width_px = _to_px(float(symbol_layer.strokeWidth()), width_unit, DEFAULT_MARKER['strokeWidth'])
            style['strokeWidth'] = round(_clamp(width_px, 0, 10), 2)
        except Exception:
            pass
        try:
            if int(symbol_layer.strokeStyle()) == 0:  # Qt.NoPen == 0 across Qt versions
                style['strokeWidth'] = 0
        except Exception:
            pass

    return style


def _extract_line_style(symbol):
    """Reference-layer line symbology (spec 4.2.1 'ライン')."""
    style = dict(DEFAULT_LINE)
    if symbol is None:
        return style
    try:
        color = symbol.color()
        if color is not None:
            style['color'] = color.name()
    except Exception:
        pass
    try:
        width_unit = symbol.widthUnit() if hasattr(symbol, 'widthUnit') else QgsUnitTypes.RenderMillimeters
        width_px = _to_px(float(symbol.width()), width_unit, DEFAULT_LINE['width'])
        style['width'] = round(_clamp(width_px, 0.5, 20), 2)
    except Exception:
        pass
    try:
        symbol_layer = symbol.symbolLayer(0)
        if symbol_layer is not None and hasattr(symbol_layer, 'penStyle'):
            style['dashed'] = int(symbol_layer.penStyle()) != 1  # Qt.SolidLine == 1 across Qt versions
    except Exception:
        pass
    return style


def _extract_fill_style(symbol):
    """Reference-layer polygon symbology (spec 4.2.1 'ポリゴン').

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
    try:
        symbol_layer = symbol.symbolLayer(0)
    except Exception:
        symbol_layer = None

    if symbol_layer is not None and hasattr(symbol_layer, 'brushStyle'):
        # Genuine fill layer.
        try:
            color = symbol.color()
            if color is not None:
                style['fillColor'] = color.name()
                style['fillOpacity'] = round(color.alphaF(), 2)
        except Exception:
            pass
        try:
            if int(symbol_layer.brushStyle()) == 0:  # Qt.NoBrush == 0 across Qt versions
                style['fillOpacity'] = 0
        except Exception:
            pass
        try:
            stroke_color = symbol_layer.strokeColor()
            if stroke_color is not None:
                style['strokeColor'] = stroke_color.name()
        except Exception:
            pass
        try:
            width_unit = (
                symbol_layer.strokeWidthUnit()
                if hasattr(symbol_layer, 'strokeWidthUnit') else QgsUnitTypes.RenderMillimeters
            )
            width_px = _to_px(float(symbol_layer.strokeWidth()), width_unit, DEFAULT_FILL['strokeWidth'])
            style['strokeWidth'] = round(_clamp(width_px, 0.5, 20), 2)
        except Exception:
            pass
        try:
            if int(symbol_layer.strokeStyle()) == 0:  # Qt.NoPen == 0
                style['strokeWidth'] = 0
        except Exception:
            pass

    elif symbol_layer is not None and hasattr(symbol_layer, 'color'):
        # Outline-only polygon: the sole symbol layer is a line layer.
        # There is no fill to draw at all.
        style['fillOpacity'] = 0
        try:
            color = symbol_layer.color()
            if color is not None:
                style['strokeColor'] = color.name()
        except Exception:
            pass
        try:
            width_unit = (
                symbol_layer.widthUnit()
                if hasattr(symbol_layer, 'widthUnit') else QgsUnitTypes.RenderMillimeters
            )
            width_px = _to_px(float(symbol_layer.width()), width_unit, DEFAULT_FILL['strokeWidth'])
            style['strokeWidth'] = round(_clamp(width_px, 0.5, 20), 2)
        except Exception:
            pass

    return style


def _extract_label_style(layer):
    """Returns (style_dict, labels_enabled)."""
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
        size_px = _to_px(float(raw_size), fmt.sizeUnit(), DEFAULT_LABEL['fontSize'])
        style['fontSize'] = round(_clamp(size_px, 6, 60), 1)
    except Exception:
        pass
    style['bold'] = bool(font.bold())

    color = fmt.color()
    if color is not None:
        style['color'] = color.name()

    buffer_settings = fmt.buffer()
    if buffer_settings.enabled():
        bcolor = buffer_settings.color()
        try:
            width_px = _to_px(float(buffer_settings.size()), buffer_settings.sizeUnit(), 2)
            # Clamped tighter than other sizes on purpose: with hundreds of
            # densely-packed permanent labels, even a legitimately large
            # halo compounds into a solid block obscuring the whole map.
            width_px = _clamp(width_px, 0, 4)
        except Exception:
            width_px = 2
        style['buffer'] = {
            'color': bcolor.name() if bcolor is not None else '#ffffff',
            'width': round(width_px, 2),
        }
    else:
        style['buffer'] = None

    return style, True


def _style_for_symbol(symbol, geometry_type):
    """Build the marker/line/fill sub-object for one symbol, matching
    whichever key `extract_style` uses for this geometry type."""
    if geometry_type == QgsWkbTypes.LineGeometry:
        return {'line': _extract_line_style(symbol)}
    if geometry_type == QgsWkbTypes.PolygonGeometry:
        return {'fill': _extract_fill_style(symbol)}
    return {'marker': _extract_marker_style(symbol)}


def _extract_category_styles(renderer, geometry_type):
    """Return (field_name, {value_as_str: style_dict}) for a
    QgsCategorizedSymbolRenderer (spec 4.2.2/4.2.3). QGIS's "all other
    values" catch-all category also has a value (commonly an empty
    string) rather than a true wildcard, so features whose value
    matches nothing here fall back to 'defaultStyle' on the JS side -
    that's the same behavior a genuinely unmatched value would get.
    """
    field = renderer.classAttribute()
    table = {}
    for category in renderer.categories():
        value = category.value()
        key = '' if value is None else str(value)
        table[key] = _style_for_symbol(category.symbol(), geometry_type)
    return field, table


def extract_style(layer):
    """Build the style.json block for a single layer: 'defaultStyle'
    always, plus 'byCategory' when the layer uses a
    QgsCategorizedSymbolRenderer (spec 4.2.2/4.2.3). Branches on
    geometry type so this covers point/line/polygon layers alike
    (spec 3.1/4.2.1: point -> marker+label, line -> line, polygon ->
    fill). Renderers other than single-symbol/categorized (rule-based,
    graduated, ...) fall back to their first symbol as 'defaultStyle'
    so export still succeeds rather than failing outright (spec 4.2.2,
    deferred to a later phase).
    """
    renderer = layer.renderer()
    symbol = None
    category_field = None
    category_table = None
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
                category_field, category_table = _extract_category_styles(renderer, layer.geometryType())
            except Exception:
                category_field, category_table = None, None

    geometry_type = layer.geometryType()
    default_style = _style_for_symbol(symbol, geometry_type)
    if geometry_type not in (QgsWkbTypes.LineGeometry, QgsWkbTypes.PolygonGeometry):
        label_style, labels_enabled = _extract_label_style(layer)
        if labels_enabled:
            default_style['label'] = label_style
            if category_table:
                for cat_style in category_table.values():
                    cat_style['label'] = label_style

    result = {'defaultStyle': default_style}
    if category_field and category_table:
        result['byCategory'] = {category_field: category_table}
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
