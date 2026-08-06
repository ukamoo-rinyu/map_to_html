# -*- coding: utf-8 -*-
"""Helpers for reading layers out of the current QGIS project."""
import math

from qgis.core import QgsProject, QgsVectorLayer, QgsRasterLayer, QgsLayerTreeNode


# The map scale denominator Leaflet/OSM zoom level 0 corresponds to at
# 96 dpi on the equator; each zoom level halves it. This is the same
# constant every "scale <-> web map zoom" table is built from.
_SCALE_DENOMINATOR_AT_ZOOM_0 = 559082264.028


def _scale_to_zoom(scale_denominator):
    """Leaflet zoom level for a QGIS scale denominator (1:`scale`).
    Returns None for 0/None, which is how QGIS spells "no limit".

    Approximate by nature: QGIS's scale is measured at the map canvas's
    center latitude, while this constant is the equator value, so the
    two drift apart the further north the data sits. For deciding
    "roughly when should this layer appear" that's well within
    tolerance - and the user can override the number per layer anyway.
    """
    try:
        scale = float(scale_denominator)
    except (TypeError, ValueError):
        return None
    if scale <= 0:
        return None
    return math.log2(_SCALE_DENOMINATOR_AT_ZOOM_0 / scale)


def scale_visibility_zoom_range(layer):
    """{'min': int, 'max': int} of Leaflet zoom levels for a layer that
    has QGIS's 縮尺に応じた表示設定 enabled, or None when it doesn't
    (spec item 6-A: "QGISの設定が済んでいればそれを自動で読み取る").

    QGIS's naming is the opposite way round from a web map's: its
    `minimumScale` is the most zoomed-OUT limit (the biggest
    denominator), so it maps to the layer's MINIMUM zoom level, and
    `maximumScale` maps to the maximum. Getting these two backwards
    would hide the layer at exactly the zooms it should be visible at.
    """
    try:
        if not layer.hasScaleBasedVisibility():
            return None
    except AttributeError:
        return None

    min_zoom = _scale_to_zoom(layer.minimumScale())
    max_zoom = _scale_to_zoom(layer.maximumScale())
    if min_zoom is None and max_zoom is None:
        return None

    result = {}
    if min_zoom is not None:
        result['min'] = int(math.floor(min_zoom))
    if max_zoom is not None:
        result['max'] = int(math.ceil(max_zoom))
    return result or None


def field_aliases(layer):
    """{field_name: display_name} for fields whose QGIS alias differs
    from the raw field name (spec item 7-4).

    `attributeDisplayName` returns the alias when one is set and the
    plain field name otherwise, so comparing the two is what tells the
    difference - only genuine aliases are exported, keeping config.js
    free of an identity mapping for every field of every layer.
    """
    aliases = {}
    # A raster/tile layer has no fields at all, which is the only case
    # this needs to tolerate - checked explicitly rather than caught,
    # so a genuine failure inside the loop below isn't swallowed too.
    if not hasattr(layer, 'fields'):
        return aliases
    for index, field in enumerate(layer.fields()):
        display = layer.attributeDisplayName(index)
        if display and display != field.name():
            aliases[field.name()] = display
    return aliases


def _walk_layers(node, path, results):
    for child in node.children():
        if child.nodeType() == QgsLayerTreeNode.NodeGroup:
            _walk_layers(child, path + [child.name()], results)
        else:  # NodeLayer
            layer = child.layer()
            if isinstance(layer, QgsVectorLayer):
                if not layer.isSpatial():
                    # Table-only layer (no geometry column - e.g. a
                    # plain CSV/DBF attribute table added to the
                    # project). There's nothing to draw or place a
                    # popup at, so it can't be published as a map
                    # layer - excluding it here keeps it out of both
                    # the picker dropdown and the auto-populated table
                    # (spec feedback: it was showing up as an addable
                    # "データ" layer even though generating with it
                    # selected has nothing to render).
                    continue
                layer_type = 'vector'
            elif isinstance(layer, QgsRasterLayer):
                layer_type = 'raster'
            else:
                continue
            label = ' / '.join(path + [layer.name()]) if path else layer.name()
            results.append({
                'label': label,
                'name': layer.name(),
                'id': layer.id(),
                'group_path': path,
                'visible': bool(child.isVisible()),
                'type': layer_type,
            })


def list_pickable_layers(project=None):
    """Return every vector or raster layer in the project as
    [{'label', 'name', 'id', 'group_path', 'visible', 'type'}, ...] in
    layer-tree display order. `label` is the full 'Group / Sub /
    Layer' path; `name` is just the layer's own name (for UI that
    renders the group separately, e.g. as a header). Raster layers are
    included so an XYZ tile layer someone already added to the QGIS
    project (e.g. a 国土地理院 basemap) can be picked and published
    as-is, alongside the usual point/line/polygon data (spec 3.1)."""
    project = project or QgsProject.instance()
    results = []
    _walk_layers(project.layerTreeRoot(), [], results)
    return results


def list_vector_layers(project=None):
    """Return [(label, layer_id)] for every vector layer only - kept
    for callers that don't care about raster/tile layers."""
    return [(item['label'], item['id']) for item in list_pickable_layers(project)
            if item['type'] == 'vector']


def list_visible_layer_ids(project=None):
    """Return the layer ids currently checked/visible in the QGIS layer
    panel (vector or raster), in tree display order, so the dialog can
    pre-populate the layer table with "what's already shown in QGIS"
    instead of starting empty."""
    return [item['id'] for item in list_pickable_layers(project) if item['visible']]


def get_layer_group_path(layer_id, project=None):
    """Return the list of group names (top -> bottom) a layer sits
    under in the layer tree, e.g. ['公共施設', '学校'], or [] if it's
    at the tree root - used to mirror QGIS's group hierarchy both in
    the plugin's own layer picker and the web output's layer panel."""
    for item in list_pickable_layers(project):
        if item['id'] == layer_id:
            return item['group_path']
    return []


def get_layer_by_id(layer_id, project=None):
    project = project or QgsProject.instance()
    return project.mapLayer(layer_id)
