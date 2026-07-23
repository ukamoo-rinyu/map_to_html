# -*- coding: utf-8 -*-
"""Tab 2 (subset): screen size / responsive / initial view / zoom
limits only (spec 3.1, Tab 2). Widgets (scale bar, geolocate, ...) and
the layer-list panel are phase 2 (spec section 6)."""
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QGroupBox,
    QCheckBox, QRadioButton, QButtonGroup, QSpinBox, QDoubleSpinBox,
    QComboBox, QLineEdit,
)

BASEMAP_OPTIONS = [
    ('carto_light', 'CARTO Light（明るい配色・既定）'),
    ('osm', 'OpenStreetMap 標準'),
    ('gsi_pale', '国土地理院 淡色地図'),
    ('gsi_standard', '国土地理院 標準地図'),
]


class DisplayTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)

        grp_size = QGroupBox(self.tr('画面サイズ・レスポンシブ'))
        lay_size = QVBoxLayout(grp_size)
        self.rb_fullscreen = QRadioButton(self.tr('画面いっぱいに表示（フルスクリーン相当）'))
        self.rb_fullscreen.setChecked(True)
        self.rb_fixed = QRadioButton(self.tr('固定サイズで表示'))
        self.size_group = QButtonGroup(self)
        self.size_group.addButton(self.rb_fullscreen)
        self.size_group.addButton(self.rb_fixed)
        lay_size.addWidget(self.rb_fullscreen)

        row_fixed = QHBoxLayout()
        row_fixed.addWidget(self.rb_fixed)
        row_fixed.addWidget(QLabel(self.tr('幅(px):')))
        self.sp_width = QSpinBox()
        self.sp_width.setRange(200, 8000)
        self.sp_width.setValue(960)
        row_fixed.addWidget(self.sp_width)
        row_fixed.addWidget(QLabel(self.tr('高さ(px):')))
        self.sp_height = QSpinBox()
        self.sp_height.setRange(200, 8000)
        self.sp_height.setValue(640)
        row_fixed.addWidget(self.sp_height)
        row_fixed.addStretch()
        lay_size.addLayout(row_fixed)

        self.rb_fixed.toggled.connect(self._update_fixed_enabled)
        self._update_fixed_enabled()

        self.chk_responsive = QCheckBox(self.tr('スマートフォン対応（レスポンシブ）'))
        self.chk_responsive.setChecked(True)
        lay_size.addWidget(self.chk_responsive)

        root.addWidget(grp_size)

        grp_view = QGroupBox(self.tr('初期表示位置・ズーム'))
        lay_view = QVBoxLayout(grp_view)
        self.rb_autofit = QRadioButton(self.tr('データの範囲に自動フィット'))
        self.rb_autofit.setChecked(True)
        self.rb_manual = QRadioButton(self.tr('中心座標・ズームレベルを手動指定'))
        self.view_group = QButtonGroup(self)
        self.view_group.addButton(self.rb_autofit)
        self.view_group.addButton(self.rb_manual)
        lay_view.addWidget(self.rb_autofit)

        row_manual = QHBoxLayout()
        row_manual.addWidget(self.rb_manual)
        row_manual.addWidget(QLabel(self.tr('緯度:')))
        self.sp_lat = QDoubleSpinBox()
        self.sp_lat.setRange(-90, 90)
        self.sp_lat.setDecimals(6)
        self.sp_lat.setValue(34.6937)
        row_manual.addWidget(self.sp_lat)
        row_manual.addWidget(QLabel(self.tr('経度:')))
        self.sp_lng = QDoubleSpinBox()
        self.sp_lng.setRange(-180, 180)
        self.sp_lng.setDecimals(6)
        self.sp_lng.setValue(135.5023)
        row_manual.addWidget(self.sp_lng)
        row_manual.addWidget(QLabel(self.tr('ズーム:')))
        self.sp_init_zoom = QSpinBox()
        self.sp_init_zoom.setRange(0, 24)
        self.sp_init_zoom.setValue(13)
        row_manual.addWidget(self.sp_init_zoom)
        row_manual.addStretch()
        lay_view.addLayout(row_manual)

        self.rb_manual.toggled.connect(self._update_manual_enabled)
        self._update_manual_enabled()

        form_zoom = QFormLayout()
        self.sp_min_zoom = QSpinBox()
        self.sp_min_zoom.setRange(0, 24)
        self.sp_min_zoom.setValue(5)
        form_zoom.addRow(self.tr('最小ズームレベル:'), self.sp_min_zoom)
        self.sp_max_zoom = QSpinBox()
        self.sp_max_zoom.setRange(0, 24)
        self.sp_max_zoom.setValue(19)
        form_zoom.addRow(self.tr('最大ズームレベル:'), self.sp_max_zoom)
        lay_view.addLayout(form_zoom)

        root.addWidget(grp_view)

        grp_basemap = QGroupBox(self.tr('背景地図（ベースマップ）'))
        lay_basemap = QVBoxLayout(grp_basemap)
        # v0.3.0 task 2-2: whether to publish a basemap at all is
        # decided here, before generating the site - NOT as an on/off
        # toggle inside the generated HTML's own layer panel (spec
        # feedback: a runtime toggle there was confusing/unwanted).
        self.chk_basemap = QCheckBox(self.tr('背景地図を表示する'))
        self.chk_basemap.setChecked(True)
        self.chk_basemap.toggled.connect(self._update_basemap_enabled)
        lay_basemap.addWidget(self.chk_basemap)
        row_basemap = QHBoxLayout()
        row_basemap.addWidget(QLabel(self.tr('地図タイル:')))
        self.cb_basemap = QComboBox()
        for key, label in BASEMAP_OPTIONS:
            self.cb_basemap.addItem(self.tr(label), key)
        row_basemap.addWidget(self.cb_basemap, 1)
        lay_basemap.addLayout(row_basemap)
        self._update_basemap_enabled()
        root.addWidget(grp_basemap)

        grp_popup = QGroupBox(self.tr('ポップアップ・ホバー動作・帰属表示'))
        lay_popup = QVBoxLayout(grp_popup)
        self.rb_popup_click = QRadioButton(self.tr('クリック時にポップアップを表示（既定、ホバー時はハイライトのみ）'))
        self.rb_popup_click.setChecked(True)
        self.rb_popup_hover = QRadioButton(self.tr('マウスを乗せた（ホバー）時にポップアップも表示'))
        self.rb_popup_none = QRadioButton(self.tr('ホバー（マウスオーバー）の効果なし（クリックのみ）'))
        self.popup_group = QButtonGroup(self)
        self.popup_group.addButton(self.rb_popup_click)
        self.popup_group.addButton(self.rb_popup_hover)
        self.popup_group.addButton(self.rb_popup_none)
        lay_popup.addWidget(self.rb_popup_click)
        lay_popup.addWidget(self.rb_popup_hover)
        lay_popup.addWidget(self.rb_popup_none)

        row_attribution = QHBoxLayout()
        row_attribution.addWidget(QLabel(self.tr('帰属表示（自由入力）:')))
        self.le_attribution = QLineEdit()
        self.le_attribution.setPlaceholderText(self.tr('例: ○○市 提供データ'))
        row_attribution.addWidget(self.le_attribution, 1)
        lay_popup.addLayout(row_attribution)
        lay_popup.addWidget(QLabel(self.tr(
            '背景地図（OpenStreetMap／CARTO／国土地理院等）の帰属表示に追記されます。既存の表示は消えません。'
        )))

        root.addWidget(grp_popup)

        root.addStretch()

    def _update_fixed_enabled(self):
        enabled = self.rb_fixed.isChecked()
        self.sp_width.setEnabled(enabled)
        self.sp_height.setEnabled(enabled)

    def _update_basemap_enabled(self):
        self.cb_basemap.setEnabled(self.chk_basemap.isChecked())

    def _update_manual_enabled(self):
        enabled = self.rb_manual.isChecked()
        self.sp_lat.setEnabled(enabled)
        self.sp_lng.setEnabled(enabled)
        self.sp_init_zoom.setEnabled(enabled)

    def validate(self):
        errors = []
        if self.sp_min_zoom.value() > self.sp_max_zoom.value():
            errors.append(self.tr('最小ズームレベルは最大ズームレベル以下にしてください。'))
        return errors

    def get_settings(self):
        if self.rb_fixed.isChecked():
            size_mode = 'fixed'
        else:
            size_mode = 'fullscreen'

        if self.rb_manual.isChecked():
            initial_view = {
                'mode': 'manual',
                'center': [self.sp_lat.value(), self.sp_lng.value()],
                'zoom': self.sp_init_zoom.value(),
            }
        else:
            initial_view = {'mode': 'autoFit'}

        display = {
            'sizeMode': size_mode,
            'fixedSize': {'width': self.sp_width.value(), 'height': self.sp_height.value()},
            'responsive': self.chk_responsive.isChecked(),
            'initialView': initial_view,
            'minZoom': self.sp_min_zoom.value(),
            'maxZoom': self.sp_max_zoom.value(),
            'basemap': self.cb_basemap.currentData(),
            'basemapEnabled': self.chk_basemap.isChecked(),
            'popupTrigger': (
                'hover' if self.rb_popup_hover.isChecked()
                else 'none' if self.rb_popup_none.isChecked()
                else 'click'
            ),
            'attribution': self.le_attribution.text().strip(),
        }
        return display
