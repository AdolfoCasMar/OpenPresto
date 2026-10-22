"""Metadatos de proyecto y referencias documentales portables."""
import json
from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QFileDialog, QInputDialog


def properties(host):
    dialog = QDialog(host)
    dialog.setWindowTitle('Propiedades del proyecto')
    layout = QFormLayout(dialog)
    fields = {}
    for key, label in [('title', 'Título'), ('author', 'Autor'), ('client', 'Cliente'),
                       ('location', 'Emplazamiento'), ('currency', 'Moneda')]:
        edit = QLineEdit(host.budget.project_metadata.get(key, 'EUR' if key == 'currency' else ''))
        fields[key] = edit
        layout.addRow(label, edit)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addRow(buttons)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        host._execute('project.properties.set', changes={key:edit.text() for key,edit in fields.items()})


def attach_document(host):
    path, _ = QFileDialog.getOpenFileName(host, 'Vincular documento', '', 'Todos los archivos (*)')
    if not path:
        return
    code = host.active_concept or host.budget.root_code
    host._execute('project.document.attach', code=code, path=path)


def open_document(host):
    from pathlib import Path
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtCore import QUrl
    rows = [row for row in host.budget.documents if row['concept'] in
            (host.active_concept, host.budget.root_code)]
    if not rows:
        host._error('No hay documentos vinculados al concepto o al proyecto')
        return
    path, ok = QInputDialog.getItem(host, 'Documentos vinculados', 'Archivo:', [row['path'] for row in rows], 0, False)
    if ok:
        target = Path(path)
        if not target.is_absolute() and host.path:
            target = host.path.parent / target
        if not target.is_file() or not QDesktopServices.openUrl(QUrl.fromLocalFile(str(target.resolve()))):
            host._error('No se pudo abrir el documento: ' + str(target))


def remove_document(host):
    rows = list(host.budget.documents)
    if not rows:
        host._error('No hay documentos vinculados')
        return
    labels = [str(i+1) + ': ' + row['concept'] + ' — ' + row['path'] for i,row in enumerate(rows)]
    selected,ok = QInputDialog.getItem(host,'Retirar vínculo documental','Se retira solo el vínculo del proyecto:',labels,0,False)
    if ok:
        index = labels.index(selected)
        host._execute('project.document.remove', index=index)
