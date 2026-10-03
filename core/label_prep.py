# -*- coding: utf-8 -*-
"""Batch label preparation for HTML export (ラベル設定 tab).

Merged in from the separate "Map to HTML Label Prep" plugin (v0.2.0).
No user interface here - ui/label_tab.py is the screen, this module
only reads and writes a layer's label settings.

The style name, custom-property key and project scope below are the
SAME ones the standalone plugin uses, on purpose: both plugins may be
installed side by side for a while, and a project prepared with one
must keep working from the other (manual buffer colours, the "Web"
style and the remembered working style are all shared, not copied).
"""
import json
import os

from qgis.core import (
    QgsPalLayerSettings,
    QgsVectorLayerSimpleLabeling,
    QgsSingleSymbolRenderer,
    QgsCategorizedSymbolRenderer,
    QgsGraduatedSymbolRenderer,
    QgsProject,
)
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QColor, QFont

# --- Smooth over the differences between QGIS versions ---------------
try:
    from qgis.core import Qgis
    PLACEMENT_HORIZONTAL = Qgis.LabelPlacement.Horizontal
    PLACEMENT_CURVED = Qgis.LabelPlacement.Curved
    PLACEMENT_OVER_POINT = Qgis.LabelPlacement.OverPoint
except Exception:  # QGIS 3.22 and similar
    PLACEMENT_HORIZONTAL = QgsPalLayerSettings.Horizontal
    PLACEMENT_CURVED = QgsPalLayerSettings.Curved
    PLACEMENT_OVER_POINT = QgsPalLayerSettings.OverPoint

try:
    from qgis.core import Qgis
    UNIT_POINTS = Qgis.RenderUnit.Points
except Exception:
    from qgis.core import QgsUnitTypes
    UNIT_POINTS = QgsUnitTypes.RenderPoints

try:
    from qgis.core import Qgis
    POINT_GEOMETRY = Qgis.GeometryType.Point
except Exception:
    from qgis.core import QgsWkbTypes
    POINT_GEOMETRY = QgsWkbTypes.PointGeometry


# --- Names stored in the project file (never translated, shared with
# the standalone Label Prep plugin) ----------------------------------
WEB_STYLE_NAME = 'Web'
LEGACY_STYLE_NAMES = ('Web用',)          # Label Prep v0.1.x
BASE_STYLE_PROP = 'mthlp/base_style'     # remembers the working style name
PROJECT_SCOPE = 'MapToHtmlLabelPrep'     # where manual colours are stored

PRESET_DIR = os.path.join(os.path.dirname(__file__), 'label_presets')
DEFAULT_PRESET = {
    'font_family': 'Noto Sans JP', 'font_family_latin': 'Arial',
    'size': 10, 'text_color': '#000000',
    'buffer': {'enabled': True, 'size': 1.2, 'fallback_color': '#FFFFFF'},
    'scale_min': 25000, 'scale_max': 0,
}


def tr(message):
    return QCoreApplication.translate('LabelPrep', message)


def load_preset(filename='web_pc.json'):
    """The preset as a dict; falls back to DEFAULT_PRESET so the tab
    keeps working even if the JSON file can't be read."""
    try:
        with open(os.path.join(PRESET_DIR, filename), 'r', encoding='utf-8') as handle:
            return json.load(handle)
    except Exception:
        return dict(DEFAULT_PRESET)


# ==================================================================
# 1. Symbol colour -> buffer colour
# ==================================================================

def symbol_color(layer):
    """(QColor or None, description). Classified renderers with more
    than one colour can't be reduced to a single colour -> None."""
    renderer = layer.renderer()
    if renderer is None:
        return None, tr('シンボルなし')

    if isinstance(renderer, QgsSingleSymbolRenderer):
        symbol = renderer.symbol()
        if symbol is not None:
            return QColor(symbol.color()), tr('単一シンボル')
        return None, tr('シンボルなし')

    if isinstance(renderer, (QgsCategorizedSymbolRenderer, QgsGraduatedSymbolRenderer)):
        items = (renderer.categories() if isinstance(renderer, QgsCategorizedSymbolRenderer)
                 else renderer.ranges())
        colors = {item.symbol().color().name() for item in items if item.symbol() is not None}
        if len(colors) == 1:
            return QColor(colors.pop()), tr('分類（実質1色）')
        return None, tr('複数色')

    return None, tr('対応外のシンボル')


