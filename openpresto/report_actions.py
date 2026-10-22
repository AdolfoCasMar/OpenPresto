"""Acciones de salida del espacio de trabajo."""
from pathlib import Path
import os
import tempfile
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QFileDialog, QInputDialog
from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog, QPageSetupDialog
from .reports import report_html, report_csv
from .preferences import working_directory
from .page_settings import restore as restore_page_layout, save as save_page_layout
from PySide6.QtCore import QSettings


def export_report(host, kind=None):
    host.flush_text()
    if kind is None:
        kind,accepted = QInputDialog.getItem(host,'Informe','Contenido:',
            ['presupuesto','resumen','mediciones','precios','economico','certificaciones','planificacion','recursos','gestion','existencias','vencimientos'],0,False)
        if not accepted:return
    path, selected = QFileDialog.getSaveFileName(host, 'Exportar informe', working_directory(),
        'PDF (*.pdf);;HTML (*.html);;CSV (*.csv)')
    if not path:
        return
    try:
        suffix = {'PDF (*.pdf)': '.pdf', 'HTML (*.html)': '.html', 'CSV (*.csv)': '.csv'}.get(selected, '.pdf')
        target = Path(path)
        if not target.suffix:
            target = target.with_suffix(suffix)
        if target.suffix.lower() != suffix:
            raise ValueError('La extensión debe corresponder al formato elegido')
        if host.path and target.resolve() == host.path.resolve():
            raise ValueError('El informe debe guardarse en otro archivo')
        if suffix == '.pdf':
            document = QTextDocument()
            document.setHtml(report_html(host.budget, kind))
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            layout = restore_page_layout(host)
            if layout is not None:
                printer.setPageLayout(layout)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(suffix='.pdf', dir=target.parent, delete=False) as stream:
                    temporary = Path(stream.name)
                printer.setOutputFileName(str(temporary))
                document.print_(printer)
                if not temporary.is_file() or temporary.stat().st_size == 0:
                    raise OSError('No se pudo generar el PDF')
                os.replace(temporary, target)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
        else:
            text = report_csv(host.budget, kind, QSettings().value('export/csv_separator', ';', type=str)) if suffix == '.csv' else report_html(host.budget, kind)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', encoding=QSettings().value('export/csv_encoding', 'utf-8-sig', type=str) if suffix == '.csv' else 'utf-8',
                        dir=target.parent, delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(text)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, target)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
    except (ValueError, OSError, UnicodeError, LookupError, ArithmeticError, RecursionError) as exc:
        host._error(exc)


def preview_report(host, kind=None):
    host.flush_text()
    if kind is None:
        kind,accepted = QInputDialog.getItem(host,'Vista previa e impresión','Contenido:',
            ['presupuesto','resumen','mediciones','precios','economico','certificaciones','planificacion','recursos','gestion','existencias','vencimientos'],0,False)
        if not accepted:return
    try:
        document = QTextDocument()
        document.setHtml(report_html(host.budget,kind))
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        layout = restore_page_layout(host)
        if layout is not None:
            printer.setPageLayout(layout)
        dialog = QPrintPreviewDialog(printer, host)
        dialog.paintRequested.connect(document.print_)
        dialog.exec()
    except (ValueError, ArithmeticError, RecursionError) as exc:
        host._error(exc)


def configure_page(host):
    from PySide6.QtWidgets import QDialog
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    layout = restore_page_layout(host)
    if layout is not None:
        printer.setPageLayout(layout)
    dialog = QPageSetupDialog(printer,host)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        host._report_page_layout = printer.pageLayout()
        try:
            save_page_layout(host._report_page_layout)
        except ValueError as exc:
            host._error(exc)
