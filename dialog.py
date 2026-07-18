# -*- coding: utf-8 -*-
"""Main settings window (spec section 3): an independent QDialog, not a
dock panel - opened fresh each time from FacilityAppGeneratorPlugin.run().
Current scope: publish any number of QGIS layers to a Leaflet map, each
keeping its own symbology/labels (qgis2web-style "show everything
first"). Search/filter across layers is a deliberately deferred next
step - see dialog.py history for the earlier single-search-target
design this replaced.
"""
import datetime
import os
import tempfile

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QDialogButtonBox, QMessageBox,
    QApplication,
)
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsRasterLayer

from .ui.data_tab import DataTab
from .ui.display_tab import DisplayTab
from .ui.output_tab import OutputTab
from .core import style_extractor, geojson_writer, config_builder, html_builder, layer_utils, tile_layer

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'template')


class FacilityAppGeneratorDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.setWindowTitle(self.tr('Map to HTML'))
        self.resize(760, 640)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.data_tab = DataTab()
        self.display_tab = DisplayTab()
        self.output_tab = OutputTab()
        self.tabs.addTab(self.data_tab, self.tr('データ設定'))
        self.tabs.addTab(self.display_tab, self.tr('表示設定'))
        self.tabs.addTab(self.output_tab, self.tr('出力設定'))
        root.addWidget(self.tabs)

        self.output_tab.btn_generate.clicked.connect(self._on_generate)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.close)
        buttons.button(QDialogButtonBox.Close).clicked.connect(self.close)
        root.addWidget(buttons)

    # ------------------------------------------------------------
    def _on_generate(self):
        errors = (
            self.data_tab.validate()
            + self.display_tab.validate()
            + self.output_tab.validate()
        )
        if errors:
            QMessageBox.warning(self, self.tr('入力エラー'), '\n'.join(errors))
            return

        layers = self.data_tab.get_layers()
        display_settings = self.display_tab.get_settings()
        output_settings = self.output_tab.get_settings()

        if output_settings['output_format'] == 'split':
            # Each run gets its own timestamped subfolder under the chosen
            # parent folder, so the user no longer has to hand-name
            # test1/test2/... folders before every export.
            stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            output_settings['output_path'] = os.path.join(output_settings['output_path'], stamp)

        self.output_tab.btn_generate.setEnabled(False)
        self.output_tab.set_progress_range(len(layers) + 2)
        try:
            with tempfile.TemporaryDirectory(prefix='facility_app_generator_') as tmp_dir:
                layer_bundle = []
                skipped_ids = set()
                skip_messages = []
                for index, entry in enumerate(layers):
                    self.output_tab.set_progress(
                        index, self.tr('レイヤーを書き出しています… ({0}/{1}) {2}').format(
                            index + 1, len(layers), entry['label']
                        )
                    )
                    QApplication.processEvents()

                    if isinstance(entry['layer'], QgsRasterLayer):
                        try:
                            style = tile_layer.extract_tile_style(entry['layer'])
                        except ValueError as exc:
                            skipped_ids.add(entry['id'])
                            skip_messages.append(str(exc))
                            continue
                        layer_bundle.append({
                            'id': entry['id'],
                            'geojson_path': None,
                            'style': style,
                        })
                        continue

                    style = style_extractor.extract_style(entry['layer'])
                    label_evaluator = style_extractor.build_label_text_evaluator(entry['layer'])
                    geojson_path = os.path.join(tmp_dir, f'layer_{index}.geojson')
                    geojson_writer.write_sites_geojson(
                        entry['layer'], geojson_path, label_evaluator, id_field=None,
                        field_order=entry.get('field_order'),
                    )
                    layer_bundle.append({
                        'id': entry['id'],
                        'geojson_path': geojson_path,
                        'style': style,
                    })

                self.output_tab.set_progress(len(layers), self.tr('config.jsonを構築しています…'))
                QApplication.processEvents()
                config = config_builder.build_config({
                    'title': output_settings['title'],
                    'display': display_settings,
                    'theme': output_settings['theme'],
                    'layers': [
                        {
                            'id': entry['id'],
                            'label': entry['label'],
                            'defaultVisible': entry['default_visible'],
                            'groupPath': layer_utils.get_layer_group_path(entry['layer'].id()),
                        }
                        for entry in layers
                        if entry['id'] not in skipped_ids
                    ],
                })

                self.output_tab.set_progress(len(layers) + 1, self.tr('HTMLを結合・出力しています…'))
                QApplication.processEvents()
                written = html_builder.build_output(
                    TEMPLATE_DIR, config, layer_bundle,
                    output_settings['output_format'], output_settings['output_path'],
                )

            self.output_tab.set_progress(len(layers) + 2)
            message = self.tr('生成が完了しました:\n') + '\n'.join(written)
            if skip_messages:
                message += '\n\n' + self.tr('以下のレイヤーはスキップされました:\n') + '\n'.join(skip_messages)
            self.output_tab.set_result(message, is_error=False)
            QMessageBox.information(self, self.tr('完了'), message)

        except Exception as exc:  # noqa: BLE001 - surface any export failure to the user
            self.output_tab.set_progress(0)
            message = self.tr('生成に失敗しました: ') + str(exc)
            self.output_tab.set_result(message, is_error=True)
            QMessageBox.critical(self, self.tr('エラー'), message)
        finally:
            self.output_tab.btn_generate.setEnabled(True)
