# -*- coding: utf-8 -*-
"""The dialog's settings, kept in the QGIS project between sessions
(spec phase 4: 設定の保存・読み込み). Saved when an HTML is generated
and when the dialog closes, restored when it opens - so a map that is
re-exported after every data update doesn't need its settings re-done
each time. Like the per-layer popup/filter fields (core/field_config.py)
it lives in the project file, so it is kept once the project is saved,
and each project remembers its own.
"""
import json

from qgis.core import QgsProject, QgsSettings

SCOPE = 'MapToHtml'
KEY = 'dialog_state'
VERSION = 1


def load():
    """The saved {'data': [...], 'display': {...}, 'output': {...}},
    or None when this project has none (or it can't be read)."""
    raw, ok = QgsProject.instance().readEntry(SCOPE, KEY, '')
    if not ok or not raw:
        return None
    try:
        state = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(state, dict) or state.get('version') != VERSION:
        return None
    return state


def save(state):
    """Writes only when something changed: every write marks the
    project as modified, and merely opening and closing the dialog
    shouldn't make QGIS ask to save the project."""
    state = dict(state, version=VERSION)
    raw = json.dumps(state, ensure_ascii=False, sort_keys=True)
    current, ok = QgsProject.instance().readEntry(SCOPE, KEY, '')
    if ok and current == raw:
        return
    QgsProject.instance().writeEntry(SCOPE, KEY, raw)


def clear():
    QgsProject.instance().removeEntry(SCOPE, KEY)


# ---- The user's own defaults ----------------------------------------
# "今の設定を初期値に保存": the Display and Output tab settings a project
# with nothing saved yet starts from, and what 初期値に戻す returns to.
# Kept in QGIS's user settings (QgsSettings), not in a project, so they
# apply to every project. The Data tab's layer list isn't part of it -
# layers belong to a project - and neither is the title.
USER_DEFAULTS_KEY = 'map_to_html/user_defaults'


def load_user_defaults():
    raw = QgsSettings().value(USER_DEFAULTS_KEY, '')
    if not raw:
        return None
    try:
        state = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(state, dict) or state.get('version') != VERSION:
        return None
    return state


def save_user_defaults(display_state, output_state):
    output_state = {key: value for key, value in (output_state or {}).items() if key != 'title'}
    QgsSettings().setValue(USER_DEFAULTS_KEY, json.dumps(
        {'version': VERSION, 'display': display_state, 'output': output_state},
        ensure_ascii=False, sort_keys=True))
