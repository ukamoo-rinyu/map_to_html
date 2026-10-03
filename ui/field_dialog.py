# -*- coding: utf-8 -*-
"""Small modal dialog for picking, per vector layer, which attributes
appear in the web output's click popup (and in what order) and which
are offered in the output's filter bar. In-plugin alternative to
QGIS's own per-field "Hidden" edit widget setting (Layer Properties >
Fields) - a first attempt reused that QGIS-side control, but the user
found it too hard to discover/operate and asked for a picker inside the
plugin itself instead. Ordering is done via drag-and-drop reordering of
the list plus explicit up/down buttons.

Two checkbox columns on one list (a QTreeWidget used as a flat table,
since QListWidget only has one checkbox per row): ポップアップ on the
field name itself, フィルター in the second column."""
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QDialogButtonBox, QPushButton, QLabel, QAbstractItemView, QHeaderView,
)
from qgis.PyQt.QtCore import Qt

COL_NAME = 0     # checkbox = shown in the popup
COL_FILTER = 1   # checkbox = offered in the filter bar


class FieldVisibilityDialog(QDialog):
    def __init__(self, layer, field_config, parent=None):
        """`field_config`: [{'name': str, 'visible': bool, 'filter':
        bool}, ...] for every field currently on `layer`, already
        reconciled by the caller (core/field_config.py::
        reconcile_field_config)."""
        super().__init__(parent)
        self.setWindowTitle(self.tr('ポップアップ・フィルター項目 - {0}').format(layer.name()))
        self.resize(400, 500)

        root = QVBoxLayout(self)
        hint = QLabel(self.tr(
            '「ポップアップ」にチェックした項目が、上から順に地図クリック時のポップアップに表示されます。\n'
            '「フィルター」にチェックした項目は、表示設定タブでフィルターバーをオンにしたとき、'
            '値で絞り込める項目になります（同じ項目名を持つ他のレイヤーにも自動で適用されます）。\n'
            '行はドラッグするか、下の「上へ」「下へ」で並び替えられます。'
        ))
        hint.setWordWrap(True)
        root.addWidget(hint)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels([self.tr('ポップアップ'), self.tr('フィルター')])
        self.tree.setRootIsDecorated(False)
        self.tree.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.tree.setDefaultDropAction(Qt.DropAction.MoveAction)
        header = self.tree.header()
        header.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_FILTER, QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(False)
        for entry in field_config:
            item = QTreeWidgetItem([entry['name'], ''])
            # Not a drop target itself: dropping onto a row would nest
            # the dragged field under it instead of reordering.
            item.setFlags(
                (item.flags() | Qt.ItemFlag.ItemIsUserCheckable) & ~Qt.ItemFlag.ItemIsDropEnabled)
            item.setCheckState(COL_NAME, self._state(entry.get('visible', True)))
            item.setCheckState(COL_FILTER, self._state(entry.get('filter', False)))
            self.tree.addTopLevelItem(item)
        root.addWidget(self.tree, 1)

        row_move = QHBoxLayout()
        btn_up = QPushButton(self.tr('↑ 上へ'))
        btn_up.clicked.connect(lambda: self._move(-1))
        row_move.addWidget(btn_up)
        btn_down = QPushButton(self.tr('↓ 下へ'))
        btn_down.clicked.connect(lambda: self._move(1))
        row_move.addWidget(btn_down)
        row_move.addStretch()
        root.addLayout(row_move)

        row_bulk = QHBoxLayout()
        row_bulk.addWidget(QLabel(self.tr('ポップアップ:')))
        btn_all = QPushButton(self.tr('すべて表示'))
        btn_all.clicked.connect(lambda: self._set_all(COL_NAME, True))
        row_bulk.addWidget(btn_all)
        btn_none = QPushButton(self.tr('すべて非表示'))
        btn_none.clicked.connect(lambda: self._set_all(COL_NAME, False))
        row_bulk.addWidget(btn_none)
        btn_filter_none = QPushButton(self.tr('フィルターをすべて外す'))
        btn_filter_none.clicked.connect(lambda: self._set_all(COL_FILTER, False))
        row_bulk.addWidget(btn_filter_none)
        row_bulk.addStretch()
        root.addLayout(row_bulk)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    @staticmethod
    def _state(checked):
        return Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked

    def _set_all(self, column, checked):
        for row in range(self.tree.topLevelItemCount()):
            self.tree.topLevelItem(row).setCheckState(column, self._state(checked))

    def _move(self, delta):
        item = self.tree.currentItem()
        if item is None:
            return
        row = self.tree.indexOfTopLevelItem(item)
        target = row + delta
        if 0 <= target < self.tree.topLevelItemCount():
            self.tree.takeTopLevelItem(row)
            self.tree.insertTopLevelItem(target, item)
            self.tree.setCurrentItem(item)

    def field_config(self):
        """Returns [{'name', 'visible', 'filter'}, ...] in the dialog's
        current (possibly reordered) row order."""
        result = []
        for row in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(row)
            result.append({
                'name': item.text(COL_NAME),
                'visible': item.checkState(COL_NAME) == Qt.CheckState.Checked,
                'filter': item.checkState(COL_FILTER) == Qt.CheckState.Checked,
            })
        return result
