from __future__ import annotations

import argparse
from pathlib import Path
import sys

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QSortFilterProxyModel, QSaveFile, QIODevice
from PySide6.QtGui import QAction, QKeySequence, QIcon
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTableView, QHeaderView, QSplitter, QTextEdit,
    QFileDialog, QMessageBox, QTabWidget, QToolBar, QAbstractItemView)

from . import APP_ID, __version__
from .bc3 import BC3Error, Document, concepts_csv, read


class ConceptsModel(QAbstractTableModel):
    HEADERS = ("Código", "Unidad", "Resumen", "Precio declarado")

    def __init__(self):
        super().__init__()
        self.document: Document | None = None

    def set_document(self, document):
        self.beginResetModel()
        self.document = document
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() or self.document is None else len(self.document.concepts)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section] if orientation == Qt.Orientation.Horizontal else section + 1

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or self.document is None:
            return None
        c = self.document.concepts[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return (c.code, c.unit, c.summary, str(c.price) if c.price is not None else "—")[index.column()]
        if role == Qt.ItemDataRole.TextAlignmentRole and index.column() == 3:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.ToolTipRole:
            return c.summary


class ConceptsProxy(QSortFilterProxyModel):
    def lessThan(self, left, right):
        if left.column() == 3:
            concepts = self.sourceModel().document.concepts
            a, b = concepts[left.row()].price, concepts[right.row()].price
            if a is None:
                return b is not None
            return b is not None and a < b
        return super().lessThan(left, right)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.document = None
        self.source_path = None
        self.setWindowTitle("OpenPresto · Explorador BC3")
        self.resize(1180, 780)
        self.setMinimumSize(760, 500)
        self.model = ConceptsModel()
        self.proxy = ConceptsProxy()
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterKeyColumn(-1)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        toolbar = QToolBar("Archivo", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        menu = self.menuBar().addMenu("&Archivo")
        self.open_action = QAction("Abrir BC3…", self)
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_action.triggered.connect(self.choose_file)
        self.copy_action = QAction("Guardar copia BC3…", self)
        self.copy_action.triggered.connect(self.save_copy)
        self.csv_action = QAction("Exportar conceptos a CSV…", self)
        self.csv_action.triggered.connect(self.export_csv)
        for action in (self.open_action, self.copy_action, self.csv_action):
            toolbar.addAction(action)
            menu.addAction(action)
        self.copy_action.setEnabled(False)
        self.csv_action.setEnabled(False)
        menu.addSeparator()
        quit_action = menu.addAction("Salir")
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        help_menu = self.menuBar().addMenu("&Ayuda")
        help_menu.addAction("Acerca de OpenPresto", self.about)

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(12)
        heading = QHBoxLayout()
        self.title = QLabel("Tus presupuestos, abiertos")
        font = self.title.font()
        font.setPointSize(20)
        font.setBold(True)
        self.title.setFont(font)
        heading.addWidget(self.title, 1)
        demo = QPushButton("Abrir ejemplo")
        demo.clicked.connect(self.open_demo)
        heading.addWidget(demo)
        layout.addLayout(heading)
        self.subtitle = QLabel("Abre un archivo BC3 para consultar sus conceptos, precios declarados y textos.")
        self.subtitle.setWordWrap(True)
        layout.addWidget(self.subtitle)
        notice = QLabel("Vista de consulta · Mediciones, descomposiciones y totales todavía no se calculan.")
        notice.setWordWrap(True)
        notice.setStyleSheet("QLabel { background: #e8f1fa; color: #23415e; padding: 10px; border-radius: 5px; }")
        layout.addWidget(notice)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar por código, unidad o descripción…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.filter_rows)
        layout.addWidget(self.search)

        splitter = QSplitter(Qt.Orientation.Vertical)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 160)
        self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(3, 160)
        self.table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.table.selectionModel().currentChanged.connect(self.show_concept)
        splitter.addWidget(self.table)
        self.tabs = QTabWidget()
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlaceholderText("Selecciona un concepto para ver su descripción completa.")
        self.diagnostics = QTextEdit()
        self.diagnostics.setReadOnly(True)
        self.diagnostics.setPlainText("Todavía no hay ningún archivo abierto.")
        self.tabs.addTab(self.details, "Descripción")
        self.tabs.addTab(self.diagnostics, "Información de importación")
        splitter.addWidget(self.tabs)
        splitter.setSizes([440, 180])
        layout.addWidget(splitter, 1)
        self.setCentralWidget(root)
        self.statusBar().showMessage(f"OpenPresto {__version__} · Versión inicial de consulta")

    def filter_rows(self, text):
        self.proxy.setFilterFixedString(text)
        if self.proxy.rowCount():
            self.table.setCurrentIndex(self.proxy.index(0, 0))
            self.show_concept(self.table.currentIndex())
        else:
            self.details.clear()
        if self.document:
            self.statusBar().showMessage(f"{self.proxy.rowCount()} de {len(self.document.concepts)} conceptos · Consulta sin modificar el original")

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Abrir presupuesto BC3", "", "Intercambio FIEBDC (*.bc3 *.BC3)")
        if path:
            self.load_path(path)

    def load_path(self, path):
        try:
            document = read(path)
        except (OSError, BC3Error) as exc:
            QMessageBox.warning(self, "No se ha podido abrir el archivo", str(exc))
            return False
        self.document, self.source_path = document, Path(path)
        self.model.set_document(document)
        self.search.clear()
        self.details.clear()
        self.title.setText(self.source_path.name)
        self.title.setToolTip(str(self.source_path))
        self.subtitle.setText(f"{len(document.concepts)} conceptos · {document.version} · {document.encoding}")
        self.setWindowTitle(f"{self.source_path.name} — OpenPresto")
        self.copy_action.setEnabled(True)
        self.csv_action.setEnabled(True)
        counts = "\n".join(f"~{k}: {v}" for k, v in sorted(document.counts.items()))
        warnings = "\n".join("• " + w for w in document.warnings[:200]) or "Sin avisos del lector de conceptos."
        if len(document.warnings) > 200:
            warnings += f"\n… {len(document.warnings) - 200} avisos adicionales."
        self.diagnostics.setPlainText(f"Origen: {document.generator}\nFormato: {document.version}\nCodificación: {document.encoding}\n\nRegistros\n{counts}\n\nAvisos\n{warnings}\n\nLa copia BC3 conserva exactamente los bytes originales. El CSV solo contiene los conceptos mostrados, no el presupuesto completo.")
        self.filter_rows(self.search.text())
        if self.proxy.rowCount():
            self.table.selectRow(0)
        return True

    def show_concept(self, current, previous=None):
        if self.document is None or not current.isValid():
            self.details.clear()
            return
        concept = self.document.concepts[self.proxy.mapToSource(current).row()]
        self.details.setPlainText(f"{concept.code} · {concept.summary}\n\n{concept.text or 'Sin texto ampliado en el registro ~T.'}")

    def open_demo(self):
        self.load_path(Path(__file__).with_name("data") / "ejemplo.bc3")

    def write_export(self, path, data):
        same_source = self.source_path and Path(path).resolve() == self.source_path.resolve()
        if self.source_path and Path(path).exists():
            try:
                same_source = same_source or Path(path).samefile(self.source_path)
            except OSError:
                pass
        if same_source:
            QMessageBox.warning(self, "Elige otro archivo", "La exportación no puede sobrescribir el archivo de origen.")
            return False
        target = QSaveFile(path)
        target.setDirectWriteFallback(True)  # Acceso a archivo individual mediante portal.
        if not target.open(QIODevice.OpenModeFlag.WriteOnly):
            QMessageBox.warning(self, "No se puede guardar", target.errorString())
            return False
        if target.write(data) != len(data):
            target.cancelWriting()
            QMessageBox.warning(self, "No se puede guardar", target.errorString())
            return False
        if not target.commit():
            QMessageBox.warning(self, "No se puede guardar", target.errorString())
            return False
        self.statusBar().showMessage(f"Guardado: {Path(path).name}")
        return True

    def save_copy(self):
        if not self.document:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Guardar copia íntegra del BC3", self.source_path.stem + "-copia.bc3", "BC3 (*.bc3)")
        if path:
            self.write_export(path, self.document.raw)

    def export_csv(self):
        if not self.document:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar todos los conceptos", self.source_path.stem + "-conceptos.csv", "CSV (*.csv)")
        if path:
            self.write_export(path, concepts_csv(self.document))

    def about(self):
        QMessageBox.about(self, "OpenPresto", f"OpenPresto {__version__}\n\nPrototipo independiente para explorar archivos BC3.\nLectura parcial de conceptos y textos; no sustituye todavía a Presto.\n\nFormatos internos de Presto, edición, cálculos y mediciones: pendientes.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="OpenPresto · Explorador BC3")
    parser.add_argument("file", nargs="?", help="Archivo BC3")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)
    app = QApplication([sys.argv[0]])
    app.setApplicationName("OpenPresto")
    app.setOrganizationName("OpenPresto")
    app.setApplicationVersion(__version__)
    app.setDesktopFileName(APP_ID)
    icon = Path(__file__).with_name("data") / "openpresto.svg"
    app.setWindowIcon(QIcon(str(icon)))
    window = MainWindow()
    window.show()
    if args.file:
        window.load_path(args.file)
    return app.exec()