def auto_buffer_color(base_color, lightness=0.78, min_saturation=0.5):
    """Keep the hue, pin lightness to 78% (a highlighter-pen look that
    black text stays readable on), floor the saturation so pale symbols
    don't turn white. lighter() isn't used because its result depends
    on how light the input already was."""
    if base_color is None:
        return None

    h, s, _l, _a = base_color.getHslF()
    # Achromatic colours keep a neutral grey. Qt reports hue -1 for
    # pure greys but hue 0 (red) with zero saturation for e.g. #303030,
    # which would otherwise turn black layers pink.
    if h < 0 or s < 0.05:
        return QColor.fromHslF(0.0, 0.0, lightness, 1.0)

    s = max(s, min_saturation)
    return QColor.fromHslF(h, min(1.0, s), lightness, 1.0)


def is_too_dark_for_black_text(color, threshold=0.55):
    """Luminance-weighted, since green reads brighter than blue."""
    if color is None:
        return False
    r, g, b, _a = color.getRgbF()
    return 0.299 * r + 0.587 * g + 0.114 * b < threshold


# ==================================================================
# 2. Manually picked colours (stored in the project file, keyed by
#    layer name since layer ids change when a project is rebuilt)
# ==================================================================

def read_override(layer_name):
    value, ok = QgsProject.instance().readEntry(
        PROJECT_SCOPE, 'buffer_overrides/' + layer_name, '')
    if ok and value:
        color = QColor(value)
        if color.isValid():
            return color
    return None


def write_override(layer_name, color):
    QgsProject.instance().writeEntry(
        PROJECT_SCOPE, 'buffer_overrides/' + layer_name,
        color.name() if color else '')


def buffer_color_for(layer):
    """(buffer QColor or None, is_manual, source description)."""
    base_color, source = symbol_color(layer)
    override = read_override(layer.name())
    if override is not None:
        return override, True, source
    return auto_buffer_color(base_color), False, source


# ==================================================================
# 3. Switching styles ("undo" is just switching back)
# ==================================================================

def switch_to_web_style(layer):
    """Remember the current style, then switch to the "Web" style
    (created from the layer's current look if it doesn't exist yet)."""
    manager = layer.styleManager()

    for legacy in LEGACY_STYLE_NAMES:
        if legacy in manager.styles() and WEB_STYLE_NAME not in manager.styles():
            manager.renameStyle(legacy, WEB_STYLE_NAME)

    current = manager.currentStyle()
    if current != WEB_STYLE_NAME:
        layer.setCustomProperty(BASE_STYLE_PROP, current)

    if WEB_STYLE_NAME not in manager.styles():
        manager.addStyleFromLayer(WEB_STYLE_NAME)

    manager.setCurrentStyle(WEB_STYLE_NAME)
    return True


def restore_base_style(layer):
    """Switch back to the working style."""
    manager = layer.styleManager()
    base = layer.customProperty(BASE_STYLE_PROP, '')

    if base and base in manager.styles():
        manager.setCurrentStyle(base)
        return True

    others = [s for s in manager.styles() if s != WEB_STYLE_NAME]
    if others:
        manager.setCurrentStyle(others[0])
        return True
    return False


def is_web_style_active(layer):
    return layer.styleManager().currentStyle() == WEB_STYLE_NAME


# ==================================================================
# 4. Applying the preset
# ==================================================================

def can_apply(layer):
    """(ok, reason). Checked before switching styles, so a layer that
    would be skipped isn't left on an untouched "Web" style copy."""
    labeling = layer.labeling()
    if labeling is None:
        return False, tr('ラベル未設定（スキップ）')
    if labeling.type() != 'simple':
        return False, tr('ルールベースラベル（現在は対象外）')
    return True, ''


