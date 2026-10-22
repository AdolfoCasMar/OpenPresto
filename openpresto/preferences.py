"""Preferencias persistentes de escritorio aplicadas a operaciones reales."""
from pathlib import Path
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QDialog, QFormLayout, QSpinBox, QDialogButtonBox, QLineEdit, QComboBox


def working_directory():
    value = QSettings().value('files/directory', '', type=str)
    return value if value and Path(value).is_dir() else str(Path.home())


def apply(host):
    settings = QSettings()
    font = host.font()
    font.setPointSize(max(8, min(24, settings.value('appearance/font_size', 10, type=int))))
    host.setFont(font)
    if hasattr(host, '_recovery_timer'):
        minutes = max(1, min(60, settings.value('recovery/minutes', 2, type=int)))
        host._recovery_timer.setInterval(minutes * 60000)


def configure(host):
    settings = QSettings()
    dialog = QDialog(host)
    dialog.setWindowTitle('Preferencias de OpenPresto')
    layout = QFormLayout(dialog)
    interval = QSpinBox()
    interval.setRange(1,60)
    interval.setValue(settings.value('recovery/minutes', 2, type=int))
    layout.addRow('Recuperación automática (minutos)',interval)
    size = QSpinBox()
    size.setRange(8,24)
    size.setValue(settings.value('appearance/font_size', 10, type=int))
    layout.addRow('Tamaño del texto',size)
    directory = QLineEdit(working_directory())
    layout.addRow('Carpeta de trabajo', directory)
    separator = QComboBox()
    separator.addItems([';', ',', '\t'])
    separator.setCurrentText(settings.value('export/csv_separator', ';', type=str))
    layout.addRow('Separador CSV', separator)
    decimal_separator = QComboBox()
    decimal_separator.addItems(['.', ','])
    decimal_separator.setCurrentText(settings.value('numbers/decimal_separator','.',type=str))
    layout.addRow('Separador decimal en tablas',decimal_separator)
    encoding = QComboBox()
    encoding.addItems(['utf-8-sig','utf-8','cp1252'])
    encoding.setCurrentText(settings.value('export/csv_encoding','utf-8-sig',type=str))
    layout.addRow('Codificación CSV',encoding)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addRow(buttons)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return
    target = Path(directory.text()).expanduser()
    if not target.is_dir():
        host._error('La carpeta de trabajo debe existir')
        return
    for key,value in {'recovery/minutes':interval.value(), 'appearance/font_size':size.value(),
                      'files/directory':str(target.resolve()), 'export/csv_separator':separator.currentText(),
                      'export/csv_encoding':encoding.currentText(), 'numbers/decimal_separator':decimal_separator.currentText()}.items():
        settings.setValue(key,value)
    settings.sync()
    if settings.status() != QSettings.Status.NoError:
        host._error('No se pudieron guardar las preferencias')
        return
    apply(host)
    host.refresh()
