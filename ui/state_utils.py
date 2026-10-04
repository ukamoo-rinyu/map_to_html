# -*- coding: utf-8 -*-
"""Read and restore plain widget values, so a tab can hand its settings
to core/settings_store.py as JSON and get them back next time the
dialog opens. Each tab names its widgets once ({key: widget}); values
that no longer fit a widget (a combo choice that was removed, a number
out of range) are skipped, leaving that widget at its default."""
from qgis.PyQt.QtWidgets import (
    QCheckBox, QRadioButton, QSpinBox, QDoubleSpinBox, QSlider, QComboBox, QLineEdit,
)


def widget_value(widget):
    if isinstance(widget, (QCheckBox, QRadioButton)):
        return widget.isChecked()
    if isinstance(widget, (QSpinBox, QDoubleSpinBox, QSlider)):
        return widget.value()
    if isinstance(widget, QComboBox):
        return widget.currentText() if widget.isEditable() else widget.currentData()
    if isinstance(widget, QLineEdit):
        return widget.text()
    raise TypeError('Unsupported widget: {0}'.format(type(widget).__name__))


def set_widget_value(widget, value):
    if value is None:
        return
    if isinstance(widget, QRadioButton):
        # Only the chosen button is stored as True; checking it unchecks
        # the rest of its exclusive group, and a False can't uncheck one.
        if value is True:
            widget.setChecked(True)
    elif isinstance(widget, QCheckBox):
        widget.setChecked(bool(value))
    elif isinstance(widget, (QSpinBox, QSlider)):
        if isinstance(value, (int, float)) and widget.minimum() <= value <= widget.maximum():
            widget.setValue(int(value))
    elif isinstance(widget, QDoubleSpinBox):
        if isinstance(value, (int, float)) and widget.minimum() <= value <= widget.maximum():
            widget.setValue(float(value))
    elif isinstance(widget, QComboBox):
        if widget.isEditable():
            widget.setEditText(str(value))
        else:
            index = widget.findData(value)
            if index >= 0:
                widget.setCurrentIndex(index)
    elif isinstance(widget, QLineEdit):
        widget.setText(str(value))


def widgets_state(widgets):
    return {key: widget_value(widget) for key, widget in widgets.items()}


def apply_widgets_state(widgets, state):
    if not isinstance(state, dict):
        return
    for key, widget in widgets.items():
        if key in state:
            set_widget_value(widget, state[key])
