# -*- coding: utf-8 -*-
"""Tab 2 (subset): screen size / responsive / initial view / zoom
limits only (spec 3.1, Tab 2). Widgets (scale bar, geolocate, ...) and
the layer-list panel are phase 2 (spec section 6)."""
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QGroupBox,
    QCheckBox, QRadioButton, QButtonGroup, QSpinBox, QDoubleSpinBox,
    QComboBox, QLineEdit, QSlider, QScrollArea, QFrame,
)


class DisplayTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _basemap_options(self):
        return [
            ('carto_light', self.tr('CARTO Light（明るい配色・既定）')),
            ('osm', self.tr('OpenStreetMap 標準')),
            ('gsi_pale', self.tr('国土地理院 淡色地図')),
            ('gsi_standard', self.tr('国土地理院 標準地図')),
        ]

    def _build_ui(self):
        # This tab's content is taller than a 1080p screen once every
        # settings group is present, and a QDialog can't be resized (or
        # dragged) smaller than its layout's minimum size - so the
        # window grew past the bottom of the screen and the 生成 button
        # and Close button became unreachable. Putting the content in a
        # scroll area decouples the dialog's minimum height from it.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        scroll.setWidget(content)
        outer.addWidget(scroll)

        root = QVBoxLayout(content)

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
        self.rb_canvas = QRadioButton(self.tr('現在のQGIS画面の表示範囲を初期表示にする'))
        self.rb_canvas.setToolTip(self.tr(
            'HTMLの地図とQGISの画面では縦横比が異なるため、表示範囲は完全には一致しません。'
            '指定した範囲が必ず収まるように表示されます。'
        ))
        self.rb_manual = QRadioButton(self.tr('中心座標・ズームレベルを手動指定'))
        self.view_group = QButtonGroup(self)
        self.view_group.addButton(self.rb_autofit)
        self.view_group.addButton(self.rb_canvas)
        self.view_group.addButton(self.rb_manual)
        lay_view.addWidget(self.rb_autofit)
        lay_view.addWidget(self.rb_canvas)

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
        for key, label in self._basemap_options():
            self.cb_basemap.addItem(label, key)
        row_basemap.addWidget(self.cb_basemap, 1)
        lay_basemap.addLayout(row_basemap)
        self._update_basemap_enabled()
        root.addWidget(grp_basemap)

        # ---- Scale bar (spec item 1) ----------------------------------
        grp_scale = QGroupBox(self.tr('スケールバー'))
        lay_scale = QHBoxLayout(grp_scale)
        self.chk_scalebar = QCheckBox(self.tr('スケールバーを表示する'))
        self.chk_scalebar.setChecked(True)
        self.chk_scalebar.toggled.connect(self._update_scalebar_enabled)
        lay_scale.addWidget(self.chk_scalebar)
        lay_scale.addWidget(QLabel(self.tr('表示位置:')))
        self.cb_scalebar_pos = QComboBox()
        for key, label in (
            ('bottomleft', self.tr('左下')),
            ('bottomright', self.tr('右下')),
        ):
            self.cb_scalebar_pos.addItem(label, key)
        lay_scale.addWidget(self.cb_scalebar_pos)
        lay_scale.addStretch()
        self._update_scalebar_enabled()
        root.addWidget(grp_scale)

        # ---- Fill opacity override (spec item 2) ----------------------
        grp_opacity = QGroupBox(self.tr('透過率'))
        lay_opacity = QVBoxLayout(grp_opacity)
        self.chk_opacity_override = QCheckBox(
            self.tr('塗りの透過率を上書きする（QGISの設定を無視して一律適用）')
        )
        self.chk_opacity_override.toggled.connect(self._update_opacity_enabled)
        lay_opacity.addWidget(self.chk_opacity_override)
        row_opacity = QHBoxLayout()
        row_opacity.addWidget(QLabel(self.tr('不透明度:')))
        self.sl_opacity = QSlider(Qt.Orientation.Horizontal)
        self.sl_opacity.setRange(0, 100)
        self.sl_opacity.setValue(40)
        row_opacity.addWidget(self.sl_opacity, 1)
        self.lb_opacity = QLabel('40%')
        self.lb_opacity.setMinimumWidth(40)
        self.sl_opacity.valueChanged.connect(
            lambda value: self.lb_opacity.setText('{0}%'.format(value))
        )
        row_opacity.addWidget(self.lb_opacity)
        lay_opacity.addLayout(row_opacity)
        lay_opacity.addWidget(QLabel(self.tr(
            'ポリゴンの塗りとマーカーの塗りに適用されます。枠線の色・透過率は変更しません。'
        )))
        self._update_opacity_enabled()
        root.addWidget(grp_opacity)

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

        # ---- Popup contents (spec item 7-6/7-7) -----------------------
        grp_popup_content = QGroupBox(self.tr('ポップアップの内容'))
        lay_popup_content = QVBoxLayout(grp_popup_content)
        self.chk_popup_show_empty = QCheckBox(
            self.tr('値が空の項目も表示する（既定：空の項目は表示しない）')
        )
        lay_popup_content.addWidget(self.chk_popup_show_empty)
        self.chk_popup_linkify = QCheckBox(
            self.tr('http で始まる値をリンクにする（画像URLは画像として表示）')
        )
        self.chk_popup_linkify.setChecked(True)
        lay_popup_content.addWidget(self.chk_popup_linkify)
        lay_popup_content.addWidget(QLabel(self.tr(
            '表示する項目と並び順は「データ設定」タブのレイヤーごとの「設定…」で指定します。'
            '項目名はQGISのフィールド別名（エイリアス）があればそちらを表示します。'
        )))
        root.addWidget(grp_popup_content)

        # ---- External map links (spec item 11) ------------------------
        grp_links = QGroupBox(self.tr('地図リンク'))
        lay_links = QVBoxLayout(grp_links)
        self.chk_links = QCheckBox(self.tr('ポップアップに地図リンクを表示する'))
        self.chk_links.setChecked(True)
        self.chk_links.toggled.connect(self._update_links_enabled)
        lay_links.addWidget(self.chk_links)

        # Defaults follow the spec's reasoning: the popup is narrow, so
        # only the two most-used links are on out of the box.
        self.chk_link_gmap = QCheckBox(self.tr('Googleマップで開く'))
        self.chk_link_gmap.setChecked(True)
        self.chk_link_sv = QCheckBox(self.tr('ストリートビューで見る'))
        self.chk_link_sv.setChecked(True)
        self.chk_link_dir = QCheckBox(self.tr('ここへの経路'))
        self.chk_link_gsi = QCheckBox(self.tr('地理院地図で開く（空中写真・災害情報などの確認に便利）'))
        for widget in (self.chk_link_gmap, self.chk_link_sv, self.chk_link_dir, self.chk_link_gsi):
            widget.setStyleSheet('margin-left: 18px;')
            lay_links.addWidget(widget)

        row_name = QHBoxLayout()
        self.chk_link_name = QCheckBox(self.tr('施設名でGoogle検索'))
        self.chk_link_name.setStyleSheet('margin-left: 18px;')
        self.chk_link_name.toggled.connect(self._update_links_enabled)
        row_name.addWidget(self.chk_link_name)
        row_name.addWidget(QLabel(self.tr('名称に使う項目:')))
        # Populated by set_name_fields() from the layers actually added
        # on the データ設定 tab - editable so a re-read of the tab isn't
        # required to type a field name the picker hasn't seen yet.
        self.cb_name_field = QComboBox()
        self.cb_name_field.setEditable(True)
        self.cb_name_field.setMinimumWidth(160)
        row_name.addWidget(self.cb_name_field, 1)
        lay_links.addLayout(row_name)

        self._update_links_enabled()
        root.addWidget(grp_links)

        # v0.3.0 tasks 3-1/3-2: no per-field configuration needed here -
        # both features reuse whichever fields are already visible in
        # each layer's ポップアップ項目 picker (Tab 1), so there's
        # nothing to pick beyond turning the feature itself on/off.
        grp_search_list = QGroupBox(self.tr('検索・一覧表示'))
        lay_search_list = QVBoxLayout(grp_search_list)
        self.chk_search = QCheckBox(self.tr('検索バーを表示する（施設名などで検索し、結果をクリックしてズーム表示）'))
        self.chk_search.setChecked(True)
        lay_search_list.addWidget(self.chk_search)
        self.chk_feature_table = QCheckBox(self.tr('レイヤー内地物の一覧表を表示する'))
        self.chk_feature_table.setChecked(True)
        lay_search_list.addWidget(self.chk_feature_table)
        root.addWidget(grp_search_list)

        root.addStretch()

    def _update_fixed_enabled(self):
        enabled = self.rb_fixed.isChecked()
        self.sp_width.setEnabled(enabled)
        self.sp_height.setEnabled(enabled)

    def _update_basemap_enabled(self):
        self.cb_basemap.setEnabled(self.chk_basemap.isChecked())

    def _update_scalebar_enabled(self):
        self.cb_scalebar_pos.setEnabled(self.chk_scalebar.isChecked())

    def _update_opacity_enabled(self):
        enabled = self.chk_opacity_override.isChecked()
        self.sl_opacity.setEnabled(enabled)
        self.lb_opacity.setEnabled(enabled)

    def _update_links_enabled(self):
        enabled = self.chk_links.isChecked()
        for widget in (self.chk_link_gmap, self.chk_link_sv, self.chk_link_dir,
                       self.chk_link_gsi, self.chk_link_name):
            widget.setEnabled(enabled)
        self.cb_name_field.setEnabled(enabled and self.chk_link_name.isChecked())

    def set_name_fields(self, field_names):
        """Refresh the "施設名でGoogle検索" field picker from the fields
        actually available on the added layers (dialog.py calls this
        when the データ設定 tab changes). The current selection is kept
        when that field still exists, so switching tabs back and forth
        doesn't silently retarget the link at a different column."""
        current = self.cb_name_field.currentText()
        self.cb_name_field.clear()
        self.cb_name_field.addItems(sorted(set(field_names)))
        if current:
            self.cb_name_field.setEditText(current)

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
        elif self.rb_canvas.isChecked():
            # Resolved into actual WGS84 bounds by dialog.py, which is
            # the only place with an `iface` to read the map canvas from.
            initial_view = {'mode': 'currentCanvas'}
        else:
            initial_view = {'mode': 'autoFit'}

        links = None
        if self.chk_links.isChecked():
            links = {
                'googleMaps': self.chk_link_gmap.isChecked(),
                'streetView': self.chk_link_sv.isChecked(),
                'directions': self.chk_link_dir.isChecked(),
                'gsi': self.chk_link_gsi.isChecked(),
                'nameSearch': self.chk_link_name.isChecked(),
                'nameField': self.cb_name_field.currentText().strip(),
            }
            if not any(links[key] for key in
                       ('googleMaps', 'streetView', 'directions', 'gsi', 'nameSearch')):
                # Parent checkbox on but every entry unchecked - same as off.
                links = None

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
            'searchEnabled': self.chk_search.isChecked(),
            'featureTableEnabled': self.chk_feature_table.isChecked(),
            'scaleBar': (
                {'position': self.cb_scalebar_pos.currentData()}
                if self.chk_scalebar.isChecked() else None
            ),
            'popupShowEmpty': self.chk_popup_show_empty.isChecked(),
            'popupLinkifyUrls': self.chk_popup_linkify.isChecked(),
            'popupLinks': links,
            # Not part of config.js: consumed at extraction time by
            # core/style_extractor.py, so the published page carries the
            # already-applied opacity rather than a knob to apply it.
            'fillOpacityOverride': (
                self.sl_opacity.value() / 100.0
                if self.chk_opacity_override.isChecked() else None
            ),
        }
        return display
