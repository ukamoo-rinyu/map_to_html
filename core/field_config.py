# -*- coding: utf-8 -*-
"""Per-layer popup field configuration: which attributes show in the
web output's click popup, and in what order (ui/field_dialog.py, Tab
1's ポップアップ項目 設定… button). Persisted on the QGIS layer itself
via a custom property, so it survives closing/reopening the plugin
dialog and is carried along when the QGIS project (.qgz/.qgs) is
saved - the user asked for the setting to be "saved" without wanting
a separate settings file, and QGIS custom properties are exactly this
kind of per-layer, project-persisted plugin state.
"""
import json

CUSTOM_PROPERTY_KEY = 'facility_app_generator/popup_fields'


def default_field_config(layer):
    """Every field, in the layer's own order, all visible - what a
    layer that's never been configured gets."""
    return [{'name': name, 'visible': True} for name in layer.fields().names()]


def load_field_config(layer):
    """Return the persisted [{'name', 'visible'}, ...] for `layer`, or
    None if nothing was ever saved for it (or the saved value is
    unreadable, e.g. from a much older/incompatible version)."""
    raw = layer.customProperty(CUSTOM_PROPERTY_KEY)
    if not raw:
        return None
    try:
        config = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(config, list):
        return None
    return config


def save_field_config(layer, config):
    layer.setCustomProperty(CUSTOM_PROPERTY_KEY, json.dumps(config, ensure_ascii=False))


def reconcile_field_config(layer, config):
    """Adapt a (possibly stale, or from a different layer) config to
    `layer`'s actual current fields: drop entries for fields that no
    longer exist, keep the rest in their given order, then append any
    of the layer's fields the config didn't mention (new fields added
    since the config was saved, or fields simply absent from a config
    borrowed from another layer via the "同グループにコピー" button)
    as visible, in the layer's own field order."""
    layer_names = layer.fields().names()
    layer_name_set = set(layer_names)
    reconciled = [entry for entry in config if entry.get('name') in layer_name_set]
    known = {entry['name'] for entry in reconciled}
    for name in layer_names:
        if name not in known:
            reconciled.append({'name': name, 'visible': True})
    return reconciled


def visible_field_order(config):
    """The ordered list of field names to actually include, for
    core/geojson_writer.py's `field_order` param."""
    return [entry['name'] for entry in config if entry.get('visible', True)]
