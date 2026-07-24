# -*- coding: utf-8 -*-
"""Build the config.json dict (spec section 4, reworked at user
request to match qgis2web's "show everything" model instead of a
single search-target + reference-layer split). Per-layer field
mapping still lives on the layer itself (ui/field_dialog.py); search
(searchEnabled) and the per-layer feature table (featureTableEnabled)
reuse those same fields rather than adding their own picker.
"""
import datetime


def build_config(settings):
    """`settings` is the plain dict assembled by the dialog:
    {
      'title': str,
      'display': {
        'sizeMode': 'fullscreen' | 'fixed',
        'fixedSize': {'width': int, 'height': int},   # only if sizeMode == 'fixed'
        'responsive': bool,
        'initialView': {'mode': 'autoFit'} or
                        {'mode': 'manual', 'center': [lat, lng], 'zoom': int},
        'minZoom': int,
        'maxZoom': int,
      },
      'theme': {
        'title_color': str, 'header_bg_color': str, 'font_family': str,
      },
      'layers': [
        {'id': str, 'label': str, 'defaultVisible': bool, 'showPopup': bool,
         'groupPath': [str, ...]}, ...
      ],
    }
    """
    display = settings['display']
    theme = settings.get('theme') or {}
    generated_at = datetime.datetime.now().astimezone().isoformat(timespec='seconds')

    config = {
        'meta': {
            'title': settings.get('title') or 'Facility Search',
            'generatedAt': generated_at,
        },
        'display': {
            'sizeMode': display['sizeMode'],
            'responsive': bool(display['responsive']),
            'initialView': display['initialView'],
            'minZoom': display['minZoom'],
            'maxZoom': display['maxZoom'],
            'basemap': display.get('basemap') or 'carto_light',
            'basemapEnabled': bool(display.get('basemapEnabled', True)),
            'searchEnabled': bool(display.get('searchEnabled', True)),
            'featureTableEnabled': bool(display.get('featureTableEnabled', True)),
            'popupTrigger': display.get('popupTrigger') or 'click',
            'attribution': display.get('attribution') or '',
        },
        'theme': {
            'titleColor': theme.get('title_color'),
            'headerBgColor': theme.get('header_bg_color'),
            'fontFamily': theme.get('font_family'),
        },
        'layers': [
            {
                'id': layer['id'],
                'label': layer['label'],
                'defaultVisible': bool(layer['defaultVisible']),
                'showPopup': bool(layer.get('showPopup', True)),
                'geojsonKey': layer['id'],
                'groupPath': list(layer.get('groupPath') or []),
            }
            for layer in settings.get('layers', [])
        ],
    }
    if display['sizeMode'] == 'fixed':
        config['display']['fixedSize'] = display['fixedSize']

    return config
