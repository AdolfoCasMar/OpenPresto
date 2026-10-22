"""Entrega portable de un proyecto con sus documentos locales vinculados."""
from pathlib import Path
import os
import re
import tempfile
import zipfile
from .storage import dumps, loads
from .budget import BudgetError


def export_bundle(budget, destination, project_path=None):
    destination = Path(destination)
    clone = loads(dumps(budget))
    sources = []
    for index, row in enumerate(clone.documents,1):
        source = Path(row['path'])
        if not source.is_absolute():
            if project_path is None:
                raise BudgetError('Guarda el proyecto para resolver documentos relativos')
            source = Path(project_path).parent / source
        source = source.resolve()
        if not source.is_file():
            raise BudgetError('Documento no encontrado: ' + str(source))
        safe = re.sub(r'[^\w. -]', '_', source.name)
        name = f'documents/{index:04d}_{safe}'
        row['path'] = name
        sources.append((source,name))
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent,suffix='.zip',delete=False) as stream:
            temporary = Path(stream.name)
        with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('project.openpresto.json',dumps(clone))
            archive.writestr('LEEME.txt','Extrae toda la carpeta y abre project.openpresto.json con OpenPresto.\n')
            for source,name in sources:
                archive.write(source,name)
        with temporary.open('rb+') as stream:
            os.fsync(stream.fileno())
        os.link(temporary,destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def choose_bundle(host):
    from PySide6.QtWidgets import QFileDialog
    from .preferences import working_directory
    host.flush_text()
    path,_ = QFileDialog.getSaveFileName(host,'Proyecto con documentos',working_directory(),'ZIP (*.zip)')
    if not path:
        return
    if not path.lower().endswith('.zip'):
        path += '.zip'
    try:
        export_bundle(host.budget,path,host.path)
        host.statusBar().showMessage('Paquete de proyecto y documentos creado',7000)
    except (ValueError,OSError,ArithmeticError) as exc:
        host._error(exc)
