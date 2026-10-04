# -*- coding: utf-8 -*-
"""Tab 2: screen size / responsive / initial view / zoom limits, the
basemap, filter bar, map buttons (scale bar, current location, radius
search, link sharing), page language, popups, search/table, thinning
and selection/export (spec 3.1, Tab 2).

get_settings() is what an export uses; get_state()/set_state() are the
raw widget values the dialog keeps in the QGIS project between
sessions (core/settings_store.py)."""
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QGroupBox,
    QCheckBox, QRadioButton, QButtonGroup, QSpinBox, QDoubleSpinBox,
    QComboBox, QLineEdit, QSlider, QScrollArea, QFrame,
)

from .state_utils import widgets_state, apply_widgets_state

# Radii offered in the published page's radius search; the default
# chosen on this tab is added when it isn't one of them.
RADIUS_CHOICES = [250, 500, 1000, 2000]


class DisplayTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _basemap_options(self):
        # 国土地理院 淡色地図 is first/default: OpenStreetMap's tile
        # servers often refuse the generated page (opened from a local
        # file, it sends no Referer, which OSM's tile policy requires),
        # so the map came up blank (user report). CARTO needs an API key
        # for real traffic, so it stays last for anyone who has one.
        return [
            ('gsi_pale', self.tr('国土地理院 淡色地図（既定）')),
            ('gsi_standard', self.tr('国土地理院 標準地図')),
            ('gsi_photo', self.tr('国土地理院 航空写真')),
            ('osm', self.tr('OpenStreetMap 標準')),
            ('carto_light', self.tr('CARTO Light（明るい配色・要APIキー）')),
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
        # Off by default (user preference): most projects already add
        # their own background tile layer on the データ設定 tab.
        self.chk_basemap.setChecked(False)
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

        # ---- Filter bar - its own box near the top (spec feedback: as
        # one more checkbox inside 検索・一覧表示 at the bottom of this
        # long tab it couldn't be found), with where its fields are
        # chosen spelled out on screen rather than only in a tooltip.
        grp_filter = QGroupBox(self.tr('フィルターバー（絞り込み）'))
        lay_filter = QVBoxLayout(grp_filter)
        self.chk_filter = QCheckBox(self.tr(
            'フィルターバーを表示する（項目ごとに値を選んで、該当する地物だけを表示）'))
        self.chk_filter.setChecked(False)
        lay_filter.addWidget(self.chk_filter)
        filter_hint = QLabel(self.tr(
            '絞り込みに使う項目は、データ設定タブの各レイヤーの「ポップアップ・フィルター項目」→'
            '「設定…」で、「フィルター」列にチェックして選びます。'
            'どれか1つのレイヤーで選べば、同じ項目名を持つ他のレイヤーもまとめて絞り込まれます。'))
        filter_hint.setWordWrap(True)
        lay_filter.addWidget(filter_hint)
        root.addWidget(grp_filter)

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

        # ---- Map buttons (v0.7.0) -------------------------------------
        grp_buttons = QGroupBox(self.tr('地図上のボタン'))
        lay_buttons = QVBoxLayout(grp_buttons)
        self.chk_locate = QCheckBox(self.tr(
            '現在地ボタンを表示する（スマートフォンなどで、今いる場所を地図に表示）'))
        self.chk_locate.setChecked(True)
        self.chk_locate.setToolTip(self.tr(
            'ブラウザが位置情報の利用を確認します。位置情報は閲覧者の端末の中だけで使われ、\n'
            'どこにも送信されません。https:// で公開したページか、端末上のファイルとして\n'
            '開いたときに使えます（http:// のページではブラウザが許可しません）。'))
        lay_buttons.addWidget(self.chk_locate)

        self.chk_radius = QCheckBox(self.tr(
            '半径検索を使えるようにする（地点を決めて、指定した半径内の地物を近い順に一覧表示）'))
        self.chk_radius.setChecked(True)
        self.chk_radius.setToolTip(self.tr(
            '中心は、地図のクリック・現在地・地図の中心から選べます。\n'
            '地図に表示中のレイヤー（ポップアップ表示がオンのもの）が対象で、\n'
            'フィルターバーの絞り込みにも従います。線・面は頂点の平均の位置で測ります。'))
        self.chk_radius.toggled.connect(self._update_radius_enabled)
        lay_buttons.addWidget(self.chk_radius)
        row_radius = QHBoxLayout()
        lbl_radius = QLabel(self.tr('最初に選ばれている半径:'))
        lbl_radius.setStyleSheet('margin-left: 18px;')
        row_radius.addWidget(lbl_radius)
        self.sp_radius = QSpinBox()
        self.sp_radius.setRange(50, 50000)
        self.sp_radius.setSingleStep(50)
        self.sp_radius.setSuffix(' m')
        self.sp_radius.setValue(500)
        row_radius.addWidget(self.sp_radius)
        row_radius.addWidget(QLabel(self.tr('（閲覧者は 250m／500m／1km／2km からも選べます）')))
        row_radius.addStretch()
        lay_buttons.addLayout(row_radius)

        self.chk_share = QCheckBox(self.tr(
            'リンク共有ボタンを表示する（今の表示位置・レイヤー・絞り込みをURLにしてコピー）'))
        self.chk_share.setChecked(True)
        self.chk_share.setToolTip(self.tr(
            'コピーしたURLを開くと、同じ場所・同じレイヤー・同じ絞り込みの状態で地図が開きます。\n'
            'ファイルとして開いた地図のURLは、同じファイルを開ける人（共有フォルダなど）だけが使えます。'))
        lay_buttons.addWidget(self.chk_share)
        self._update_radius_enabled()
        root.addWidget(grp_buttons)

        # ---- Page language (spec 10.3) ---------------------------------
        grp_lang = QGroupBox(self.tr('出力HTMLの表示言語'))
        lay_lang = QVBoxLayout(grp_lang)
        row_lang = QHBoxLayout()
        row_lang.addWidget(QLabel(self.tr('最初に表示する言語:')))
        self.cb_language = QComboBox()
        for key, label in (
            ('auto', self.tr('閲覧者のブラウザに合わせる（日本語以外は英語）')),
            ('ja', self.tr('日本語')),
            ('en', self.tr('英語（English）')),
        ):
            self.cb_language.addItem(label, key)
        row_lang.addWidget(self.cb_language, 1)
        lay_lang.addLayout(row_lang)
        self.chk_lang_toggle = QCheckBox(self.tr('日本語／英語の切り替えボタンを表示する'))
        self.chk_lang_toggle.setChecked(True)
        lay_lang.addWidget(self.chk_lang_toggle)
        lang_hint = QLabel(self.tr(
            'ボタンや案内の文言が切り替わります。レイヤー名・項目名・値は、QGISのデータのまま表示されます。'))
        lang_hint.setWordWrap(True)
        lay_lang.addWidget(lang_hint)
        root.addWidget(grp_lang)

        # ---- Fill opacity override (spec item 2) ----------------------
        grp_opacity = QGroupBox(self.tr('不透明度'))
        lay_opacity = QVBoxLayout(grp_opacity)
        self.chk_opacity_override = QCheckBox(
            self.tr('塗りの不透明度を上書きする（QGISの設定を無視して一律適用）')
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
            'ポリゴンの塗りとマーカーの塗りに適用されます。枠線の色・不透明度は変更しません。'
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

        # ---- Point thinning at wide zooms (spec item 6-B) -------------
        grp_thin = QGroupBox(self.tr('広域表示時の間引き'))
        lay_thin = QVBoxLayout(grp_thin)
        self.chk_thinning = QCheckBox(
            self.tr('広域表示のときポイントを間引いて表示する')
        )
        self.chk_thinning.setToolTip(self.tr(
            '指定したズームより広域では、画面を格子に区切って1マスにつき1件だけ\n'
            '描画し、密集した点が団子にならないようにします。\n'
            '※間引くのは「描画」だけです。検索・一覧表・CSV出力には全件が\n'
            '　含まれますし、拡大すれば全件表示に戻ります。'
        ))
        self.chk_thinning.toggled.connect(self._update_thinning_enabled)
        lay_thin.addWidget(self.chk_thinning)

        row_thin = QHBoxLayout()
        row_thin.addWidget(QLabel(self.tr('このズーム未満で間引く:')))
        self.sp_thin_zoom = QSpinBox()
        self.sp_thin_zoom.setRange(0, 24)
        self.sp_thin_zoom.setValue(14)
        row_thin.addWidget(self.sp_thin_zoom)
        row_thin.addWidget(QLabel(self.tr('格子の大きさ(px):')))
        self.sp_thin_grid = QSpinBox()
        self.sp_thin_grid.setRange(8, 200)
        self.sp_thin_grid.setValue(32)
        row_thin.addWidget(self.sp_thin_grid)
        row_thin.addStretch()
        lay_thin.addLayout(row_thin)
        lay_thin.addWidget(QLabel(self.tr(
            '間引いている間は「一部の地物のみ表示中」と画面に表示されます。'
        )))
        self._update_thinning_enabled()
        root.addWidget(grp_thin)

        # ---- Selection + data export (spec item 9) --------------------
        grp_export = QGroupBox(self.tr('地物の選択・データ出力'))
        lay_export = QVBoxLayout(grp_export)
        self.chk_selection = QCheckBox(
            self.tr('地物の選択とCSV/GeoJSON出力を使えるようにする')
        )
        self.chk_selection.setToolTip(self.tr(
            'クリック／Ctrl+クリック／範囲（矩形）で地物を選択し、選択分または\n'
            'レイヤー全体をCSV・GeoJSONでダウンロードできるようになります。\n'
            'ボタンは一覧表パネルの下部に表示されます（一覧表の表示が必要です）。'
        ))
        self.chk_selection.toggled.connect(self._update_selection_enabled)
        lay_export.addWidget(self.chk_selection)

        self.chk_force_text_codes = QCheckBox(self.tr(
            'ゼロ始まりの番号をExcelで欠けないよう ="0123" 形式で出力する'
        ))
        self.chk_force_text_codes.setToolTip(self.tr(
            '施設コードなど先頭が0の値は、通常のCSVだとExcelで開いた時に\n'
            '0が消えて「123」になります。この形式なら消えませんが、\n'
            'Excel以外のツールに取り込む場合は ="..." が邪魔になることがあります。'
        ))
        self.chk_pretty_geojson = QCheckBox(
            self.tr('GeoJSONを整形して出力する（読みやすいがファイルは大きくなる）')
        )
        for widget in (self.chk_force_text_codes, self.chk_pretty_geojson):
            widget.setStyleSheet('margin-left: 18px;')
            lay_export.addWidget(widget)
        lay_export.addWidget(QLabel(self.tr(
            'CSVはBOM付きUTF-8で出力するため、Excelで開いても文字化けしません。'
            '緯度・経度の列が自動で追加されます（面・線は重心）。'
        )))
        self._update_selection_enabled()
        root.addWidget(grp_export)

        root.addStretch()

    def _update_fixed_enabled(self):
        enabled = self.rb_fixed.isChecked()
        self.sp_width.setEnabled(enabled)
        self.sp_height.setEnabled(enabled)

    def _update_radius_enabled(self):
        self.sp_radius.setEnabled(self.chk_radius.isChecked())

    def _update_basemap_enabled(self):
        self.cb_basemap.setEnabled(self.chk_basemap.isChecked())

    def _update_scalebar_enabled(self):
        self.cb_scalebar_pos.setEnabled(self.chk_scalebar.isChecked())

    def _update_opacity_enabled(self):
        enabled = self.chk_opacity_override.isChecked()
        self.sl_opacity.setEnabled(enabled)
        self.lb_opacity.setEnabled(enabled)

    def _update_thinning_enabled(self):
        enabled = self.chk_thinning.isChecked()
        self.sp_thin_zoom.setEnabled(enabled)
        self.sp_thin_grid.setEnabled(enabled)

    def _update_selection_enabled(self):
        enabled = self.chk_selection.isChecked()
        self.chk_force_text_codes.setEnabled(enabled)
        self.chk_pretty_geojson.setEnabled(enabled)

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
            'filterEnabled': self.chk_filter.isChecked(),
            'scaleBar': (
                {'position': self.cb_scalebar_pos.currentData()}
                if self.chk_scalebar.isChecked() else None
            ),
            # The export UI lives in the feature-table panel, so it can
            # only be reached when that panel is published at all.
            'selection': (
                {
                    'forceTextCodes': self.chk_force_text_codes.isChecked(),
                    'prettyGeoJson': self.chk_pretty_geojson.isChecked(),
                }
                if (self.chk_selection.isChecked() and self.chk_feature_table.isChecked())
                else None
            ),
            'thinning': (
                {
                    'belowZoom': self.sp_thin_zoom.value(),
                    'gridPx': self.sp_thin_grid.value(),
                }
                if self.chk_thinning.isChecked() else None
            ),
            'locate': self.chk_locate.isChecked(),
            'radiusSearch': (
                {
                    'defaultRadius': self.sp_radius.value(),
                    'radii': sorted(set(RADIUS_CHOICES + [self.sp_radius.value()])),
                }
                if self.chk_radius.isChecked() else None
            ),
            'shareLink': self.chk_share.isChecked(),
            'language': self.cb_language.currentData(),
            'languageToggle': self.chk_lang_toggle.isChecked(),
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

    # ------------------------------------------------------------
    def _state_widgets(self):
        """Every setting on this tab, by a stable key, for get_state()/
        set_state(). A new setting only needs a line here to be kept
        between sessions."""
        return {
            'size_fullscreen': self.rb_fullscreen,
            'size_fixed': self.rb_fixed,
            'width': self.sp_width,
            'height': self.sp_height,
            'responsive': self.chk_responsive,
            'view_autofit': self.rb_autofit,
            'view_canvas': self.rb_canvas,
            'view_manual': self.rb_manual,
            'lat': self.sp_lat,
            'lng': self.sp_lng,
            'init_zoom': self.sp_init_zoom,
            'min_zoom': self.sp_min_zoom,
            'max_zoom': self.sp_max_zoom,
            'basemap_enabled': self.chk_basemap,
            'basemap': self.cb_basemap,
            'filter_enabled': self.chk_filter,
            'scalebar': self.chk_scalebar,
            'scalebar_position': self.cb_scalebar_pos,
            'locate': self.chk_locate,
            'radius': self.chk_radius,
            'radius_default': self.sp_radius,
            'share': self.chk_share,
            'language': self.cb_language,
            'language_toggle': self.chk_lang_toggle,
            'opacity_override': self.chk_opacity_override,
            'opacity': self.sl_opacity,
            'popup_click': self.rb_popup_click,
            'popup_hover': self.rb_popup_hover,
            'popup_none': self.rb_popup_none,
            'attribution': self.le_attribution,
            'popup_show_empty': self.chk_popup_show_empty,
            'popup_linkify': self.chk_popup_linkify,
            'links': self.chk_links,
            'link_gmap': self.chk_link_gmap,
            'link_sv': self.chk_link_sv,
            'link_dir': self.chk_link_dir,
            'link_gsi': self.chk_link_gsi,
            'link_name': self.chk_link_name,
            'link_name_field': self.cb_name_field,
            'search': self.chk_search,
            'feature_table': self.chk_feature_table,
            'thinning': self.chk_thinning,
            'thin_zoom': self.sp_thin_zoom,
            'thin_grid': self.sp_thin_grid,
            'selection': self.chk_selection,
            'force_text_codes': self.chk_force_text_codes,
            'pretty_geojson': self.chk_pretty_geojson,
        }

    def get_state(self):
        return widgets_state(self._state_widgets())

    def set_state(self, state):
        apply_widgets_state(self._state_widgets(), state)
        # Checkbox-driven enabling follows from the toggled signals, but
        # only when a value actually changed - refresh it explicitly.
        for update in (
            self._update_fixed_enabled, self._update_manual_enabled,
            self._update_basemap_enabled, self._update_scalebar_enabled,
            self._update_radius_enabled, self._update_opacity_enabled,
            self._update_links_enabled, self._update_thinning_enabled,
            self._update_selection_enabled,
        ):
            update()
