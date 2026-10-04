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
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QDialogButtonBox, QMessageBox,
    QApplication, QLabel, QPushButton,
)
from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.core import (
    QgsRasterLayer, QgsProject, QgsCoordinateTransform, QgsCoordinateReferenceSystem,
)

from .ui.data_tab import DataTab
from .ui.display_tab import DisplayTab
from .ui.label_tab import LabelTab
from .ui.output_tab import OutputTab
from .core import (
    label_prep, style_extractor, geojson_writer, config_builder, html_builder, layer_utils,
    tile_layer, settings_store,
)

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'template')


class FacilityAppGeneratorDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.setWindowTitle(self.tr('Map to HTML'))
        self._resize_to_fit_screen(1200, 640)
        # Explicitly modeless (plugin.py opens it with show(), not
        # exec()): the user has to be able to keep working in QGIS -
        # changing a layer's symbology, adding a layer - while this is
        # open, then pull those changes in with the データ設定 tab's
        # 再読み込み button.
        self.setModal(False)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMinMaxButtonsHint)
        # Set by plugin.py's unload() - closing because QGIS is exiting
        # or the plugin is being reloaded must not stop on a question.
        self.skip_close_prompt = False
        self._build_ui()
        # Settings are kept in the QGIS project between sessions
        # (core/settings_store.py). The fresh tabs' values are what
        # 初期状態に戻す goes back to; the snapshot after restoring is
        # what closing compares against, so just opening and closing
        # the dialog doesn't modify the project.
        self._default_state = self._collect_state()
        # Settings are written to the project that was open when the
        # dialog opened - never into a different one opened since.
        self._project_file = QgsProject.instance().fileName()
        self._restore_state()
        self._saved_snapshot = self._collect_state()

    def _resize_to_fit_screen(self, width, height):
        """Open at the preferred size, but never taller/wider than the
        screen actually has room for. A dialog that opens larger than
        the desktop can't be shrunk back on Windows once its title bar
        is off-screen, which stranded the 生成/閉じる buttons out of
        reach as this dialog's settings grew."""
        # primaryScreen() can be None on a headless/offscreen Qt
        # platform - checked explicitly rather than wrapped in a
        # catch-all, so a real failure here isn't silently discarded.
        screen = QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            width = min(width, available.width() - 60)
            height = min(height, available.height() - 80)
        self.resize(max(width, 480), max(height, 360))

    def _build_ui(self):
        root = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.data_tab = DataTab()
        self.label_tab = LabelTab(self.iface)
        self.display_tab = DisplayTab()
        self.output_tab = OutputTab()
        self.tabs.addTab(self.data_tab, self.tr('データ設定'))
        self.tabs.addTab(self.label_tab, self.tr('ラベル設定'))
        self.tabs.addTab(self.display_tab, self.tr('表示設定'))
        self.tabs.addTab(self.output_tab, self.tr('出力設定'))
        root.addWidget(self.tabs)

        self.output_tab.btn_generate.clicked.connect(self._on_generate)
        # Cheap enough to just refresh whenever the user lands on 表示設定,
        # which also covers layers added since the dialog opened.
        self.tabs.currentChanged.connect(self._on_tab_changed)

        row_bottom = QHBoxLayout()
        btn_reset = QPushButton(self.tr('設定を初期状態に戻す'))
        btn_reset.setToolTip(self.tr(
            'データ設定・表示設定・出力設定を、初めて開いたときの状態に戻します。\n'
            '（各レイヤーのポップアップ・フィルター項目の設定は、そのまま残ります）'))
        btn_reset.clicked.connect(self._on_reset_settings)
        row_bottom.addWidget(btn_reset)
        self.lbl_state = QLabel('')
        self.lbl_state.setStyleSheet('color:#767c87;')
        self.lbl_state.setWordWrap(True)
        row_bottom.addWidget(self.lbl_state, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        # Only rejected, not also the button's clicked: the Close button
        # emits both, and closing twice would ask the label question
        # below a second time after the user answered キャンセル.
        buttons.rejected.connect(self.close)
        row_bottom.addWidget(buttons)
        root.addLayout(row_bottom)

    # ------------------------------------------------------------
    def _collect_state(self):
        return {
            'data': self.data_tab.get_state(),
            'display': self.display_tab.get_state(),
            'output': self.output_tab.get_state(),
        }

    def _restore_state(self):
        state = settings_store.load()
        if not state:
            return
        restored_layers = self.data_tab.set_state(state.get('data'))
        self.display_tab.set_state(state.get('display'))
        self.output_tab.set_state(state.get('output'))
        message = self.tr('前回の設定（このQGISプロジェクトに保存）を読み込みました。')
        saved_layers = state.get('data') or []
        if restored_layers < len(saved_layers):
            message += ' ' + self.tr('プロジェクトに見つからないレイヤー {0} 件は除きました。').format(
                len(saved_layers) - restored_layers)
        self.lbl_state.setText(message)

    def _save_state(self, force=False):
        if QgsProject.instance().fileName() != self._project_file:
            return
        state = self._collect_state()
        if not force and state == self._saved_snapshot:
            return
        settings_store.save(state)
        self._saved_snapshot = state

    def _on_reset_settings(self):
        answer = QMessageBox.question(
            self, self.tr('設定を初期状態に戻す'),
            self.tr('データ設定・表示設定・出力設定を初期状態に戻しますか？\n'
                    'このプロジェクトに保存されている前回の設定も消去されます。'),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.data_tab.reset_to_visible_layers()
        self.display_tab.set_state(self._default_state['display'])
        self.output_tab.set_state(self._default_state['output'])
        settings_store.clear()
        self._saved_snapshot = self._collect_state()
        self.lbl_state.setText(self.tr('設定を初期状態に戻しました。'))

    # ------------------------------------------------------------
    def reject(self):
        """Every way of closing ends up here (閉じる, the window's ×,
        Esc - QDialog.closeEvent calls reject()), so this is where the
        ラベル設定 tab's "Web" styles are offered to be switched back."""
        if not self.skip_close_prompt and not self._confirm_restore_label_styles():
            return
        if not self.skip_close_prompt:
            self._save_state()
        super().reject()

    def _confirm_restore_label_styles(self):
        """Ask whether layers left on the "Web" label style should go
        back to their working style. Returns False if the user cancels
        (the dialog then stays open)."""
        layers = [
            entry['layer'] for entry in reversed(self.data_tab.get_layers())
            if not isinstance(entry['layer'], QgsRasterLayer)
            and label_prep.is_web_style_active(entry['layer'])
        ]
        if not layers:
            return True

        names = '\n'.join('・' + layer.name() for layer in layers[:10])
        if len(layers) > 10:
            names += '\n' + self.tr('ほか {0} レイヤー').format(len(layers) - 10)
        answer = QMessageBox.question(
            self, self.tr('ラベルを元に戻しますか？'),
            self.tr('次のレイヤーのラベルが「Web用」スタイルのままです。\n'
                    '作業用スタイルに戻してから閉じますか？\n\n{0}').format(names),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        if answer == QMessageBox.StandardButton.Yes:
            for layer in layers:
                label_prep.restore_base_style(layer)
            self.iface.mapCanvas().refreshAllLayers()
        return True

    def _filter_summary(self, layers):
        """Completion-message lines saying which layers each filter
        narrows (spec feedback: どのレイヤーに対してフィルター掛けして
        いるのか分からない)."""
        targets = {}  # field name -> [layer label]
        for entry in layers:
            for item in entry.get('filter_config') or []:
                targets.setdefault(item['name'], []).append(entry['label'])
        if not targets:
            return ''
        lines = [self.tr('フィルターの対象レイヤー:')]
        for name, labels in targets.items():
            lines.append('  {0} → {1}'.format(name, '、'.join(labels)))
        return '\n\n' + '\n'.join(lines)

    @staticmethod
    def _filter_field_names(layers, display_settings):
        """Every field name ticked as a filter on ANY layer, in first-
        seen order - empty when the filter bar is off, so an export
        without it is unchanged. Ticking a field on one layer is enough:
        _filter_fields then applies it to every layer that has a field
        of that name (spec feedback: ticking it on only one of several
        sibling layers left the others silently unfiltered)."""
        if not display_settings.get('filterEnabled'):
            return []
        names = []
        for entry in layers:
            for name in entry.get('filter_fields') or []:
                if name not in names:
                    names.append(name)
        return names

    @staticmethod
    def _filter_fields(entry, filter_names):
        """[{'name', 'key'}] for this layer's part of the filter bar:
        each pooled filter name the layer actually has. A filter field
        hidden from the popup is still written to the GeoJSON (the bar
        needs its values) under a '_flt_' key the template treats as
        internal."""
        layer_names = entry['layer'].fields().names()
        field_order = entry.get('field_order')
        shown = set(field_order if field_order is not None else layer_names)
        return [
            {'name': name, 'key': name if name in shown else '_flt_' + name}
            for name in filter_names if name in layer_names
        ]

    def _on_tab_changed(self, index):
        if self.tabs.widget(index) is self.data_tab:
            self.data_tab.refresh_label_styles()
        elif self.tabs.widget(index) is self.display_tab:
            self._sync_name_field_choices()
        elif self.tabs.widget(index) is self.label_tab:
            # Follows whatever is currently added on データ設定, listed
            # top-first like that tab's table (get_layers() is in map
            # stacking order, bottom-first).
            self.label_tab.set_layers([
                entry['layer'] for entry in reversed(self.data_tab.get_layers())
                if not isinstance(entry['layer'], QgsRasterLayer)
            ])

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
                # Symbology that had to be approximated (spec item 10-C:
                # a silently changed appearance is the worst outcome).
                style_warnings = []
                filter_names = self._filter_field_names(layers, display_settings)
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
                        entry['layer'], fill_opacity_override=fill_opacity_override,
                        warnings=style_warnings,
                    )
                    label_evaluator = style_extractor.build_label_text_evaluator(entry['layer'])
                    geojson_path = os.path.join(tmp_dir, f'layer_{index}.geojson')
                    filter_fields = self._filter_fields(entry, filter_names)
                    geojson_writer.write_sites_geojson(
                        entry['layer'], geojson_path, label_evaluator, id_field=None,
                        field_order=entry.get('field_order'),
                        extra_fields={
                            item['name']: item['key'] for item in filter_fields
                            if item['key'] != item['name']
                        },
                        # Features in a category the user unchecked in QGIS
                        # are invisible there, so they're not exported.
                        feature_filter=style_extractor.build_render_filter(entry['layer']),
                    )
                    layer_bundle.append({
                        'id': entry['id'],
                        'geojson_path': geojson_path,
                        'style': style,
                    })
                    entry['filter_config'] = filter_fields

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
                            'filterFields': entry.get('filter_config') or [],
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
            if style_warnings:
                message += '\n\n' + self.tr('以下は見た目が変わっている可能性があります:\n') + \
                    '\n'.join(dict.fromkeys(style_warnings))
            if display_settings.get('filterEnabled'):
                message += self._filter_summary(layers)
            if display_settings.get('filterEnabled') and not any(
                    entry.get('filter_config') for entry in layers):
                # The bar only appears once some field is picked, so say
                # why it's missing instead of leaving the user to guess.
                message += '\n\n' + self.tr(
                    'フィルターバーはオンですが、フィルター項目が選ばれていないため表示されません。\n'
                    'データ設定タブの「ポップアップ・フィルター項目」→「設定…」で、'
                    '「フィルター」列にチェックしてください。')
            self.output_tab.set_result(message, is_error=False)
            self._save_state(force=True)
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
