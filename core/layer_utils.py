# -*- coding: utf-8 -*-
"""Helpers for reading layers out of the current QGIS project."""
from qgis.core import QgsProject, QgsVectorLayer, QgsRasterLayer, QgsLayerTreeNode


def _walk_layers(node, path, results):
    for child in node.children():
        if child.nodeType() == QgsLayerTreeNode.NodeGroup:
            _walk_layers(child, path + [child.name()], results)
        else:  # NodeLayer
            layer = child.layer()
            if isinstance(layer, QgsVectorLayer):
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
