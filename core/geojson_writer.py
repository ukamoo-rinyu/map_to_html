# -*- coding: utf-8 -*-
"""Write the search-target layer out as WGS84 GeoJSON (spec 4.1)."""
from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsVectorLayer, QgsField, QgsFeature, QgsFields, QgsGeometry,
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject,
    QgsVectorFileWriter, QgsWkbTypes,
)


AUTO_ID_FIELD = '_fid'


def write_sites_geojson(layer, output_path, label_text_evaluator, id_field=None, field_order=None):
    """Write `layer`'s features to a WGS84 (EPSG:4326) GeoJSON, adding a
    pre-evaluated 'label_text' attribute to every feature (spec 4.1,
    4.2.1.1). Original attribute names are kept as-is; config.json's
    `fields` block references those same names directly instead of the
    plugin renaming them on export (spec 4.1, "config側でマッピング").
    `field_order` (an ordered list of field names, from
    core/field_config.py's per-layer picker in Tab 1) controls both
    which attributes reach the GeoJSON at all and the order they're
    written in - the popup just iterates the GeoJSON properties object
    in insertion order, so this is also what decides popup row order.
    None means "every field, in the layer's own order" (unconfigured).

    If `id_field` is None (user didn't map an ID attribute in Tab 1), a
    stable auto-incrementing '_fid' attribute is added so the template's
    JS has a reliable key to correlate map markers with list rows.
    Returns (output_path, id_field_used).
    """
    dest_crs = QgsCoordinateReferenceSystem('EPSG:4326')
    transform = QgsCoordinateTransform(layer.crs(), dest_crs, QgsProject.instance())

    layer_fields = layer.fields()
    all_names = layer_fields.names()
    if field_order is None:
        field_order = list(all_names)
    else:
        # Guard against a stale/borrowed config naming a field that
        # doesn't actually exist on this layer.
        field_order = [name for name in field_order if name in all_names]

    out_fields = QgsFields()
    for name in field_order:
        idx = layer_fields.indexFromName(name)
        if idx >= 0:
            out_fields.append(layer_fields.field(idx))
    if out_fields.indexOf('label_text') < 0:
        out_fields.append(QgsField('label_text', QVariant.String))
    needs_auto_id = not id_field
    if needs_auto_id and out_fields.indexOf(AUTO_ID_FIELD) < 0:
        out_fields.append(QgsField(AUTO_ID_FIELD, QVariant.Int))

    geom_type_str = QgsWkbTypes.displayString(layer.wkbType())
    mem_layer = QgsVectorLayer(f'{geom_type_str}?crs=EPSG:4326', 'sites', 'memory')
    mem_layer.dataProvider().addAttributes(out_fields)
    mem_layer.updateFields()

    source_field_names = field_order
    new_features = []
    for index, feature in enumerate(layer.getFeatures()):
        new_feature = QgsFeature(out_fields)
        geom = feature.geometry()
        if geom is not None and not geom.isEmpty():
            geom = QgsGeometry(geom)
            geom.transform(transform)
        new_feature.setGeometry(geom)
        for field_name in source_field_names:
            new_feature[field_name] = feature[field_name]
        new_feature['label_text'] = label_text_evaluator(feature)
        if needs_auto_id:
            new_feature[AUTO_ID_FIELD] = index
        new_features.append(new_feature)

    mem_layer.dataProvider().addFeatures(new_features)
    mem_layer.updateExtents()

    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = 'GeoJSON'
    options.fileEncoding = 'UTF-8'
    # 6 decimal degrees is ~11cm at the equator - far finer than a
    # facility map needs, but far shorter than the ~15 significant
    # digits a raw double coordinate would otherwise write, which adds
    # up fast across thousands of features (qgis2web does the same).
    options.layerOptions = ['COORDINATE_PRECISION=6']

    error, msg, _, _ = QgsVectorFileWriter.writeAsVectorFormatV3(
        mem_layer, output_path, QgsProject.instance().transformContext(), options
    )
    if error != QgsVectorFileWriter.NoError:
        raise RuntimeError(f'GeoJSON export failed: {msg}')
    return output_path, (id_field or AUTO_ID_FIELD)
