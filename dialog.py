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
from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.core import (
    QgsRasterLayer, QgsProject, QgsCoordinateTransform, QgsCoordinateReferenceSystem,
)

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
        self._resize_to_fit_screen(760, 640)
        # Explicitly modeless (plugin.py opens it with show(), not
        # exec()): the user has to be able to keep working in QGIS -
        # changing a layer's symbology, adding a layer - while this is
        # open, then pull those changes in with the データ設定 tab's
        # 再読み込み button.
        self.setModal(False)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMinMaxButtonsHint)
        self._build_ui()

    def _resize_to_fit_screen(self, width, height):
        """Open at the preferred size, but never taller/wider than the
        screen actually has room for. A dialog that opens larger than
        the desktop can't be shrunk back on Windows once its title bar
        is off-screen, which stranded the 生成/閉じる buttons out of
        reach as this dialog's settings grew."""
        try:
            available = QApplication.primaryScreen().availableGeometry()
            width = min(width, available.width() - 60)
            height = min(height, available.height() - 80)
        except Exception:
            pass
        self.resize(max(width, 480), max(height, 360))

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
        # Cheap enough to just refresh whenever the user lands on 表示設定,
        # which also covers layers added since the dialog opened.
        self.tabs.currentChanged.connect(self._on_tab_changed)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        buttons.button(QDialogButtonBox.StandardButton.Close).clicked.connect(self.close)
        root.addWidget(buttons)

    # ------------------------------------------------------------
    def _on_tab_changed(self, index):
        if self.tabs.widget(index) is self.display_tab:
            self._sync_name_field_choices()

    def _current_canvas_view(self):
        """The QGIS map canvas's current extent as a WGS84
        [[south, west], [north, east]] pair for Leaflet's fitBounds
        (spec item 5). Falls back to the usual auto-fit if the canvas
        extent can't be read or transformed - an unusable initial view
        is worse than ignoring the setting."""
        try:
            canvas = self.iface.mapCanvas()
            extent = canvas.extent()
            if extent.isEmpty():
                return {'mode': 'autoFit'}
            transform = QgsCoordinateTransform(
                canvas.mapSettings().destinationCrs(),
                QgsCoordinateReferenceSystem('EPSG:4326'),
                QgsProject.instance(),
            )
            rect = transform.transformBoundingBox(extent)
            return {
                'mode': 'bounds',
                'bounds': [
                    [rect.yMinimum(), rect.xMinimum()],
                    [rect.yMaximum(), rect.xMaximum()],
                ],
            }
        except Exception:
            return {'mode': 'autoFit'}

    def _sync_name_field_choices(self):
        """Feed the 表示設定 tab's "施設名でGoogle検索" field picker with
        the field names of whichever layers are currently added on the
        データ設定 tab, so the user picks from a list instead of typing
        a field name from memory."""
        names = []
        for entry in self.data_tab.get_layers():
            layer = entry.get('layer')
            if isinstance(layer, QgsRasterLayer) or layer is None:
                continue
            try:
                names.extend(layer.fields().names())
            except AttributeError:
                continue
        self.display_tab.set_name_fields(names)

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

        if display_settings['initialView'].get('mode') == 'currentCanvas':
            display_settings['initialView'] = self._current_canvas_view()
        # Applied while reading each layer's symbology rather than as a
        # runtime knob in the output (see core/style_extractor.py).
        fill_opacity_override = display_settings.pop('fillOpacityOverride', None)

        if output_settings['output_format'] == 'split':
            # Each run gets its own timestamped subfolder under the chosen
            # parent folder, so the user no longer has to hand-name
            # test1/test2/... folders before every export. The
            # "Map to html_" prefix identifies which subfolders came from
            # this plugin when the parent folder is shared with other things.
            stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            output_settings['output_path'] = os.path.join(
                output_settings['output_path'], f'Map to html_{stamp}'
            )

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
                            style = tile_layer.extract_tile_style(
                                entry['layer'], opacity_override=entry.get('opacity')
                            )
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

                    style = style_extractor.extract_style(
                        entry['layer'], fill_opacity_override=fill_opacity_override
                    )
                    label_evaluator = style_extractor.build_label_text_evaluator(entry['layer'])
                    geojson_path = os.path.join(tmp_dir, f'layer_{index}.geojson')
                    geojson_writer.write_sites_geojson(
                        entry['layer'], geojson_path, label_evaluator, id_field=None,
                        field_order=entry.get('field_order'),
                        # Features in a category the user unchecked in QGIS
                        # are invisible there, so they're not exported.
                        feature_filter=style_extractor.build_render_filter(entry['layer']),
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
                            'showPopup': entry.get('show_popup', True),
                            'groupPath': layer_utils.get_layer_group_path(entry['layer'].id()),
                            'fieldAliases': layer_utils.field_aliases(entry['layer']),
                            'minZoom': entry.get('min_zoom'),
                            'maxZoom': entry.get('max_zoom'),
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
            if written:
                # written's last entry is always the generated .html file
                # itself (html_builder.build_output appends it last for
                # both split and single output), so opening it in the
                # user's default browser needs no extra bookkeeping here.
                QDesktopServices.openUrl(QUrl.fromLocalFile(written[-1]))
            QMessageBox.information(self, self.tr('完了'), message)

        except Exception as exc:  # noqa: BLE001 - surface any export failure to the user
            self.output_tab.set_progress(0)
            message = self.tr('生成に失敗しました: ') + str(exc)
            self.output_tab.set_result(message, is_error=True)
            QMessageBox.critical(self, self.tr('エラー'), message)
        finally:
            self.output_tab.btn_generate.setEnabled(True)
