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


def extract_tile_style(layer):
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
    return {'defaultStyle': {'tile': tile}}
