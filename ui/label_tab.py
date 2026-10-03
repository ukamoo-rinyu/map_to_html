# -*- coding: utf-8 -*-
"""ラベル設定 tab: batch-prepare the labels of the published vector
layers for HTML export (merged in from the standalone "Map to HTML
Label Prep" plugin - see core/label_prep.py).

The target layers are the vector layers added on the データ設定 tab,
not the QGIS Layers-panel selection the standalone plugin used: inside
this dialog the データ設定 table already *is* "the layers I'm about to
publish". dialog.py calls set_layers() whenever this tab is opened, so
it follows adds/removes there.

Settings are written to a separate "Web" layer style, so the user's
working style is never lost and 作業用に戻す switches straight back.
"""
from qgis.PyQt.QtCore import Qt, QCoreApplication
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView, QColorDialog,
    QMessageBox, QGroupBox, QAbstractItemView, QMenu,
)

from ..core import label_prep

COL_LAYER = 0
COL_STYLE = 1
COL_SYMBOL = 2
COL_BUFFER = 3
COL_SOURCE = 4
COL_WARN = 5

WEB_BADGE_BACKGROUND = QColor('#c8ecd0')   # pale green: "Web用 is active"


def set_style_badge(item, layer):
    """Show which label style `layer` is on in a table cell: a
    green "Web用" badge or a plain "作業用". Shared with the データ設定
    tab's ラベル column so both tabs read the same way."""
    if label_prep.is_web_style_active(layer):
        item.setText(QCoreApplication.translate('LabelTab', 'Web用'))
        item.setBackground(WEB_BADGE_BACKGROUND)
        item.setForeground(QColor('#000000'))
        font = item.font()
        font.setBold(True)
        item.setFont(font)
        item.setToolTip(QCoreApplication.translate(
            'LabelTab', 'ラベルは「ラベル設定」タブで適用したWeb用スタイルです。'))
    else:
        item.setText(QCoreApplication.translate('LabelTab', '作業用'))
        item.setData(Qt.ItemDataRole.BackgroundRole, None)
        item.setData(Qt.ItemDataRole.ForegroundRole, None)
        font = item.font()
        font.setBold(False)
        item.setFont(font)
        item.setToolTip(QCoreApplication.translate(
            'LabelTab', 'ラベルは普段の作業用スタイルです。'))
    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)


