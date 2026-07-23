# -*- coding: utf-8 -*-
"""Publish a QGIS raster layer that's an XYZ tile source (added via
Layer > Add Layer > Add XYZ Layer - the common way someone adds a
basemap like a 国土地理院 tile layer into a QGIS project) as a Leaflet
tile layer in the web output. This lets any such layer be picked and
published as-is, instead of forcing basemap choice into a fixed
built-in list. Non-XYZ rasters (local files, WMS, WMTS, ...) aren't
supported - callers should catch ValueError and skip/report those.
"""
from urllib.parse import parse_qs


def read_native_opacity(layer):
    """QGIS's own layer transparency (Layer Properties > Symbology, or
    the Layers panel's own opacity slider) - previously ignored
    entirely when publishing a raster/XYZ layer (v0.3.0 task 2-3: every
    output rendered such layers fully opaque no matter what was set in
    QGIS). Used both as the value actually written to style.json
    (unless the plugin's own per-layer opacity override in
    ui/data_tab.py replaces it) and as the fallback default that
    override starts from for the first raster layer added in a
    session."""
    try:
        return float(layer.renderer().opacity())
    except Exception:
        return 1.0


def extract_tile_style(layer, opacity_override=None):
    """`opacity_override` (0.0-1.0), when given, is the value from the
    plugin's own per-layer opacity control (ui/data_tab.py, v0.3.0 task
    2-3) - takes precedence over the layer's native QGIS opacity so the
    user can adjust it per layer without changing the QGIS project
    itself."""
    source = layer.source() or ''
    params = parse_qs(source)
    if params.get('type', [''])[0] != 'xyz' or not params.get('url'):
        raise ValueError(
            'レイヤー「{0}」はXYZタイル形式のラスターレイヤーではないため、'
            'Web出力では未対応です（ローカルファイルやWMS/WMTSは非対応）。'.format(layer.name())
        )

    tile = {'url': params['url'][0]}
    if params.get('zmin'):
        try:
            tile['minZoom'] = int(params['zmin'][0])
        except ValueError:
            pass
    if params.get('zmax'):
        try:
            tile['maxNativeZoom'] = int(params['zmax'][0])
        except ValueError:
            pass
    opacity = opacity_override if opacity_override is not None else read_native_opacity(layer)
    tile['opacity'] = round(opacity, 2)
    return {'defaultStyle': {'tile': tile}}
