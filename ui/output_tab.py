# -*- coding: utf-8 -*-
"""Tab 5: title, output format (split/single), output path, generate
button + progress bar (spec 3.1 Tab 5). The button only emits a click
signal here - FacilityAppGeneratorDialog owns the actual export logic
since it needs the other tabs' settings too."""
import os

from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QPushButton, QGroupBox, QRadioButton, QButtonGroup, QFileDialog,
    QProgressBar, QColorDialog, QFontComboBox,
)
from qgis.PyQt.QtGui import QColor

DEFAULT_TITLE_COLOR = '#ffffff'
DEFAULT_HEADER_BG_COLOR = '#3b4656'


class OutputTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._title_color = DEFAULT_TITLE_COLOR
        self._header_bg_color = DEFAULT_HEADER_BG_COLOR
        self._font_touched = False
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)

        form = QFormLayout()
        self.le_title = QLineEdit()
        self.le_title.setPlaceholderText(self.tr('例: ○○マップ'))
        form.addRow(self.tr('タイトル:'), self.le_title)
        root.addLayout(form)

        grp_theme = QGroupBox(self.tr('デザイン（タイトルバー）'))
        lay_theme = QFormLayout(grp_theme)

        self.btn_title_color = QPushButton()
        self.btn_title_color.clicked.connect(self._pick_title_color)
        self._update_color_button(self.btn_title_color, self._title_color)
        lay_theme.addRow(self.tr('タイトル文字色:'), self.btn_title_color)

        self.btn_header_bg_color = QPushButton()
        self.btn_header_bg_color.clicked.connect(self._pick_header_bg_color)
        self._update_color_button(self.btn_header_bg_color, self._header_bg_color)
        lay_theme.addRow(self.tr('タイトルバー背景色:'), self.btn_header_bg_color)

        self.font_combo = QFontComboBox()
        self.font_combo.setToolTip(self.tr(
            '未設定のままなら既定のゴシック体（Noto Sans JP等）を使います。\n'
            '閲覧環境に選んだフォントが入っていない場合も、そちらへ自動でフォールバックします。'
        ))
        # QFontComboBox always shows *some* font selected even before the
        # user touches it - only start honoring its value once the user
        # actually changes it, or every output would silently lose the
        # template's own Noto-Sans-JP-first default font stack.
        self.font_combo.currentFontChanged.connect(self._on_font_changed)
        lay_theme.addRow(self.tr('フォント:'), self.font_combo)

        root.addWidget(grp_theme)

        grp_format = QGroupBox(self.tr('出力形式'))
        lay_format = QVBoxLayout(grp_format)
        self.rb_split = QRadioButton(self.tr('分割ファイル（HTML＋GeoJSON/config別ファイル、推奨）'))
        self.rb_split.setChecked(True)
        self.rb_single = QRadioButton(self.tr('単一HTMLファイル'))
        self.format_group = QButtonGroup(self)
        self.format_group.addButton(self.rb_split)
        self.format_group.addButton(self.rb_single)
        lay_format.addWidget(self.rb_split)
        lay_format.addWidget(self.rb_single)
        self.rb_split.toggled.connect(self._update_path_placeholder)
        root.addWidget(grp_format)

        grp_path = QGroupBox(self.tr('出力先（分割ファイル方式では実行日時のサブフォルダが自動生成されます）'))
        lay_path = QHBoxLayout(grp_path)
        self.le_path = QLineEdit()
        lay_path.addWidget(self.le_path, 1)
        btn_browse = QPushButton(self.tr('参照…'))
        btn_browse.clicked.connect(self._browse)
        lay_path.addWidget(btn_browse)
        root.addWidget(grp_path)
        self._update_path_placeholder()

        self.btn_generate = QPushButton(self.tr('▶ HTML生成'))
        self.btn_generate.setStyleSheet(
            'background: #2e7d32; color: white; font-weight: bold; font-size: 13px; padding: 8px;'
        )
        root.addWidget(self.btn_generate)

        self.progress = QProgressBar()
        self.progress.setRange(0, 4)
        self.progress.setValue(0)
        root.addWidget(self.progress)

        self.lbl_result = QLabel('')
        self.lbl_result.setWordWrap(True)
        root.addWidget(self.lbl_result)

        root.addStretch()

    def _on_font_changed(self, _font):
        self._font_touched = True

    def _update_color_button(self, button, hex_color):
        button.setText(hex_color)
        text_color = '#000000' if QColor(hex_color).lightnessF() > 0.5 else '#ffffff'
        button.setStyleSheet('background:{0}; color:{1};'.format(hex_color, text_color))

    def _pick_title_color(self):
        color = QColorDialog.getColor(QColor(self._title_color), self, self.tr('タイトル文字色を選択'))
        if color.isValid():
            self._title_color = color.name()
            self._update_color_button(self.btn_title_color, self._title_color)

    def _pick_header_bg_color(self):
        color = QColorDialog.getColor(QColor(self._header_bg_color), self, self.tr('タイトルバー背景色を選択'))
        if color.isValid():
            self._header_bg_color = color.name()
            self._update_color_button(self.btn_header_bg_color, self._header_bg_color)

    def _update_path_placeholder(self):
        if self.rb_split.isChecked():
            self.le_path.setPlaceholderText(self.tr('出力先の親フォルダ（実行日時のサブフォルダが自動生成されます）'))
        else:
            self.le_path.setPlaceholderText(self.tr('出力先ファイル（.html）'))

    def _browse(self):
        if self.rb_split.isChecked():
            path = QFileDialog.getExistingDirectory(self, self.tr('出力先フォルダを選択'))
        else:
            path, _ = QFileDialog.getSaveFileName(
                self, self.tr('出力先ファイルを選択'), '', 'HTML (*.html)'
            )
            if path and not path.lower().endswith('.html'):
                path += '.html'
        if path:
            self.le_path.setText(path)

    def validate(self):
        errors = []
        path = self.le_path.text().strip()
        if not path:
            errors.append(self.tr('出力先を指定してください。'))
        elif self.rb_split.isChecked():
            if os.path.isfile(path):
                errors.append(self.tr('分割ファイル方式の出力先はフォルダを指定してください。'))
        else:
            if os.path.isdir(path):
                errors.append(self.tr('単一HTML方式の出力先はファイルパスを指定してください。'))
        return errors

    def get_settings(self):
        return {
            'title': self.le_title.text().strip(),
            'output_format': 'split' if self.rb_split.isChecked() else 'single',
            'output_path': self.le_path.text().strip(),
            'theme': {
                'title_color': self._title_color,
                'header_bg_color': self._header_bg_color,
                'font_family': self.font_combo.currentFont().family() if self._font_touched else None,
            },
        }

    def set_progress_range(self, maximum):
        self.progress.setRange(0, maximum)

    def set_progress(self, value, message=None):
        self.progress.setValue(value)
        if message is not None:
            self.lbl_result.setText(message)

    def set_result(self, message, is_error=False):
        self.lbl_result.setText(message)
        self.lbl_result.setStyleSheet('color:#b85000;' if is_error else 'color:#1a7a3a;')
