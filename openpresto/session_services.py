"""Servicios de sesión, recientes y recuperación de escritorio."""
from pathlib import Path
from PySide6.QtCore import QSettings, QStandardPaths, QTimer
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox
from .storage import save_budget
from .history_snapshots import capture_snapshot, restore_snapshot

_WINDOWS = []


def another_window(host):
    from .mdi_workspace import PrestoWorkspace
    window = PrestoWorkspace()
    _WINDOWS.append(window)
    window.destroyed.connect(lambda: _WINDOWS.remove(window) if window in _WINDOWS else None)
    window.setAttribute(__import__('PySide6.QtCore', fromlist=['Qt']).Qt.WidgetAttribute.WA_DeleteOnClose)
    window.show()


def recent(host):
    settings = QSettings()
    paths = settings.value('files/recent', [], type=list)
    recovery_root = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)) / 'recovery'
    available = [str(p) for p in paths if Path(str(p)).is_file()
                 and Path(str(p)).suffix.lower() != '.bak' and Path(str(p)).resolve().parent != recovery_root.resolve()]
    if not available:
        host.statusBar().showMessage('No hay proyectos recientes disponibles', 5000)
        return
    path, ok = QInputDialog.getItem(host, 'Proyectos recientes', 'Archivo:', available, 0, False)
    if ok and host._confirm_discard():
        host.load_path(path)


def remember(path):
    settings = QSettings()
    resolved = Path(path).resolve()
    recovery_root = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)) / 'recovery'
    if resolved.suffix.lower() == '.bak' or resolved.parent == recovery_root.resolve():
        return
    name = str(resolved)
    paths = settings.value('files/recent', [], type=list)
    settings.setValue('files/recent', ([name] + [p for p in paths if p != name])[:20])


def install_recovery(host):
    from uuid import uuid4
    root = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)) / 'recovery'
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        host.statusBar().showMessage('Recuperación automática no disponible: ' + str(exc), 15000)
    host._recovery_path = root / (uuid4().hex + '.openpresto.json')
    timer = QTimer(host)
    def recoverable_save():
        if host.project_open and (host.dirty or host._text_pending):
            try:
                host.flush_text()
                snapshot = restore_snapshot(capture_snapshot(host.budget))
                if host.path is not None:
                    for row in snapshot.documents:
                        document = Path(row['path'])
                        if not document.is_absolute():
                            row['path'] = str((host.path.parent / document).resolve())
                save_budget(snapshot, host._recovery_path)
            except (ValueError, OSError, ArithmeticError) as exc:
                host.statusBar().showMessage('No se pudo guardar recuperación: ' + str(exc), 10000)
    timer.timeout.connect(recoverable_save)
    timer.start(QSettings().value('recovery/minutes', 2, type=int) * 60000)
    host._recovery_timer = timer
    def notify_available():
        try:
            available = any(path != host._recovery_path for path in root.glob('*.openpresto.json'))
        except OSError as exc:
            host.statusBar().showMessage('No se pudo consultar recuperación: ' + str(exc),10000)
            return
        if available:
            host.statusBar().showMessage('Hay copias automáticas disponibles en Archivo → Recuperar proyecto.',15000)
    QTimer.singleShot(0,notify_available)


def recover(host):
    root = host._recovery_path.parent
    try:
        files = sorted(root.glob('*.openpresto.json'), key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError as exc:
        host._error('No se pudieron consultar las recuperaciones: ' + str(exc))
        return
    if not files:
        host.statusBar().showMessage('No hay archivos de recuperación', 5000)
        return
    names = [str(p) for p in files]
    path, ok = QInputDialog.getItem(host, 'Recuperar proyecto', 'Copia automática:', names, 0, False)
    if ok and host._confirm_discard() and host.load_path(path):
        host.path = None
        host._file_revision = None
        host.dirty = True
        host._saved_snapshot = None
        host.refresh()


def preferences(host):
    from .preferences import configure
    configure(host)


def cleanup_recovery(host):
    path = getattr(host, '_recovery_path', None)
    if path is None:
        return
    try:
        path.unlink(missing_ok=True)
        path.with_name(path.name + '.bak').unlink(missing_ok=True)
    except OSError as exc:
        host.statusBar().showMessage('No se pudo retirar la copia de recuperación: ' + str(exc), 10000)


def open_backup(host):
    from .preferences import working_directory
    path,_ = QFileDialog.getOpenFileName(host,'Abrir copia de seguridad',working_directory(),'Respaldos (*.bak);;Proyectos (*.json)')
    if not path or not host._confirm_discard():
        return
    if host.load_path(path):
        for row in host.budget.documents:
            document = Path(row['path'])
            if not document.is_absolute():
                row['path'] = str((Path(path).parent / document).resolve())
        host.path = None
        host._file_revision = None
        host.dirty = True
        host._reset_history()
        host.refresh()
        host.statusBar().showMessage('Respaldo abierto. Guarda un proyecto nuevo para conservar los cambios.',10000)
