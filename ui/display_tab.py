# -*- coding: utf-8 -*-
"""Tab 2: how the published page looks and behaves (spec 3.1, Tab 2).

Laid out like QGIS's own Options dialog (user request: the single long
column had grown to about three screens): a category list on the left,
that category's settings on the right, and an explanation box below
them. Settings carry short labels; the longer explanation of whichever
setting the mouse is over (or has keyboard focus) appears in the box,
and the category's own summary when it's over nothing in particular.

get_settings() is what an export uses; get_state()/set_state() are the
raw widget values the dialog keeps in the QGIS project between
sessions (core/settings_store.py)."""
from qgis.PyQt.QtCore import Qt, QEvent
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QGroupBox,
    QCheckBox, QRadioButton, QButtonGroup, QSpinBox, QDoubleSpinBox,
    QComboBox, QLineEdit, QSlider, QScrollArea, QFrame, QListWidget,
    QStackedWidget,
)

from .state_utils import widgets_state, apply_widgets_state

# Radii offered in the published page's radius search; the default
# chosen on this tab is added when it isn't one of them.
RADIUS_CHOICES = [250, 500, 1000, 2000]

INDENT = 'margin-left: 18px;'


class DisplayTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._help_texts = {}   # widget -> (title, text)
        self._page_help = []    # per category: (title, text)
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

    # ------------------------------------------------------------
    # Layout helpers
    def _help(self, title, text, *widgets):
        """Show `text` in the explanation box while the mouse is over
        (or keyboard focus is in) any of `widgets`."""
        for widget in widgets:
            self._help_texts[widget] = (title, text)
            widget.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj in self._help_texts:
            kind = event.type()
            if kind in (QEvent.Type.Enter, QEvent.Type.FocusIn):
                self._show_help(*self._help_texts[obj])
            elif kind == QEvent.Type.Leave:
                self._show_page_help()
        return super().eventFilter(obj, event)

    def _show_help(self, title, text):
        self.lbl_help.setText('<b>{0}</b><br>{1}'.format(
            title.replace('&', '&amp;').replace('<', '&lt;'),
            text.replace('&', '&amp;').replace('<', '&lt;').replace('\n', '<br>')))

    def _show_page_help(self):
        index = self.nav.currentRow()
        if 0 <= index < len(self._page_help):
            self._show_help(*self._page_help[index])

    def _add_page(self, name, summary):
        """A new category: its entry in the list, and the layout its
        settings go into. The page scrolls on its own if a small screen
        can't fit it (the dialog must never grow past the screen - the
        生成/閉じる buttons were once stranded off-screen that way)."""
        self.nav.addItem(name)
        self._page_help.append((name, summary))
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 6, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        self.pages.addWidget(scroll)
        return layout

    @staticmethod
    def _row(*items):
        row = QHBoxLayout()
        for item in items:
            if isinstance(item, str):
                row.addWidget(QLabel(item))
            else:
                row.addWidget(item)
        row.addStretch()
        return row

    # ------------------------------------------------------------
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        body = QHBoxLayout()
        outer.addLayout(body, 1)

        self.nav = QListWidget()
        self.nav.setFixedWidth(170)
        self.nav.setStyleSheet(
            'QListWidget::item { padding: 8px 6px; }'
            'QListWidget::item:selected { background: #3b6fb0; color: white; }')
        body.addWidget(self.nav)

        right = QVBoxLayout()
        self.lbl_page_title = QLabel()
        self.lbl_page_title.setStyleSheet('font-size: 15px; font-weight: bold; padding: 2px 0 4px 0;')
        right.addWidget(self.lbl_page_title)
        self.pages = QStackedWidget()
        right.addWidget(self.pages, 1)

        help_box = QGroupBox(self.tr('説明'))
        help_box.setStyleSheet(
            'QGroupBox { background: #f4f6fa; border: 1px solid #c9d3e3; border-radius: 4px;'
            ' margin-top: 10px; padding-top: 6px; }'
            'QGroupBox::title { subcontrol-origin: margin; left: 8px; }')
        help_layout = QVBoxLayout(help_box)
        self.lbl_help = QLabel()
        self.lbl_help.setWordWrap(True)
        self.lbl_help.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_help.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        # Room for about four lines, so the box doesn't jump in height
        # as the mouse moves between settings.
        self.lbl_help.setMinimumHeight(self.fontMetrics().lineSpacing() * 4 + 8)
        help_layout.addWidget(self.lbl_help)
        right.addWidget(help_box)
        body.addLayout(right, 1)

        self._build_basic_page()
        self._build_search_page()
        self._build_buttons_page()
        self._build_popup_page()
        self._build_look_page()
        self._build_language_page()
        self._build_export_page()

        self.nav.currentRowChanged.connect(self._on_page_changed)
        self.nav.setCurrentRow(0)

    def _on_page_changed(self, index):
        self.pages.setCurrentIndex(index)
        if 0 <= index < len(self._page_help):
            self.lbl_page_title.setText(self._page_help[index][0])
        self._show_page_help()

    # ---- 地図の基本 ------------------------------------------------
    def _build_basic_page(self):
        root = self._add_page(self.tr('地図の基本'), self.tr(
            '地図の大きさ、開いたときに表示する範囲、拡大・縮小できる範囲、背景地図を設定します。\n'
            '項目にマウスを乗せると、ここに説明が出ます。'))

        grp_size = QGroupBox(self.tr('画面サイズ'))
        lay_size = QVBoxLayout(grp_size)
        self.rb_fullscreen = QRadioButton(self.tr('画面いっぱい'))
        self.rb_fullscreen.setChecked(True)
        self.rb_fixed = QRadioButton(self.tr('固定サイズ'))
        self.size_group = QButtonGroup(self)
        self.size_group.addButton(self.rb_fullscreen)
        self.size_group.addButton(self.rb_fixed)
        self.sp_width = QSpinBox()
        self.sp_width.setRange(200, 8000)
        self.sp_width.setValue(960)
        self.sp_height = QSpinBox()
        self.sp_height.setRange(200, 8000)
        self.sp_height.setValue(640)
        lay_size.addLayout(self._row(
            self.rb_fullscreen, self.rb_fixed, self.tr('幅(px):'), self.sp_width,
            self.tr('高さ(px):'), self.sp_height))
        self.chk_responsive = QCheckBox(self.tr('スマートフォン対応'))
        self.chk_responsive.setChecked(True)
        lay_size.addWidget(self.chk_responsive)
        self.rb_fixed.toggled.connect(self._update_fixed_enabled)
        self._update_fixed_enabled()
        root.addWidget(grp_size)
        self._help(self.tr('画面いっぱい'), self.tr(
            '地図をブラウザのウィンドウいっぱいに表示します。通常はこちらを選びます。'), self.rb_fullscreen)
        self._help(self.tr('固定サイズ'), self.tr(
            '地図を指定した幅・高さの枠の中に表示します。ほかのページに埋め込むときなどに使います。'),
            self.rb_fixed, self.sp_width, self.sp_height)
        self._help(self.tr('スマートフォン対応'), self.tr(
            'スマートフォンなど幅の狭い画面では、検索欄やパネルの配置を自動で切り替えます。'),
            self.chk_responsive)

        grp_view = QGroupBox(self.tr('初期表示'))
        lay_view = QVBoxLayout(grp_view)
        self.rb_autofit = QRadioButton(self.tr('データの範囲に合わせる'))
        self.rb_autofit.setChecked(True)
        self.rb_canvas = QRadioButton(self.tr('今のQGIS画面の範囲'))
        self.rb_manual = QRadioButton(self.tr('中心とズームを指定'))
        self.view_group = QButtonGroup(self)
        for button in (self.rb_autofit, self.rb_canvas, self.rb_manual):
            self.view_group.addButton(button)
        lay_view.addWidget(self.rb_autofit)
        lay_view.addWidget(self.rb_canvas)
        self.sp_lat = QDoubleSpinBox()
        self.sp_lat.setRange(-90, 90)
        self.sp_lat.setDecimals(6)
        self.sp_lat.setValue(34.6937)
        self.sp_lng = QDoubleSpinBox()
        self.sp_lng.setRange(-180, 180)
        self.sp_lng.setDecimals(6)
        self.sp_lng.setValue(135.5023)
        self.sp_init_zoom = QSpinBox()
        self.sp_init_zoom.setRange(0, 24)
        self.sp_init_zoom.setValue(13)
        lay_view.addLayout(self._row(
            self.rb_manual, self.tr('緯度:'), self.sp_lat, self.tr('経度:'), self.sp_lng,
            self.tr('ズーム:'), self.sp_init_zoom))
        self.rb_manual.toggled.connect(self._update_manual_enabled)
        self._update_manual_enabled()

        self.sp_min_zoom = QSpinBox()
        self.sp_min_zoom.setRange(0, 24)
        self.sp_min_zoom.setValue(5)
        self.sp_max_zoom = QSpinBox()
        self.sp_max_zoom.setRange(0, 24)
        self.sp_max_zoom.setValue(19)
        lbl_zoom = QLabel(self.tr('ズームの範囲:'))
        lay_view.addLayout(self._row(lbl_zoom, self.sp_min_zoom, '〜', self.sp_max_zoom))
        root.addWidget(grp_view)
        self._help(self.tr('データの範囲に合わせる'), self.tr(
            '出力するすべてのレイヤーが収まるように、地図の表示範囲を自動で決めます。'), self.rb_autofit)
        self._help(self.tr('今のQGIS画面の範囲'), self.tr(
            'HTMLを生成した時点のQGISの表示範囲で地図を開きます。'
            'HTMLの地図とQGISの画面は縦横比が違うため完全には一致しませんが、'
            '指定した範囲が必ず収まるように表示されます。'), self.rb_canvas)
        self._help(self.tr('中心とズームを指定'), self.tr(
            '地図の中心の緯度・経度と、ズームレベル（数字が大きいほど拡大）を直接指定します。'),
            self.rb_manual, self.sp_lat, self.sp_lng, self.sp_init_zoom)
        self._help(self.tr('ズームの範囲'), self.tr(
            '閲覧者が縮小・拡大できる範囲です。左が最小（5でおよそ日本全体）、'
            '右が最大（19でおよそ建物1軒）です。'), lbl_zoom, self.sp_min_zoom, self.sp_max_zoom)

        grp_basemap = QGroupBox(self.tr('背景地図'))
        lay_basemap = QHBoxLayout(grp_basemap)
        # v0.3.0 task 2-2: whether to publish a basemap at all is
        # decided here, before generating the site - NOT as an on/off
        # toggle inside the generated HTML's own layer panel.
        self.chk_basemap = QCheckBox(self.tr('背景地図を表示'))
        # Off by default (user preference): most projects already add
        # their own background tile layer on the データ設定 tab.
        self.chk_basemap.setChecked(False)
        self.chk_basemap.toggled.connect(self._update_basemap_enabled)
        lay_basemap.addWidget(self.chk_basemap)
        self.cb_basemap = QComboBox()
        for key, label in self._basemap_options():
            self.cb_basemap.addItem(label, key)
        lay_basemap.addWidget(self.cb_basemap, 1)
        self._update_basemap_enabled()
        root.addWidget(grp_basemap)
        self._help(self.tr('背景地図'), self.tr(
            '地図の下に敷く背景地図です。データ設定タブで背景タイルのレイヤーを追加している場合は、'
            'オフのままで構いません。OpenStreetMap はファイルとして開いた地図では表示されないことがあり、'
            'CARTO は本格的に使うには API キーが必要です。'), self.chk_basemap, self.cb_basemap)
        root.addStretch()

    # ---- 検索・絞り込み --------------------------------------------
    def _build_search_page(self):
        root = self._add_page(self.tr('検索・絞り込み'), self.tr(
            '閲覧者が地物を探すための機能（検索バー・一覧表・フィルターバー）を設定します。'))

        grp = QGroupBox(self.tr('検索・一覧表'))
        lay = QVBoxLayout(grp)
        # v0.3.0 tasks 3-1/3-2: both reuse each layer's popup fields
        # (Tab 1), so there's nothing to pick here beyond on/off.
        self.chk_search = QCheckBox(self.tr('検索バー'))
        self.chk_search.setChecked(True)
        lay.addWidget(self.chk_search)
        self.chk_feature_table = QCheckBox(self.tr('地物の一覧表'))
        self.chk_feature_table.setChecked(True)
        lay.addWidget(self.chk_feature_table)
        root.addWidget(grp)
        self._help(self.tr('検索バー'), self.tr(
            '画面上部に検索欄を出します。施設名などを入力すると、表示中のレイヤーから候補が出て、'
            'クリックするとその場所へ移動します。検索の対象は、ポップアップに表示する項目です。'),
            self.chk_search)
        self._help(self.tr('地物の一覧表'), self.tr(
            '地図の左下に、レイヤーごとの地物の一覧表を出します。見出しのクリックで並べ替え、'
            '行のクリックでその地物へ移動します。'), self.chk_feature_table)

        grp_filter = QGroupBox(self.tr('フィルターバー'))
        lay_filter = QVBoxLayout(grp_filter)
        self.chk_filter = QCheckBox(self.tr('フィルターバー'))
        self.chk_filter.setChecked(False)
        lay_filter.addWidget(self.chk_filter)
        # Where the fields are chosen stays on screen, not only in the
        # explanation box (spec feedback: the setting couldn't be found).
        filter_hint = QLabel(self.tr(
            '絞り込む項目は、データ設定タブ →「ポップアップ・フィルター項目」の「設定…」で選びます。'))
        filter_hint.setWordWrap(True)
        filter_hint.setStyleSheet('color: #555;' + INDENT)
        lay_filter.addWidget(filter_hint)
        root.addWidget(grp_filter)
        self._help(self.tr('フィルターバー'), self.tr(
            'ヘッダーの下に、項目ごとのチェックリスト（区・種別など）を並べ、選んだ値の地物だけを表示します。'
            '地図・ラベル・一覧表・検索・データ出力すべてが連動します。'
            'どれか1つのレイヤーで項目を選べば、同じ項目名を持つ他のレイヤーもまとめて絞り込まれます。'),
            self.chk_filter, filter_hint)
        root.addStretch()

    # ---- 地図上のボタン --------------------------------------------
    def _build_buttons_page(self):
        root = self._add_page(self.tr('地図上のボタン'), self.tr(
            '地図の上に置くボタンや目盛りを設定します。初期値はスケールバーだけがオンです。'))

        grp_scale = QGroupBox(self.tr('スケールバー'))
        lay_scale = QHBoxLayout(grp_scale)
        self.chk_scalebar = QCheckBox(self.tr('スケールバー'))
        self.chk_scalebar.setChecked(True)
        self.chk_scalebar.toggled.connect(self._update_scalebar_enabled)
        lay_scale.addWidget(self.chk_scalebar)
        lbl_pos = QLabel(self.tr('位置:'))
        lay_scale.addWidget(lbl_pos)
        self.cb_scalebar_pos = QComboBox()
        for key, label in (('bottomleft', self.tr('左下')), ('bottomright', self.tr('右下'))):
            self.cb_scalebar_pos.addItem(label, key)
        lay_scale.addWidget(self.cb_scalebar_pos)
        lay_scale.addStretch()
        self._update_scalebar_enabled()
        root.addWidget(grp_scale)
        self._help(self.tr('スケールバー'), self.tr(
            '地図の隅に縮尺の目盛り（例: 500 m）を表示します。'),
            self.chk_scalebar, lbl_pos, self.cb_scalebar_pos)

        grp = QGroupBox(self.tr('便利ボタン'))
        lay = QVBoxLayout(grp)
        # Off until switched on (user preference: only the scale bar is
        # on by default).
        self.chk_locate = QCheckBox(self.tr('現在地ボタン'))
        self.chk_locate.setChecked(False)
        lay.addWidget(self.chk_locate)
        self.chk_radius = QCheckBox(self.tr('半径検索'))
        self.chk_radius.setChecked(False)
        self.chk_radius.toggled.connect(self._update_radius_enabled)
        self.sp_radius = QSpinBox()
        self.sp_radius.setRange(50, 50000)
        self.sp_radius.setSingleStep(50)
        self.sp_radius.setSuffix(' m')
        self.sp_radius.setValue(500)
        lbl_radius = QLabel(self.tr('最初の半径:'))
        lay.addLayout(self._row(self.chk_radius, lbl_radius, self.sp_radius))
        self.chk_share = QCheckBox(self.tr('リンク共有ボタン'))
        self.chk_share.setChecked(False)
        lay.addWidget(self.chk_share)
        self._update_radius_enabled()
        root.addWidget(grp)
        self._help(self.tr('現在地ボタン'), self.tr(
            '押すと閲覧者の今いる場所を、青い点と誤差の円で地図に表示します。'
            'ブラウザが位置情報の利用を確認します。位置情報は閲覧者の端末の中だけで使われ、どこにも送信されません。'
            'https:// で公開したページか、端末上のファイルとして開いたときに使えます。'), self.chk_locate)
        self._help(self.tr('半径検索'), self.tr(
            '中心（地図のクリック・現在地・地図の中心）と半径を決めると、範囲内の地物を近い順に一覧表示します。'
            '閲覧者は 250m／500m／1km／2km からも半径を選べます。'
            '地図に表示中のレイヤー（ポップアップ表示がオンのもの）が対象で、フィルターバーにも従います。'
            '線・面は頂点の平均の位置で測ります。'), self.chk_radius, lbl_radius, self.sp_radius)
        self._help(self.tr('リンク共有ボタン'), self.tr(
            '今の表示位置・レイヤー・絞り込みをURLにしてコピーします。コピーしたURLを開くと同じ表示になります。'
            'ファイルとして開いた地図のURLは、同じファイルを開ける人（共有フォルダなど）だけが使えます。'),
            self.chk_share)
        root.addStretch()

    # ---- ポップアップ ----------------------------------------------
    def _build_popup_page(self):
        root = self._add_page(self.tr('ポップアップ'), self.tr(
            '地物をクリックしたときに出る吹き出し（ポップアップ）の出し方と中身を設定します。'
            '表示する項目と並び順は、データ設定タブの「設定…」で選びます。'))

        grp_trigger = QGroupBox(self.tr('出し方'))
        lay_trigger = QVBoxLayout(grp_trigger)
        self.rb_popup_click = QRadioButton(self.tr('クリックで表示'))
        self.rb_popup_click.setChecked(True)
        self.rb_popup_hover = QRadioButton(self.tr('マウスを乗せたときも表示'))
        self.rb_popup_none = QRadioButton(self.tr('マウスを乗せても何もしない'))
        self.popup_group = QButtonGroup(self)
        for button in (self.rb_popup_click, self.rb_popup_hover, self.rb_popup_none):
            self.popup_group.addButton(button)
            lay_trigger.addWidget(button)
        # 出し方 and 中身 side by side, so the page fits without scrolling.
        row_top = QHBoxLayout()
        row_top.addWidget(grp_trigger, 1)
        root.addLayout(row_top)
        self._help(self.tr('クリックで表示'), self.tr(
            'クリックするとポップアップが開きます。マウスを乗せたときは、地物が強調表示されるだけです。'),
            self.rb_popup_click)
        self._help(self.tr('マウスを乗せたときも表示'), self.tr(
            'マウスを乗せただけでポップアップが開き、離すと閉じます。クリックでも開けます。'),
            self.rb_popup_hover)
        self._help(self.tr('マウスを乗せても何もしない'), self.tr(
            'マウスを乗せても強調表示しません。ポップアップはクリックで開きます。'), self.rb_popup_none)

        grp_content = QGroupBox(self.tr('中身'))
        lay_content = QVBoxLayout(grp_content)
        self.chk_popup_show_empty = QCheckBox(self.tr('空欄の項目も表示'))
        lay_content.addWidget(self.chk_popup_show_empty)
        self.chk_popup_linkify = QCheckBox(self.tr('URLをリンクにする'))
        self.chk_popup_linkify.setChecked(True)
        lay_content.addWidget(self.chk_popup_linkify)
        lay_content.addStretch()
        row_top.addWidget(grp_content, 1)
        self._help(self.tr('空欄の項目も表示'), self.tr(
            'オフにすると、値が空の項目はポップアップに出しません。項目名はQGISの別名（エイリアス）があればそちらを使います。'),
            self.chk_popup_show_empty)
        self._help(self.tr('URLをリンクにする'), self.tr(
            'http で始まる値をクリックできるリンクにします。画像のURLは画像として表示します。'),
            self.chk_popup_linkify)

        grp_links = QGroupBox(self.tr('地図リンク'))
        lay_links = QGridLayout(grp_links)
        self.chk_links = QCheckBox(self.tr('地図リンクを表示'))
        self.chk_links.setChecked(True)
        self.chk_links.toggled.connect(self._update_links_enabled)
        lay_links.addWidget(self.chk_links, 0, 0, 1, 2)
        # Defaults follow the spec's reasoning: the popup is narrow, so
        # only the two most-used links are on out of the box.
        self.chk_link_gmap = QCheckBox(self.tr('Googleマップ'))
        self.chk_link_gmap.setChecked(True)
        self.chk_link_sv = QCheckBox(self.tr('ストリートビュー'))
        self.chk_link_sv.setChecked(True)
        self.chk_link_dir = QCheckBox(self.tr('ここへの経路'))
        self.chk_link_gsi = QCheckBox(self.tr('地理院地図'))
        for index, widget in enumerate((self.chk_link_gmap, self.chk_link_sv,
                                        self.chk_link_dir, self.chk_link_gsi)):
            widget.setStyleSheet(INDENT)
            lay_links.addWidget(widget, 1 + index // 2, index % 2)
        self.chk_link_name = QCheckBox(self.tr('施設名でGoogle検索'))
        self.chk_link_name.setStyleSheet(INDENT)
        self.chk_link_name.toggled.connect(self._update_links_enabled)
        # Populated by set_name_fields() from the layers actually added
        # on the データ設定 tab - editable so a field the picker hasn't
        # seen yet can still be typed.
        self.cb_name_field = QComboBox()
        self.cb_name_field.setEditable(True)
        self.cb_name_field.setMinimumWidth(160)
        lbl_name_field = QLabel(self.tr('名称の項目:'))
        lay_links.addLayout(self._row(self.chk_link_name, lbl_name_field, self.cb_name_field), 3, 0, 1, 2)
        self._update_links_enabled()
        root.addWidget(grp_links)
        self._help(self.tr('地図リンク'), self.tr(
            'ポップアップの下に、その地点を外部の地図で開くリンクを並べます。'
            'ポップアップは幅が狭いので、使うものだけ選んでください。'), self.chk_links)
        self._help(self.tr('Googleマップ'), self.tr('その地点をGoogleマップで開きます。'), self.chk_link_gmap)
        self._help(self.tr('ストリートビュー'), self.tr(
            'その地点のストリートビューを開きます。'), self.chk_link_sv)
        self._help(self.tr('ここへの経路'), self.tr(
            'Googleマップで、閲覧者の現在地からその地点までの経路を調べます。'), self.chk_link_dir)
        self._help(self.tr('地理院地図'), self.tr(
            'その地点を国土地理院の地理院地図で開きます。空中写真や災害情報の確認に便利です。'), self.chk_link_gsi)
        self._help(self.tr('施設名でGoogle検索'), self.tr(
            '「名称の項目」で選んだ項目の値（施設名など）でGoogle検索します。'),
            self.chk_link_name, lbl_name_field, self.cb_name_field)

        grp_attr = QGroupBox(self.tr('帰属表示'))
        lay_attr = QHBoxLayout(grp_attr)
        self.le_attribution = QLineEdit()
        self.le_attribution.setPlaceholderText(self.tr('例: ○○市 提供データ'))
        lay_attr.addWidget(self.le_attribution)
        root.addWidget(grp_attr)
        self._help(self.tr('帰属表示'), self.tr(
            '地図の右下の出典表示に、この文を書き足します。背景地図の出典表示は消えません。'),
            self.le_attribution)
        root.addStretch()

    # ---- 見た目 ----------------------------------------------------
    def _build_look_page(self):
        root = self._add_page(self.tr('見た目'), self.tr(
            '塗りの濃さを一律にそろえる設定と、縮小したときに密集した点を間引く設定です。'))

        grp_opacity = QGroupBox(self.tr('塗りの不透明度'))
        lay_opacity = QVBoxLayout(grp_opacity)
        self.chk_opacity_override = QCheckBox(self.tr('不透明度を一律にする'))
        self.chk_opacity_override.toggled.connect(self._update_opacity_enabled)
        lay_opacity.addWidget(self.chk_opacity_override)
        self.sl_opacity = QSlider(Qt.Orientation.Horizontal)
        self.sl_opacity.setRange(0, 100)
        self.sl_opacity.setValue(40)
        self.lb_opacity = QLabel('40%')
        self.lb_opacity.setMinimumWidth(40)
        self.sl_opacity.valueChanged.connect(
            lambda value: self.lb_opacity.setText('{0}%'.format(value)))
        row_opacity = QHBoxLayout()
        row_opacity.addWidget(self.sl_opacity, 1)
        row_opacity.addWidget(self.lb_opacity)
        lay_opacity.addLayout(row_opacity)
        self._update_opacity_enabled()
        root.addWidget(grp_opacity)
        self._help(self.tr('不透明度を一律にする'), self.tr(
            'QGISの設定に関係なく、ポリゴンの塗りとマーカーの塗りを同じ濃さにします。'
            '枠線の色・不透明度は変えません。'), self.chk_opacity_override, self.sl_opacity)

        grp_thin = QGroupBox(self.tr('広域表示時の間引き'))
        lay_thin = QVBoxLayout(grp_thin)
        self.chk_thinning = QCheckBox(self.tr('縮小時に点を間引く'))
        self.chk_thinning.toggled.connect(self._update_thinning_enabled)
        lay_thin.addWidget(self.chk_thinning)
        self.sp_thin_zoom = QSpinBox()
        self.sp_thin_zoom.setRange(0, 24)
        self.sp_thin_zoom.setValue(14)
        self.sp_thin_grid = QSpinBox()
        self.sp_thin_grid.setRange(8, 200)
        self.sp_thin_grid.setValue(32)
        lbl_thin_zoom = QLabel(self.tr('このズーム未満:'))
        lbl_thin_grid = QLabel(self.tr('格子の大きさ(px):'))
        lbl_thin_zoom.setStyleSheet(INDENT)
        lay_thin.addLayout(self._row(lbl_thin_zoom, self.sp_thin_zoom, lbl_thin_grid, self.sp_thin_grid))
        self._update_thinning_enabled()
        root.addWidget(grp_thin)
        self._help(self.tr('縮小時に点を間引く'), self.tr(
            '指定したズームより縮小しているときは、画面を格子に区切って1マスにつき1件だけ描き、'
            '密集した点が団子にならないようにします。間引くのは描画だけで、検索・一覧表・CSV出力には全件が含まれます。'
            '間引いている間は「一部の地物のみ表示中」と画面に出ます。格子を大きくするほど多く間引きます。'),
            self.chk_thinning, lbl_thin_zoom, self.sp_thin_zoom, lbl_thin_grid, self.sp_thin_grid)
        root.addStretch()

    # ---- 言語 ------------------------------------------------------
    def _build_language_page(self):
        root = self._add_page(self.tr('言語'), self.tr(
            '出力したHTMLの、ボタンや案内の言語を設定します。'
            'レイヤー名・項目名・値は、QGISのデータのまま表示されます。'))

        grp = QGroupBox(self.tr('出力HTMLの表示言語'))
        lay = QVBoxLayout(grp)
        self.cb_language = QComboBox()
        for key, label in (
            ('auto', self.tr('閲覧者のブラウザに合わせる（日本語以外は英語）')),
            ('ja', self.tr('日本語')),
            ('en', self.tr('英語（English）')),
        ):
            self.cb_language.addItem(label, key)
        lbl_language = QLabel(self.tr('最初の言語:'))
        lay.addLayout(self._row(lbl_language, self.cb_language))
        self.chk_lang_toggle = QCheckBox(self.tr('日本語／英語の切り替えボタン'))
        self.chk_lang_toggle.setChecked(True)
        lay.addWidget(self.chk_lang_toggle)
        root.addWidget(grp)
        self._help(self.tr('最初の言語'), self.tr(
            '地図を開いたときの言語です。「ブラウザに合わせる」なら、日本語のブラウザでは日本語、'
            'それ以外では英語で表示します。'), lbl_language, self.cb_language)
        self._help(self.tr('日本語／英語の切り替えボタン'), self.tr(
            '地図の右上に「EN／日本語」ボタンを出します。閲覧者が選んだ言語は、そのブラウザで次回も使われます。'),
            self.chk_lang_toggle)
        root.addStretch()

    # ---- データ出力 ------------------------------------------------
    def _build_export_page(self):
        root = self._add_page(self.tr('データ出力'), self.tr(
            '閲覧者が地図上で地物を選び、CSV・GeoJSONファイルとして保存できるようにする設定です。'))

        grp = QGroupBox(self.tr('地物の選択・データ出力'))
        lay = QVBoxLayout(grp)
        self.chk_selection = QCheckBox(self.tr('地物の選択とCSV・GeoJSON出力'))
        self.chk_selection.toggled.connect(self._update_selection_enabled)
        lay.addWidget(self.chk_selection)
        self.chk_force_text_codes = QCheckBox(self.tr('先頭が0の番号を ="0123" 形式で出力'))
        self.chk_pretty_geojson = QCheckBox(self.tr('GeoJSONを整形して出力'))
        for widget in (self.chk_force_text_codes, self.chk_pretty_geojson):
            widget.setStyleSheet(INDENT)
            lay.addWidget(widget)
        self._update_selection_enabled()
        root.addWidget(grp)
        self._help(self.tr('地物の選択とCSV・GeoJSON出力'), self.tr(
            'クリック・Ctrl+クリック・範囲（四角形）で地物を選び、選んだ分またはレイヤー全体を'
            'CSV・GeoJSONで保存できるようにします。ボタンは一覧表の下に出るので、'
            '「検索・絞り込み」の地物の一覧表もオンにしてください。'
            'CSVはExcelで文字化けしない形式（BOM付きUTF-8）で、緯度・経度の列が付きます（線・面は重心）。'),
            self.chk_selection)
        self._help(self.tr('先頭が0の番号を ="0123" 形式で出力'), self.tr(
            '施設コードなど先頭が0の値は、普通のCSVだとExcelで開いたときに0が消えます（0123 → 123）。'
            'この形式なら消えませんが、Excel以外のツールに取り込むときは ="..." が邪魔になることがあります。'),
            self.chk_force_text_codes)
        self._help(self.tr('GeoJSONを整形して出力'), self.tr(
            '改行と字下げを入れて読みやすくします。そのぶんファイルは大きくなります。'),
            self.chk_pretty_geojson)
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