def apply_preset(layer, preset, buffer_color, flags):
    """Apply the preset items ticked in `flags` ({"font": True, ...})
    to one layer. Returns (succeeded, message)."""
    ok, reason = can_apply(layer)
    if not ok:
        return False, reason
    labeling = layer.labeling()

    # Edit a copy so the original is never half-written.
    settings = QgsPalLayerSettings(labeling.settings())
    text_format = settings.format()

    if flags.get('font'):
        family = preset.get('font_family', 'Noto Sans JP')
        latin_family = preset.get('font_family_latin', '')
        font = QFont(family)
        if latin_family and hasattr(font, 'setFamilies'):
            # Qt picks a family per character: Latin letters/digits use
            # the Latin font, kanji/kana fall back to the Japanese one.
            font.setFamilies([latin_family, family])
        text_format.setFont(font)

    if flags.get('size'):
        text_format.setSizeUnit(UNIT_POINTS)
        text_format.setSize(float(preset.get('size', 10)))

    if flags.get('color'):
        text_format.setColor(QColor(preset.get('text_color', '#000000')))

    if flags.get('buffer'):
        buffer_cfg = preset.get('buffer', {})
        buffer = text_format.buffer()
        buffer.setEnabled(bool(buffer_cfg.get('enabled', True)))
        buffer.setSizeUnit(UNIT_POINTS)
        buffer.setSize(float(buffer_cfg.get('size', 1.2)))
        buffer.setColor(buffer_color if buffer_color is not None
                        else QColor(buffer_cfg.get('fallback_color', '#FFFFFF')))
        text_format.setBuffer(buffer)

    settings.setFormat(text_format)

    if flags.get('placement'):
        # Curved labels have no Leaflet equivalent. Point layers keep
        # around-the-point placement, which horizontal would collide.
        if layer.geometryType() == POINT_GEOMETRY:
            settings.placement = PLACEMENT_OVER_POINT
        else:
            settings.placement = PLACEMENT_HORIZONTAL

    if flags.get('scale'):
        settings.scaleVisibility = True
        # minimumScale is the denominator when zoomed furthest out:
        # 25000 = labels only at 1:25,000 and closer.
        settings.minimumScale = float(preset.get('scale_min', 25000))
        settings.maximumScale = float(preset.get('scale_max', 0))

    layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
    layer.setLabelsEnabled(True)
    layer.triggerRepaint()
    return True, tr('適用しました')


# ==================================================================
# 5. HTML export compatibility check (warnings only)
# ==================================================================

def diagnose(layer):
    labeling = layer.labeling()
    if labeling is None:
        return [tr('ラベル未設定')]
    if labeling.type() != 'simple':
        return [tr('ルールベースラベル（現在は対象外）')]

    warnings = []
    if not layer.labelsEnabled():
        warnings.append(tr('ラベル表示がオフ（適用するとオンになります）'))
    settings = labeling.settings()

    if settings.placement == PLACEMENT_CURVED:
        warnings.append(tr('曲線ラベル → 水平に変換されます'))

    callout = settings.callout()
    if callout is not None and callout.enabled():
        warnings.append(tr('引き出し線は出力されません'))

    if getattr(settings, 'geometryGeneratorEnabled', False):
        warnings.append(tr('ジオメトリジェネレータは再現できません'))

    text_format = settings.format()

    buffer = text_format.buffer()
    if buffer.enabled() and is_too_dark_for_black_text(buffer.color()):
        warnings.append(tr('バッファが濃く、黒文字が読みにくい可能性'))

    if text_format.shadow().enabled():
        warnings.append(tr('影は再現できません（バッファで代替を推奨）'))

    font = text_format.font()
    # setFamilies() makes family() report the Latin font, so both have
    # to be checked to recognise the preset's own combination.
    families = set(font.families()) if hasattr(font, 'families') else set()
    families.add(font.family())
    families.discard('')
    if families and not families & {'Noto Sans JP', 'Arial', 'sans-serif'}:
        warnings.append(tr('フォント「{0}」は閲覧環境で置き換わる可能性').format(font.family()))

    return warnings