class LabelTab(QWidget):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.preset = label_prep.load_preset()
        self._layers = []          # QgsVectorLayer, one per table row
        self._buffer_colors = []   # [(QColor or None, is_manual)], one per row
        # Unticked layer ids survive set_layers() calls, so leaving and
        # re-entering the tab doesn't re-tick what the user unticked.
        self._unchecked_ids = set()
        self._build_ui()

    # ------------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)

        info = QLabel(self.tr(
            '「データ設定」タブで追加したベクタレイヤーのラベルを、HTML出力向けにまとめて整えます。'
            '文字色は黒で固定し、バッファ（縁取り）色を各レイヤーのシンボル色から自動で作ります。'
            'バッファ色のセルをダブルクリックすると手動で指定でき、右クリックで自動の色に戻せます。\n'
            '設定は「Web」という別のレイヤースタイルに書き込むため、作業用の表示は消えません。'
            'HTMLを生成し終えたら「作業用に戻す」で元に戻せます。'
        ))
        info.setWordWrap(True)
        root.addWidget(info)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            self.tr('レイヤー'), self.tr('現在のスタイル'), self.tr('シンボル色'),
            self.tr('バッファ色'), self.tr('取得元'), self.tr('出力時の注意'),
        ])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        for col in (COL_LAYER, COL_STYLE, COL_SYMBOL, COL_BUFFER, COL_SOURCE):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_WARN, QHeaderView.ResizeMode.Stretch)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)
        root.addWidget(self.table, 1)

        group = QGroupBox(self.tr('適用する項目（チェックした項目だけ書き換えます）'))
        grid = QGridLayout(group)
        preset = self.preset
        font_family = preset.get('font_family', 'Noto Sans JP')
        font_family_latin = preset.get('font_family_latin', '')
        if font_family_latin:
            font_text = self.tr('フォント（{0} / 日本語以外は{1}）').format(font_family, font_family_latin)
        else:
            font_text = self.tr('フォント（{0}）').format(font_family)
        items = [
            ('font', font_text),
            ('size', self.tr('サイズ（{0}pt）').format(preset.get('size', 10))),
            ('color', self.tr('文字色（黒で固定）')),
            ('buffer', self.tr('バッファ（レイヤー色 {0}pt）').format(
                '%.1f' % preset.get('buffer', {}).get('size', 1.2))),
            ('placement', self.tr('配置（曲線→水平）')),
            ('scale', self.tr('縮尺連動（1:{0} 以下で表示）').format(
                '{:,}'.format(int(preset.get('scale_min', 25000))))),
        ]
        self.checks = {}
        for index, (key, text) in enumerate(items):
            box = QCheckBox(text)
            box.setChecked(True)
            self.checks[key] = box
            grid.addWidget(box, index // 3, index % 3)
        root.addWidget(group)

        buttons = QHBoxLayout()
        self.status = QLabel('')
        self.status.setWordWrap(True)
        buttons.addWidget(self.status, 1)
        btn_restore = QPushButton(self.tr('作業用に戻す'))
        btn_restore.clicked.connect(self._restore_layers)
        buttons.addWidget(btn_restore)
        btn_apply = QPushButton(self.tr('Web用に切替して適用'))
        btn_apply.clicked.connect(self._apply_to_layers)
        buttons.addWidget(btn_apply)
        root.addLayout(buttons)

    # ------------------------------------------------------------
    def set_layers(self, layers):
        """Show `layers` (the データ設定 tab's vector layers, in its
        display order). Manual buffer colours live in the project file,
        so rebuilding the rows from scratch loses nothing."""
        self._layers = list(layers)
        self._buffer_colors = []
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for layer in self._layers:
            buffer_color, is_manual, source = label_prep.buffer_color_for(layer)
            self._buffer_colors.append((buffer_color, is_manual))
            self._append_row(layer, buffer_color, is_manual, source)
        self.table.blockSignals(False)

        if self._layers:
            self.status.setText(self.tr('{0} レイヤーが対象です。').format(len(self._layers)))
        else:
            self.status.setText(self.tr('「データ設定」タブにベクタレイヤーを追加すると、ここに表示されます。'))

    def _append_row(self, layer, buffer_color, is_manual, source):
        row = self.table.rowCount()
        self.table.insertRow(row)

        name_item = QTableWidgetItem(layer.name())
        name_item.setFlags(name_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        name_item.setCheckState(
            Qt.CheckState.Unchecked if layer.id() in self._unchecked_ids else Qt.CheckState.Checked)
        self.table.setItem(row, COL_LAYER, name_item)

        self.table.setItem(row, COL_STYLE, QTableWidgetItem(''))
        self._update_style_cell(row)

        base_color, _source = label_prep.symbol_color(layer)
        symbol_item = QTableWidgetItem(base_color.name() if base_color else '—')
        if base_color:
            symbol_item.setBackground(base_color)
        self.table.setItem(row, COL_SYMBOL, symbol_item)

        self.table.setItem(row, COL_BUFFER, QTableWidgetItem(''))
        self.table.setItem(row, COL_SOURCE, QTableWidgetItem(''))
        self._set_buffer_cell(row, buffer_color, is_manual, source)

        self.table.setItem(row, COL_WARN, QTableWidgetItem(''))
        self._update_warn_cell(row)

    def _update_style_cell(self, row):
        set_style_badge(self.table.item(row, COL_STYLE), self._layers[row])

    def _update_warn_cell(self, row):
        warnings = label_prep.diagnose(self._layers[row])
        self.table.item(row, COL_WARN).setText(' / '.join(warnings) if warnings else '—')

    def _set_buffer_cell(self, row, buffer_color, is_manual, source_text):
        self._buffer_colors[row] = (buffer_color, is_manual)
        item = self.table.item(row, COL_BUFFER)
        if buffer_color is not None:
            item.setText(buffer_color.name())
            item.setBackground(buffer_color)
            # Show the cell the way the label will look: black on pale.
            item.setForeground(QColor('#000000'))
        else:
            item.setText(self.tr('白（既定）'))
            item.setData(Qt.ItemDataRole.BackgroundRole, None)
            item.setData(Qt.ItemDataRole.ForegroundRole, None)
        self.table.item(row, COL_SOURCE).setText(self.tr('手動') if is_manual else source_text)

    def _on_item_changed(self, item):
        if item.column() != COL_LAYER or item.row() >= len(self._layers):
            return
        layer_id = self._layers[item.row()].id()
        if item.checkState() == Qt.CheckState.Checked:
            self._unchecked_ids.discard(layer_id)
        else:
            self._unchecked_ids.add(layer_id)

    # ------------------------------------------------------------
    def _on_cell_double_clicked(self, row, column):
        if column != COL_BUFFER or row >= len(self._layers):
            return
        layer = self._layers[row]
        current, _is_manual = self._buffer_colors[row]
        chosen = QColorDialog.getColor(
            current or QColor('#FFFFFF'), self,
            self.tr('{0} のバッファ色').format(layer.name()))
        if not chosen.isValid():
            return
        label_prep.write_override(layer.name(), chosen)
        self._set_buffer_cell(row, chosen, True, '')
        if label_prep.is_too_dark_for_black_text(chosen):
            self.table.item(row, COL_WARN).setText(
                self.tr('バッファが濃く、黒文字が読みにくい可能性'))

    def _on_context_menu(self, pos):
        index = self.table.indexAt(pos)
        row, column = index.row(), index.column()
        if column != COL_BUFFER or row < 0 or row >= len(self._layers):
            return
        _color, is_manual = self._buffer_colors[row]
        menu = QMenu(self)
        reset_action = menu.addAction(self.tr('自動生成の色に戻す'))
        reset_action.setEnabled(is_manual)
        if menu.exec(self.table.viewport().mapToGlobal(pos)) == reset_action:
            layer = self._layers[row]
            label_prep.write_override(layer.name(), None)
            buffer_color, is_manual, source = label_prep.buffer_color_for(layer)
            self._set_buffer_cell(row, buffer_color, is_manual, source)
            self._update_warn_cell(row)

    # ------------------------------------------------------------
    def _checked_rows(self):
        return [
            row for row in range(self.table.rowCount())
            if self.table.item(row, COL_LAYER).checkState() == Qt.CheckState.Checked
        ]

    def _apply_to_layers(self):
        rows = self._checked_rows()
        if not rows:
            QMessageBox.information(self, self.tr('対象なし'), self.tr('適用するレイヤーがありません。'))
            return

        flags = {key: box.isChecked() for key, box in self.checks.items()}
        applied, skipped = 0, []
        for row in rows:
            layer = self._layers[row]
            buffer_color, _is_manual = self._buffer_colors[row]
            ok, message = label_prep.can_apply(layer)
            if ok:
                label_prep.switch_to_web_style(layer)
                ok, message = label_prep.apply_preset(layer, self.preset, buffer_color, flags)
            if ok:
                applied += 1
            else:
                skipped.append('{0}: {1}'.format(layer.name(), message))
            self._update_style_cell(row)
            self._update_warn_cell(row)

        self.iface.mapCanvas().refreshAllLayers()
        text = self.tr('{0} レイヤーに適用しました。').format(applied)
        if skipped:
            text += ' ' + self.tr('スキップ：') + ' / '.join(skipped)
        self.status.setText(text)

    def _restore_layers(self):
        restored = 0
        for row in self._checked_rows():
            if label_prep.restore_base_style(self._layers[row]):
                restored += 1
            self._update_style_cell(row)
            self._update_warn_cell(row)
        self.iface.mapCanvas().refreshAllLayers()
        self.status.setText(self.tr('{0} レイヤーを作業用スタイルに戻しました。').format(restored))
