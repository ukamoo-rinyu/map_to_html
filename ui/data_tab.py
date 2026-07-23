# -*- coding: utf-8 -*-
"""Tab 1: the layers to publish (spec 3.1, reworked at user request to
match qgis2web's model - "多重表示" first, search/filter later). Every
layer added here is displayed on the output map with its own QGIS
symbology/labels; there is no merging and no distinction between a
"search target" and "reference" layer in this round - that split is
deferred until cross-layer search is designed. Vector layers are
published as styled GeoJSON; raster layers that are XYZ tile sources
(e.g. a 国土地理院 basemap already added to the QGIS project) are
published as a Leaflet tile layer instead (see core/tile_layer.py).

`self._entries` (not the QTableWidget) is the source of truth for
layer order/settings - the table is just a rendering of it, fully
rebuilt on every add/remove/reorder. This is simpler than trying to
move QTableWidgetItems and their cellWidgets (with closures bound to
specific rows) around in place. Row order in `self._entries` directly
becomes both the map's draw/stacking order and the web output's
legend order (dialog.py/config_builder.py/layer-control.js all just
iterate get_layers() order downstream), so the 上へ/下へ移動 buttons
here (next to 削除, operating on the currently selected row) are the
only place layer order needs to be controlled.
"""
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QGroupBox, QTableWidget, QTableWidgetItem, QCheckBox, QHeaderView,
    QMessageBox, QAbstractItemView, QSpinBox,
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QFont
from qgis.core import QgsRasterLayer

from ..core import layer_utils, field_config, tile_layer
from . import field_dialog

COL_GROUP = 0
COL_NAME = 1
COL_TYPE = 2
COL_OPACITY = 3
COL_FIELDS = 4
COL_POPUP = 5
COL_VISIBLE = 6

TYPE_LABELS = {'vector': 'データ', 'raster': '背景タイル'}


class DataTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries = []  # [{'layer_id', 'label', 'default_visible', 'field_config'}, ...] in display order
        self._build_ui()
        self.refresh_pick_list()
        self._populate_visible_layers()

    # ------------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)

        grp = QGroupBox(self.tr('レイヤー（複数追加可・すべて地図に表示されます）'))
        lay = QVBoxLayout(grp)

        row_add = QHBoxLayout()
        row_add.addWidget(QLabel(self.tr('レイヤー:')))
        self.cb_pick = QComboBox()
        row_add.addWidget(self.cb_pick, 1)
        btn_refresh = QPushButton(self.tr('一覧更新'))
        btn_refresh.clicked.connect(self.refresh_pick_list)
        row_add.addWidget(btn_refresh)
        btn_add = QPushButton(self.tr('＋ 追加'))
        btn_add.clicked.connect(self._add_layer)
        row_add.addWidget(btn_add)
        lay.addLayout(row_add)

        lay.addWidget(QLabel(self.tr(
            '行を選択して「上へ移動／下へ移動」で表示順を変更できます。リストの上にあるレイヤーほど'
            '地図上で手前（上）に描画され、凡例（レイヤーパネル）でもこの順に並びます。'
        )))

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            self.tr('グループ'), self.tr('レイヤー名（地図上の表示ラベル）'),
            self.tr('種別'), self.tr('透過率'), self.tr('ポップアップ項目'),
            self.tr('ポップアップ表示'), self.tr('初期表示ON'),
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_NAME, QHeaderView.Stretch)
        for col in (COL_GROUP, COL_TYPE, COL_OPACITY, COL_FIELDS, COL_POPUP, COL_VISIBLE):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        lay.addWidget(self.table, 1)

        row_bottom = QHBoxLayout()
        btn_up = QPushButton(self.tr('↑ 上へ移動'))
        btn_up.clicked.connect(lambda: self._move_selected(-1))
        row_bottom.addWidget(btn_up)
        btn_down = QPushButton(self.tr('↓ 下へ移動'))
        btn_down.clicked.connect(lambda: self._move_selected(1))
        row_bottom.addWidget(btn_down)
        btn_remove = QPushButton(self.tr('選択した行を削除'))
        btn_remove.clicked.connect(self._remove_layer)
        row_bottom.addWidget(btn_remove)
        lay.addLayout(row_bottom)

        root.addWidget(grp, 1)

    # ------------------------------------------------------------
    def refresh_pick_list(self):
        current = self.cb_pick.currentData()
        self.cb_pick.clear()
        added_ids = set(self._added_layer_ids())

        # Bucket remaining pickable layers by their QGIS group path so
        # the picker mirrors the layer-tree hierarchy instead of a
        # flat list (spec feedback: groups were only visible in the
        # already-added table, not here where layers get chosen).
        # Root-level (ungrouped) layers get no header and come first,
        # since that's the common case and needs no visual grouping.
        ungrouped = []
        grouped = []  # [(group_path_tuple, [item, ...])]
        group_index = {}
        for item in layer_utils.list_pickable_layers():
            if item['id'] in added_ids:
                continue
            key = tuple(item['group_path'])
            if not key:
                ungrouped.append(item)
                continue
            if key not in group_index:
                group_index[key] = []
                grouped.append((key, group_index[key]))
            group_index[key].append(item)

        header_font = QFont()
        header_font.setBold(True)
        model = self.cb_pick.model()

        def add_item(item, indent=''):
            type_tag = '[{0}] '.format(TYPE_LABELS.get(item['type'], item['type']))
            self.cb_pick.addItem(indent + type_tag + item['name'], item['id'])

        for item in ungrouped:
            add_item(item)

        for group_path, items in grouped:
            self.cb_pick.addItem(' / '.join(group_path))
            header_item = model.item(self.cb_pick.count() - 1)
            header_item.setFlags(header_item.flags() & ~Qt.ItemIsEnabled)
            header_item.setFont(header_font)
            for item in items:
                add_item(item, indent='    ')

        index = self.cb_pick.findData(current)
        if index >= 0:
            self.cb_pick.setCurrentIndex(index)

    def _added_layer_ids(self):
        return [entry['layer_id'] for entry in self._entries]

    def _add_layer(self):
        layer_id = self.cb_pick.currentData()
        if not layer_id:
            return
        self._add_layer_by_id(layer_id)
        self.refresh_pick_list()

    def _populate_visible_layers(self):
        """Pre-fill the table with whatever layers are currently
        checked/visible in the QGIS layer panel, so the common case
        (publish what I'm already looking at) needs no manual 追加."""
        for layer_id in layer_utils.list_visible_layer_ids():
            self._add_layer_by_id(layer_id)
        self.refresh_pick_list()

    def _add_layer_by_id(self, layer_id):
        if not layer_id or layer_id in self._added_layer_ids():
            return
        layer = layer_utils.get_layer_by_id(layer_id)
        if layer is None:
            return

        if isinstance(layer, QgsRasterLayer):
            initial_config = None
            # v0.3.0 task 2-3: default a newly-added raster/tile layer's
            # opacity to whatever the most-recently-added raster layer
            # in this table is already set to ("継承" - inherit the
            # transparency already configured on an existing layer),
            # so publishing several translucent overlays in a row
            # doesn't mean re-picking the same value each time. Falls
            # back to this layer's own native QGIS opacity for the
            # first raster layer added in a session - either way, the
            # per-row spinbox in _append_row lets it be changed
            # individually afterward ("個別に設定できるように").
            inherited_opacity = self._last_raster_opacity()
            opacity = inherited_opacity if inherited_opacity is not None else tile_layer.read_native_opacity(layer)
        else:
            saved_config = field_config.load_field_config(layer)
            if saved_config is not None:
                initial_config = field_config.reconcile_field_config(layer, saved_config)
            else:
                initial_config = field_config.default_field_config(layer)
            opacity = None  # not applicable to vector layers

        self._entries.append({
            'layer_id': layer_id,
            'label': layer.name(),
            'default_visible': True,
            'field_config': initial_config,
            'show_popup': True,
            'opacity': opacity,
        })
        self._rebuild_table()

    def _last_raster_opacity(self):
        for entry in reversed(self._entries):
            if entry.get('opacity') is not None:
                return entry['opacity']
        return None

    # ------------------------------------------------------------
    def _rebuild_table(self):
        self.table.setRowCount(0)
        # v0.3.0 task 2-4: the table is displayed in the REVERSE of
        # self._entries. self._entries[0] is the map's bottommost layer
        # (added to the map first, in get_layers() order) and
        # self._entries[-1] is the topmost (added last, drawn over
        # everything else) - but showing that same order top-to-bottom
        # in a table made "the layer at the bottom of the list" the one
        # that ends up on TOP of the map, which read as backwards (spec
        # feedback). Reversing purely this table's display order (not
        # self._entries itself, which still drives get_layers()/the
        # actual map stacking) makes "top of the list" mean "top of the
        # map", matching how QGIS's own layers panel behaves. See
        # _move_selected for the matching index translation.
        for entry in reversed(self._entries):
            self._append_row(entry)

    def _append_row(self, entry):
        layer = layer_utils.get_layer_by_id(entry['layer_id'])
        if layer is None:
            return
        layer_type = 'raster' if isinstance(layer, QgsRasterLayer) else 'vector'
        group_path = layer_utils.get_layer_group_path(entry['layer_id'])

        row = self.table.rowCount()
        self.table.insertRow(row)

        group_item = QTableWidgetItem(' / '.join(group_path))
        group_item.setFlags(group_item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, COL_GROUP, group_item)

        name_item = QTableWidgetItem(entry['label'])
        self.table.setItem(row, COL_NAME, name_item)

        type_item = QTableWidgetItem(TYPE_LABELS.get(layer_type, layer_type))
        type_item.setFlags(type_item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, COL_TYPE, type_item)

        if layer_type == 'raster':
            spn_opacity = QSpinBox()
            spn_opacity.setRange(0, 100)
            spn_opacity.setSuffix('%')
            spn_opacity.setValue(round((entry.get('opacity') if entry.get('opacity') is not None else 1.0) * 100))
            spn_opacity.setToolTip(self.tr(
                '背景地図・ラスターレイヤーの透過率です。新しく追加したレイヤーは、直前に追加した'
                'ラスターレイヤーの透過率を引き継ぎます（未追加ならQGIS側の設定を引き継ぎます）。'
            ))
            spn_opacity.valueChanged.connect(lambda value, e=entry: e.__setitem__('opacity', value / 100.0))
            self.table.setCellWidget(row, COL_OPACITY, self._centered(spn_opacity))
        else:
            # Vector layer opacity comes from the QGIS symbol itself
            # (style_extractor.py extracts it automatically) - no
            # separate control needed here.
            self.table.setCellWidget(row, COL_OPACITY, self._centered(QLabel('—')))

        if layer_type == 'vector':
            cell = QWidget()
            cell_layout = QHBoxLayout(cell)
            cell_layout.setContentsMargins(2, 0, 2, 0)
            cell_layout.setAlignment(Qt.AlignCenter)
            btn_fields = QPushButton(self.tr('設定…'))
            btn_fields.clicked.connect(lambda checked=False, e=entry, ly=layer: self._open_field_settings(ly, e))
            cell_layout.addWidget(btn_fields)
            btn_copy = QPushButton(self.tr('→同グループにコピー'))
            btn_copy.setToolTip(self.tr(
                'このレイヤーの「ポップアップに表示する項目」設定（表示・非表示と並び順）を、\n'
                '同じグループの他のレイヤーにも適用します。'
            ))
            btn_copy.clicked.connect(lambda checked=False, e=entry: self._copy_field_config_to_group(e))
            cell_layout.addWidget(btn_copy)
            self.table.setCellWidget(row, COL_FIELDS, cell)
        else:
            # Raster/tile layers have no attributes - nothing to pick.
            self.table.setCellWidget(row, COL_FIELDS, self._centered(QLabel('—')))

        if layer_type == 'vector':
            chk_popup = QCheckBox()
            chk_popup.setChecked(entry.get('show_popup', True))
            chk_popup.setToolTip(self.tr(
                'オフにすると、このレイヤーはクリック/ホバーしても何も反応しなくなります。\n'
                '背景の区境界線などが手前のポイントのクリックを奪ってしまう場合に、\n'
                'そのレイヤーだけオフにしてください。'
            ))
            chk_popup.toggled.connect(lambda checked, e=entry: e.__setitem__('show_popup', checked))
            self.table.setCellWidget(row, COL_POPUP, self._centered(chk_popup))
        else:
            # Raster/tile layers are never interactive/clickable at all
            # (core/tile_layer.py just publishes an L.tileLayer) - no
            # popup toggle applies here.
            self.table.setCellWidget(row, COL_POPUP, self._centered(QLabel('—')))

        chk_visible = QCheckBox()
        chk_visible.setChecked(entry['default_visible'])
        chk_visible.toggled.connect(lambda checked, e=entry: e.__setitem__('default_visible', checked))
        self.table.setCellWidget(row, COL_VISIBLE, self._centered(chk_visible))

    def _sync_labels_from_table(self):
        """Row-edited labels (double-click the name cell) only live in
        the QTableWidgetItem text until this runs - call before reading
        or reordering `self._entries` so edits aren't lost."""
        for row, entry in enumerate(self._entries):
            item = self.table.item(row, COL_NAME)
            if item is not None:
                entry['label'] = item.text().strip() or entry['label']

    def _move_selected(self, delta):
        """`delta` is in *display* terms: -1 = toward the top of the
        table (v0.3.0 task 2-4: table top = map top = drawn in front),
        +1 = toward the bottom (map bottom = drawn behind). Since the
        table renders self._entries in reverse (see _rebuild_table),
        moving toward the table's top means moving to a *higher* index
        in self._entries - the opposite sign from `delta`."""
        self._sync_labels_from_table()
        row = self.table.currentRow()
        if row < 0:
            return
        n = len(self._entries)
        entry_index = n - 1 - row
        new_entry_index = entry_index - delta
        if not (0 <= new_entry_index < n):
            return
        self._entries[entry_index], self._entries[new_entry_index] = (
            self._entries[new_entry_index], self._entries[entry_index]
        )
        self._rebuild_table()
        self.table.selectRow(n - 1 - new_entry_index)

    def _open_field_settings(self, layer, entry):
        current_config = entry['field_config'] or field_config.default_field_config(layer)
        dlg = field_dialog.FieldVisibilityDialog(layer, current_config, self)
        if dlg.exec_():
            new_config = dlg.field_config()
            entry['field_config'] = new_config
            field_config.save_field_config(layer, new_config)

    def _copy_field_config_to_group(self, source_entry):
        """Apply this layer's popup field configuration (visibility
        and order), matched by field name, to every other vector layer
        in the table that shares the same QGIS group - the common case
        is several layers sharing one schema (spec feedback: user
        didn't want to repeat the same picker/reorder work per layer).
        Persists to each target layer too, same as opening 設定… would."""
        group_path = layer_utils.get_layer_group_path(source_entry['layer_id'])
        group_text = ' / '.join(group_path)
        if not group_text:
            QMessageBox.information(
                self, self.tr('コピー'),
                self.tr('このレイヤーはグループに属していないため、コピー先がありません。')
            )
            return

        source_config = source_entry['field_config'] or []
        copied = 0
        for other_entry in self._entries:
            if other_entry is source_entry:
                continue
            other_layer = layer_utils.get_layer_by_id(other_entry['layer_id'])
            if other_layer is None or isinstance(other_layer, QgsRasterLayer):
                continue
            other_group_text = ' / '.join(layer_utils.get_layer_group_path(other_entry['layer_id']))
            if other_group_text != group_text:
                continue
            projected_config = field_config.reconcile_field_config(other_layer, source_config)
            other_entry['field_config'] = projected_config
            field_config.save_field_config(other_layer, projected_config)
            copied += 1

        if copied:
            QMessageBox.information(
                self, self.tr('コピー完了'),
                self.tr('同じグループ「{0}」の他のレイヤー{1}件に設定をコピーしました。').format(group_text, copied)
            )
        else:
            QMessageBox.information(
                self, self.tr('コピー'),
                self.tr('同じグループ「{0}」に他のレイヤーが見つかりませんでした。').format(group_text)
            )

    def _remove_layer(self):
        self._sync_labels_from_table()
        rows = sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True)
        for row in rows:
            if 0 <= row < len(self._entries):
                del self._entries[row]
        self._rebuild_table()
        self.refresh_pick_list()

    @staticmethod
    def _centered(widget):
        holder = QWidget()
        layout = QHBoxLayout(holder)
        layout.addWidget(widget)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)
        return holder

    # ------------------------------------------------------------
    def get_layers(self):
        """Returns [{'id': str, 'layer': QgsMapLayer, 'label': str,
        'default_visible': bool, 'field_order': list}, ...] in display
        order (see module docstring - this order drives both map
        stacking and legend order downstream). `layer` is a
        QgsVectorLayer or QgsRasterLayer - callers branch on type.
        `show_popup` (always True for raster - the checkbox doesn't
        apply there) controls whether the published layer responds to
        clicks/hover at all; turning it off is how a background
        reference layer (e.g. a ward boundary) is kept from stealing
        clicks meant for a point layer on top of it. `field_order`
        (empty for raster layers) is the ordered list of visible field
        names picked via the ポップアップ項目 button, ready for
        geojson_writer.py. `opacity` (0.0-1.0, raster layers only,
        None for vector) is the per-layer override from the 透過率
        spinbox (v0.3.0 task 2-3), ready for tile_layer.py."""
        self._sync_labels_from_table()
        result = []
        for index, entry in enumerate(self._entries):
            layer = layer_utils.get_layer_by_id(entry['layer_id'])
            if layer is None:
                continue
            result.append({
                'id': 'layer_' + str(index),
                'layer': layer,
                'label': entry['label'] or layer.name(),
                'default_visible': entry['default_visible'],
                'show_popup': entry.get('show_popup', True),
                'opacity': entry.get('opacity'),
                'field_order': (
                    field_config.visible_field_order(entry['field_config']) if entry['field_config'] else None
                ),
            })
        return result

    def validate(self):
        errors = []
        if not self._entries:
            errors.append(self.tr('表示するレイヤーを1つ以上追加してください。'))
        return errors
