# -*- coding: utf-8 -*-
"""Small modal dialog for picking which of a vector layer's attributes
appear in the web output's click popup, and in what order. In-plugin
alternative to QGIS's own per-field "Hidden" edit widget setting
(Layer Properties > Fields) - a first attempt reused that QGIS-side
control, but the user found it too hard to discover/operate and asked
for a picker inside the plugin itself instead. Ordering is done via
drag-and-drop reordering of the list plus explicit up/down buttons."""
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QDialogButtonBox, QPushButton, QLabel, QAbstractItemView,
)
from qgis.PyQt.QtCore import Qt


class FieldVisibilityDialog(QDialog):
    def __init__(self, layer, field_config, parent=None):
        """`field_config`: [{'name': str, 'visible': bool}, ...] for
        every field currently on `layer`, already reconciled by the
        caller (core/field_config.py::reconcile_field_config)."""
        super().__init__(parent)
        self.setWindowTitle(self.tr('ポップアップに表示する項目 - {0}').format(layer.name()))
        self.resize(320, 460)

        root = QVBoxLayout(self)
        root.addWidget(QLabel(self.tr(
            'チェックした項目が、上から順に地図クリック時のポップアップに表示されます。\n'
            '行はドラッグするか、下の「上へ」「下へ」で並び替えられます。'
        )))

        self.list_widget = QListWidget()
        self.list_widget.setDragDropMode(QAbstractItemView.InternalMove)
        self.list_widget.setDefaultDropAction(Qt.MoveAction)
        for entry in field_config:
            item = QListWidgetItem(entry['name'])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if entry.get('visible', True) else Qt.Unchecked)
            self.list_widget.addItem(item)
        root.addWidget(self.list_widget, 1)

        row_move = QHBoxLayout()
        btn_up = QPushButton(self.tr('↑ 上へ'))
        btn_up.clicked.connect(self._move_up)
        row_move.addWidget(btn_up)
        btn_down = QPushButton(self.tr('↓ 下へ'))
        btn_down.clicked.connect(self._move_down)
        row_move.addWidget(btn_down)
        row_move.addStretch()
        root.addLayout(row_move)

        row_bulk = QHBoxLayout()
        btn_all = QPushButton(self.tr('すべて表示'))
        btn_all.clicked.connect(lambda: self._set_all(Qt.Checked))
        row_bulk.addWidget(btn_all)
        btn_none = QPushButton(self.tr('すべて非表示'))
        btn_none.clicked.connect(lambda: self._set_all(Qt.Unchecked))
        row_bulk.addWidget(btn_none)
        row_bulk.addStretch()
        root.addLayout(row_bulk)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _set_all(self, state):
        for row in range(self.list_widget.count()):
            self.list_widget.item(row).setCheckState(state)

    def _move_up(self):
        row = self.list_widget.currentRow()
        if row > 0:
            item = self.list_widget.takeItem(row)
            self.list_widget.insertItem(row - 1, item)
            self.list_widget.setCurrentRow(row - 1)

    def _move_down(self):
        row = self.list_widget.currentRow()
        if 0 <= row < self.list_widget.count() - 1:
            item = self.list_widget.takeItem(row)
            self.list_widget.insertItem(row + 1, item)
            self.list_widget.setCurrentRow(row + 1)

    def field_config(self):
        """Returns [{'name': str, 'visible': bool}, ...] in the
        dialog's current (possibly reordered) row order."""
        result = []
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            result.append({'name': item.text(), 'visible': item.checkState() == Qt.Checked})
        return result
