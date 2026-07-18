# -*- coding: utf-8 -*-
import os
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon


class FacilityAppGeneratorPlugin:
    """Entry point registered with QGIS. Opens an independent QDialog
    (not a dock panel) where the user configures and exports the
    facility search web app."""

    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None

    def initGui(self):
        icon_path = os.path.join(os.path.dirname(__file__), 'icon.svg')
        self.action = QAction(
            QIcon(icon_path) if os.path.exists(icon_path) else QIcon(),
            self.tr('Map to HTML'),
            self.iface.mainWindow()
        )
        self.action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToWebMenu(self.tr('Map to HTML'), self.action)

    def unload(self):
        self.iface.removePluginWebMenu(self.tr('Map to HTML'), self.action)
        self.iface.removeToolBarIcon(self.action)
        if self.dialog is not None:
            self.dialog.close()
            self.dialog = None

    def run(self):
        # Recreate each time so the dialog always reflects the current
        # project's layers (a fresh QDialog, not a persistent dock widget).
        from .dialog import FacilityAppGeneratorDialog
        self.dialog = FacilityAppGeneratorDialog(self.iface, self.iface.mainWindow())
        self.dialog.show()

    def tr(self, message):
        from qgis.PyQt.QtCore import QCoreApplication
        return QCoreApplication.translate('FacilityAppGeneratorPlugin', message)
