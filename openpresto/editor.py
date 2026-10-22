"""Editor de presupuestos, mediciones BC3 y proyectos JSON."""
from __future__ import annotations
from .storage import economic_document, load_budget_revision, MAX_FILE_BYTES
from .preferences import working_directory
from .number_format import display, input_number

import sys
from decimal import Decimal
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt, QEventLoop
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QSpinBox,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QProgressDialog, QPushButton, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from .budget import Budget, BudgetConcept, BudgetError, BudgetMeasurement, BudgetRelation
from .calculations import calculator_for as BudgetCalculator
from .storage import StorageError, load_budget, save_budget, dumps, to_dict, from_dict
from .history_snapshots import capture_snapshot, restore_snapshot
from .bc3_importer import import_bc3, BC3ImportError
from .pzh_importer import import_pzh, PZHCompressedTextError
from .bc3_measurements import BC3MeasurementLine, rebuild_record, MeasurementParseError

FILE_FILTER = "Presupuesto OpenPresto (*.openpresto.json);;JSON (*.json)"


class ConceptDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nuevo concepto")
        form = QFormLayout(self)
        self.code = QLineEdit()
        self.unit = QLineEdit()
        self.summary = QLineEdit()
        self.nature = QLineEdit()
        self.price = QLineEdit("0")
        self.measurement_decimals = QSpinBox()
        self.measurement_decimals.setRange(-1, 12)
        self.measurement_decimals.setValue(-1)
        self.measurement_decimals.setSpecialValueText('Cálculo anterior')
        self.measurement_decimals.setToolTip('Solo mediciones geométricas nativas; conserva las cifras originales. No cambia el motor BC3.')
        for label, widget in [
            ("Código", self.code), ("Unidad", self.unit),
            ("Resumen", self.summary), ("Naturaleza", self.nature),
            ("Precio base", self.price),
            ('Decimales de medición nativa', self.measurement_decimals),
        ]:
            form.addRow(label, widget)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def get_concept(self) -> BudgetConcept:
        return BudgetConcept(
            code=self.code.text().strip(),
            unit=self.unit.text().strip(),
            summary=self.summary.text().strip(),
            nature=self.nature.text().strip(),
            base_price=input_number(self.price.text()),
            measurement_decimals=None if self.measurement_decimals.value() < 0 else self.measurement_decimals.value(),
        )


class RelationDialog(QDialog):
    def __init__(self, concepts: list[str], parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QComboBox
        self.setWindowTitle("Añadir partida o componente")
        form = QFormLayout(self)
        self.parent_code = QComboBox()
        self.child_code = QComboBox()
        self.parent_code.addItems(concepts)
        self.child_code.addItems(concepts)
        self.quantity = QLineEdit("1")
        self.position = QLineEdit("1")
        form.addRow("Concepto superior", self.parent_code)
        form.addRow("Concepto inferior", self.child_code)
        form.addRow("Cantidad", self.quantity)
        form.addRow("Posición", self.position)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def get_relation(self) -> BudgetRelation:
        return BudgetRelation(
            self.parent_code.currentText(), self.child_code.currentText(),
            quantity=input_number(self.quantity.text()),
            position=int(self.position.text().strip()),
        )


class MeasurementDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nueva línea de medición")
        form = QFormLayout(self)
        self.comment = QLineEdit()
        self.n = QLineEdit("1")
        self.length = QLineEdit()
        self.width = QLineEdit()
        self.height = QLineEdit()
        self.formula = QLineEdit()
        self.formula.setPlaceholderText('Opcional: (B+C)/2, SQRT(B), SIN(A)…')
        self.annulled = {}
        for name, caption in (('n_lines', 'N'), ('length', 'Longitud'),
                              ('width', 'Anchura'), ('height', 'Altura')):
            check = QCheckBox('Anular ' + caption + ' en el cálculo')
            self.annulled[name] = check
            form.addRow(check)
        for label, widget in [
            ("Comentario", self.comment), ("N", self.n),
            ("Longitud", self.length), ("Anchura", self.width),
            ("Altura", self.height),
            ('Fórmula de medición', self.formula),
        ]:
            form.addRow(label, widget)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def get_measurement(self, relation_id: str) -> BudgetMeasurement:
        def optional(edit: QLineEdit):
            value = input_number(edit.text())
            return None if not value else value
        return BudgetMeasurement(
            relation_id=relation_id, comment=self.comment.text(),
            n_lines=input_number(self.n.text()),
            length=optional(self.length), width=optional(self.width),
            height=optional(self.height),
            formula=self.formula.text().strip(),
            annulled_dimensions=tuple(name for name, check in self.annulled.items() if check.isChecked()),
        )


class BudgetEditor(QMainWindow):
    """Ventana editable mediante diálogos, sin tocar el lector BC3."""

    def __init__(self):
        super().__init__()
        self.budget = Budget()
        self.path: Path | None = None
        self._file_revision = None
        self.dirty = False
        self._undo = []
        self._redo = []
        self._snapshot = capture_snapshot(self.budget)
        self._saved_snapshot = self._snapshot
        self.setWindowTitle("OpenPresto · Editor de presupuestos")
        self.resize(1100, 700)

        bar = self.addToolBar("Presupuesto")
        for caption, method in [
            ("Nuevo", self.new_budget), ("Abrir", self.open_budget),
            ("Importar BC3", self.import_budget),
            ("Editar", self.edit_selected), ("Eliminar", self.delete_selected),
            ("Deshacer", self.undo), ("Rehacer", self.redo),
            ("Guardar", self.save), ("Guardar como", self.save_as),
            ("Añadir concepto", self.add_concept),
            ("Añadir relación", self.add_relation),
            ("Añadir medición", self.add_measurement),
        ]:
            action = bar.addAction(caption)
            action.triggered.connect(method)

        center = QWidget()
        layout = QVBoxLayout(center)
        self.description = QLabel("Nuevo presupuesto · Añade un concepto y establece su raíz.")
        layout.addWidget(self.description)
        tabs = QTabWidget()
        self.concepts_table = self._table(
            ["Código", "Unidad", "Resumen", "Naturaleza", "Precio calculado"]
        )
        self.relations_table = self._table(
            ["ID", "Superior", "Inferior", "Posición", "Cantidad", "P. unitario", "Importe"]
        )
        self.measurements_table = self._table(
            ["Relación", "Comentario", "N", "Longitud", "Anchura", "Altura", "Parcial"]
        )
        tabs.addTab(self.concepts_table, "Conceptos")
        tabs.addTab(self.relations_table, "Descomposición")
        tabs.addTab(self.measurements_table, "Mediciones")
        layout.addWidget(tabs)
        self.setCentralWidget(center)
        self.refresh()

    @staticmethod
    def _table(headers):
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setDefaultSectionSize(25)
        table.verticalHeader().setMinimumSectionSize(20)
        table.horizontalHeader().setStretchLastSection(True)
        return table

    @staticmethod
    def _fill(table, rows):
        table.setRowCount(len(rows))
        for i, values in enumerate(rows):
            for j, value in enumerate(values):
                table.setItem(i, j, QTableWidgetItem(display(value)))

    def refresh(self):
        calculator = BudgetCalculator(self.budget)
        from .calculations import calculation_batch
        with calculation_batch(calculator):
            concept_rows = [(c.code, c.unit, c.summary, c.nature, calculator.price(c.code))
                            for c in self.budget.concepts.values()]
            relation_rows = []
            for r in self.budget.relations:
                value = calculator.relation(r.id)
                relation_rows.append((r.id[:8], r.parent_code, r.child_code, r.position,
                                      value.quantity, value.unit_price, value.amount))
        self._fill(self.concepts_table, concept_rows)
        self._fill(self.relations_table, relation_rows)
        self._measurement_keys = [("native", m.id) for m in self.budget.measurements]
        self._fill(self.measurements_table, [
            (m.relation_id[:8], m.comment, m.n_lines,
             "" if m.length is None else m.length,
             "" if m.width is None else m.width,
             "" if m.height is None else m.height, self.budget.measurement_partial(m))
            for m in self.budget.measurements
        ])
        for relation_id, record in self.budget.bc3_measurements.items():
            relation = self.budget._relation(relation_id)
            for index, line in enumerate(record.lines):
                row = self.measurements_table.rowCount()
                self.measurements_table.insertRow(row)
                values = (f"{relation.parent_code} → {relation.child_code}",
                          f"[{line.kind or 'normal'}] {line.description}",
                          line.a, line.b, line.c, line.d, line.partial)
                for column, value in enumerate(values):
                    self.measurements_table.setItem(row, column, QTableWidgetItem(display(value)))
                self._measurement_keys.append((relation_id, index))
        root = self.budget.root_code
        total = f" · Total calculado: {calculator.total()}" if root else ""
        if any(w.startswith("Medición no aplicada") for w in self.budget.import_warnings):
            total += " · Revisar avisos: mediciones no aplicadas"
        self.description.setText(f"Raíz: {root or '(sin establecer)'}{total}")
        self.setWindowTitle(
            f"{self.path.name if self.path else 'Sin guardar'}"
            f"{' *' if self.dirty else ''} — OpenPresto"
        )

    def _execute_model(self, command, factory, **params):
        from dataclasses import asdict
        try:
            data = asdict(factory())
        except (ValueError, ArithmeticError, TypeError) as exc:
            self._error(exc)
            return
        self._execute(command, data=data, **params)

    def _execute(self, command, **params):
        from .commands import execute
        try:
            self.budget = execute(self.budget, command, params)
            self._changed()
        except (ValueError, ArithmeticError, TypeError, RecursionError) as exc:
            self._error(exc)

    def _history_context(self):
        return None

    def _capture_history_snapshot(self):
        return replace(capture_snapshot(self.budget),context=self._history_context())

    def _changed(self):
        try:
            calculator = BudgetCalculator(self.budget)
            from .calculations import calculation_batch
            with calculation_batch(calculator):
                for code in self.budget.concepts:
                    calculator.price(code)
            snapshot = capture_snapshot(self.budget)
        except (ValueError, ArithmeticError, RecursionError) as exc:
            self.budget = restore_snapshot(self._snapshot)
            self.refresh()
            self._error(f"Cambio no aplicado: {exc}")
            return
        if snapshot == self._snapshot:
            self.refresh()
            return
        self._undo.append(replace(self._snapshot,context=self._history_context()))
        self._undo = self._undo[-50:]
        self._redo.clear()
        self._snapshot = snapshot
        self.dirty = snapshot != self._saved_snapshot
        self.refresh()

    def _error(self, exc):
        QMessageBox.warning(self, "OpenPresto", str(exc))

    def _confirm_discard(self):
        if not self.dirty:
            return True
        reply = QMessageBox.question(
            self, "Cambios sin guardar",
            "Hay cambios sin guardar. Puedes guardarlos antes de continuar.",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if reply == QMessageBox.StandardButton.Save:
            return bool(self.save())
        return reply == QMessageBox.StandardButton.Discard

    def new_budget(self):
        if not self._confirm_discard():
            return
        self.budget = Budget()
        self.path = None
        self._file_revision = None
        self.dirty = False
        self._reset_history()
        self.refresh()

    def open_budget(self):
        if not self._confirm_discard():
            return
        name, _ = QFileDialog.getOpenFileName(self, "Abrir presupuesto", working_directory(), FILE_FILTER + ";;BC3 (*.bc3);;Presto PZH · experimental (*.pzh)")
        if not name:
            return
        self.load_path(name)

    def _reset_history(self):
        self._undo.clear()
        self._redo.clear()
        self._snapshot = capture_snapshot(self.budget)
        self._saved_snapshot = None if self.dirty else self._snapshot

    def load_path(self, name, *, observed_presto88=False, native_economic=False):
        pzh_options = {}
        progress = None
        if Path(name).suffix.lower() == '.pzh':
            dialog = QDialog(self)
            dialog.setWindowTitle('Importar PZH · elegir módulos')
            layout = QVBoxLayout(dialog)
            layout.addWidget(QLabel('Presupuesto, conceptos, textos y mediciones: siempre incluidos.\nEl original completo se conserva para recuperar otros módulos después.'))
            choices = {}
            for key, title in (('certifications', 'Certificaciones'), ('planning', 'Planificación'), ('management', 'Gestión: entidades, ofertas, documentos y vencimientos de origen')):
                check = QCheckBox(title)
                check.setChecked(True)
                layout.addWidget(check)
                choices[key] = check
            native_copies=QCheckBox('Crear copias editables de los módulos compatibles (documentos como borradores)')
            native_copies.setChecked(True);layout.addWidget(native_copies)
            layout.addWidget(QLabel('Los datos pendientes se detallarán al terminar. No se generan movimientos históricos.'))
            actions = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            actions.accepted.connect(dialog.accept)
            actions.rejected.connect(dialog.reject)
            layout.addWidget(actions)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return False
            progress = QProgressDialog('Preparando importación…', '', 0, 100, self)
            progress.setWindowTitle('Importar PZH')
            progress.setCancelButton(None)
            progress.setWindowModality(Qt.WindowModality.ApplicationModal)
            progress.setMinimumDuration(0)
            progress.setAutoClose(False)
            progress.show()
            def update_progress(value, label):
                progress.setLabelText(label)
                progress.setValue(value)
                QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
            pzh_options = dict(pzh_modules={key for key, check in choices.items() if check.isChecked()},
                               pzh_progress=update_progress, pzh_native_modules=native_copies.isChecked())
        try:
            suffix = Path(name).suffix.lower()
            imported = suffix in ('.bc3', '.pzh')
            from .project_io import load_project
            try:
                opened = load_project(name, observed_presto88=observed_presto88, native_economic=native_economic, **pzh_options)
            except PZHCompressedTextError as exc:
                answer = QMessageBox.question(self, 'Texto PZH no compatible',
                    str(exc) + '\n\n¿Importar el resto del presupuesto? Se mostrará un marcador en lugar del texto comprimido. El archivo original se conserva.',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No)
                if answer != QMessageBox.StandardButton.Yes:
                    return False
                opened = load_project(name, observed_presto88=observed_presto88,
                    native_economic=native_economic, skip_compressed_text=True, **pzh_options)
            budget, imported, revision = opened.budget, opened.imported, opened.revision
        except (StorageError, BC3ImportError, BudgetError, ArithmeticError, RecursionError) as exc:
            self._error(exc)
            return False
        finally:
            if progress is not None:
                progress.close()
        self.budget = budget
        self.path = None if imported else Path(name)
        self._file_revision = None if imported else (self.path.resolve(),revision)
        self.dirty = imported
        if hasattr(self, 'current_code'):
            self.current_code = budget.root_code
            self._navigation = []
        self._reset_history()
        self.refresh()
        if suffix == '.pzh':
            from .pzh_archive import import_summary
            summary, partial = import_summary(budget)
            message = QMessageBox(self)
            message.setWindowTitle('PZH · resultado de importación')
            message.setIcon(QMessageBox.Icon.Warning if partial else QMessageBox.Icon.Information)
            message.setText('Importación con datos pendientes de revisión' if partial else 'Archivo PZH importado')
            message.setInformativeText(summary)
            message.setDetailedText('\n'.join(budget.import_warnings))
            message.exec()
        self.statusBar().showMessage('Importado: guarda una copia de proyecto JSON' if imported else 'Proyecto abierto', 7000)
        return True

    def import_pzh_budget(self):
        if not self._confirm_discard():
            return
        name, _ = QFileDialog.getOpenFileName(self, 'Importar PZH · experimental',
                                             working_directory(), 'Presto PZH (*.pzh)')
        if name:
            self.load_path(name)

    def import_budget(self):
        if not self._confirm_discard():
            return
        name, _ = QFileDialog.getOpenFileName(self, 'Importar presupuesto BC3', working_directory(), 'BC3 (*.bc3)')
        if name:
            self.load_path(name)

    def undo(self):
        if self._undo:
            self._redo.append(self._capture_history_snapshot())
            self.budget = restore_snapshot(self._undo.pop())
            self._snapshot = capture_snapshot(self.budget)
            self.dirty = self._snapshot != self._saved_snapshot
            self.refresh()

    def redo(self):
        if self._redo:
            self._undo.append(self._capture_history_snapshot())
            self.budget = restore_snapshot(self._redo.pop())
            self._snapshot = capture_snapshot(self.budget)
            self.dirty = self._snapshot != self._saved_snapshot
            self.refresh()

    def _selected_table(self):
        for table in (self.measurements_table, self.relations_table, self.concepts_table):
            if table.isVisible() and table.currentRow() >= 0 and not table.isRowHidden(table.currentRow()):
                return table
        return None

    def edit_selected(self):
        table = self._selected_table()
        if table is None:
            self._error('Selecciona una fila en Mediciones, Conceptos o Relaciones.')
            return
        row = table.currentRow()
        try:
            if table is self.concepts_table:
                old = list(self.budget.concepts.values())[row]
                percentage = '%' in old.code and (self.budget.percentage_profile is not None or self.budget.project_metadata.get('engine') == 'native-v1')
                composed = any(r.parent_code == old.code for r in self.budget.relations)
                displayed_price = BudgetCalculator(self.budget).price(old.code) if percentage or composed else old.base_price
                dialog = ConceptDialog(self)
                for field, value in ((dialog.code, old.code), (dialog.unit, old.unit),
                                     (dialog.summary, old.summary), (dialog.nature, old.nature),
                                     (dialog.price, displayed_price)):
                    field.setText(str(value))
                dialog.measurement_decimals.setValue(-1 if old.measurement_decimals is None else old.measurement_decimals)
                dialog.code.setEnabled(False)
                dialog.price.setEnabled(not composed)
                if composed:
                    dialog.price.setToolTip('Precio vigente. Para cambiar un bloqueo utiliza Cálculos → Bloquear precio o Desbloquear precio.')
                if dialog.exec() != QDialog.DialogCode.Accepted:
                    return
                proposed = replace(dialog.get_concept(), text=old.text)
                from dataclasses import asdict
                self._execute('budget.concept.replace', data=asdict(proposed))
                return
            elif table is self.relations_table:
                old = self.budget.relations[row]
                if '%' in old.child_code:
                    raise BudgetError('La base porcentual es calculada; edita el tipo en Precios.')
                if (old.id in self.budget.bc3_measurements and self.budget.bc3_measurements[old.id].lines) or any(m.relation_id == old.id for m in self.budget.measurements):
                    raise BudgetError('Cantidad calculada desde mediciones: edita sus líneas.')
                value, ok = QInputDialog.getText(self, 'Cantidad manual',
                    'Cantidad (las mediciones, si existen, tienen prioridad)', text=str(old.quantity))
                if not ok:
                    return
                self._execute('budget.relation.edit', relation_id=old.id, field='quantity', value=value)
                return
            else:
                key, index = self._measurement_keys[row]
                if key != 'native':
                    self.edit_bc3_line(key, index)
                    return
                old = next(m for m in self.budget.measurements if m.id == index)
                dialog = MeasurementDialog(self)
                for field, value in ((dialog.comment, old.comment), (dialog.n, old.n_lines),
                                     (dialog.length, old.length), (dialog.width, old.width),
                                     (dialog.height, old.height), (dialog.formula, old.formula)):
                    field.setText('' if value is None else str(value))
                for name, check in dialog.annulled.items():
                    check.setChecked(name in old.annulled_dimensions)
                subtotal=self.budget.project_metadata.get('measurement_kind:' + old.id) in ('1','2')
                if subtotal:
                    dialog.setWindowTitle('Editar comentario del subtotal')
                    for widget in (dialog.n,dialog.length,dialog.width,dialog.height,dialog.formula,*dialog.annulled.values()):
                        widget.setEnabled(False)
                    dialog.layout().insertRow(0,QLabel('El subtotal se calcula desde las líneas anteriores. Puedes editar su comentario.'))
                if dialog.exec() != QDialog.DialogCode.Accepted:
                    return
                from dataclasses import asdict
                updated = replace(old,comment=dialog.comment.text()) if subtotal else replace(dialog.get_measurement(old.relation_id), id=old.id)
                changes = asdict(updated)
                from .commands import execute
                # The complete dialog is applied as one command and one history step.
                self._execute('budget.measurement.replace', data=changes)
                return
            self._changed()
        except (ValueError, ArithmeticError) as exc:
            self._error(exc)

    def edit_bc3_line(self, relation_id, index=None):
        record = self.budget.bc3_measurements[relation_id]
        old = record.lines[index] if index is not None else BC3MeasurementLine('', '', '1', '', '', '', None)
        dialog = QDialog(self)
        dialog.setWindowTitle('Medición BC3 · parcial a 2 decimales')
        form = QFormLayout(dialog)
        edits = []
        for label, value in zip(('Tipo: vacío, 1, 2 o 3', 'Comentario / fórmula', 'N', 'Longitud', 'Anchura', 'Altura'),
                               (old.kind, old.description, old.a, old.b, old.c, old.d)):
            edit = QLineEdit(value)
            form.addRow(label, edit)
            edits.append(edit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            updated = BC3MeasurementLine(*(e.text() if i<2 else input_number(e.text()) for i,e in enumerate(edits)), None)
            from dataclasses import asdict
            self._execute('budget.measurement.bc3.replace', relation_id=relation_id, data=asdict(updated), index=index)
        except (ValueError, ArithmeticError) as exc:
            self._error(exc)

    def delete_selected(self):
        table = self._selected_table()
        if table is None:
            return
        row = table.currentRow()
        if table is self.measurements_table:
            self._execute('budget.measurement.remove', keys=[self._measurement_keys[row]])
        elif table is self.concepts_table:
            self._execute('budget.concepts.remove', codes=[list(self.budget.concepts)[row]])
        else:
            self._execute('budget.relations.remove', relation_ids=[self.budget.relations[row].id])

    def save(self):
        if self.path is None:
            return self.save_as()
        try:
            import hashlib
            resolved = self.path.resolve()
            if self._file_revision is not None and self._file_revision[0] == resolved:
                if not self.path.is_file():
                    raise StorageError('El archivo abierto fue retirado. Usa Guardar como para elegir otro destino.')
                with self.path.open('rb') as stream:
                    current = stream.read(MAX_FILE_BYTES + 1)
                if hashlib.sha256(current).hexdigest() != self._file_revision[1]:
                    raise StorageError('El archivo cambió fuera de esta ventana. Guarda con otro nombre para conservar ambas versiones.')
            snapshot = dumps(self.budget)
            from .project_io import save_project
            save_project(self.budget, self.path)
            self._file_revision = (resolved,hashlib.sha256(snapshot.encode('utf-8')).hexdigest())
        except (StorageError, OSError) as exc:
            self._error(exc)
            return False
        self.dirty = False
        self._snapshot = capture_snapshot(self.budget)
        self._saved_snapshot = self._snapshot
        from .session_services import remember
        remember(self.path)
        self.refresh()
        self.statusBar().showMessage(f"Guardado: {self.path.name}", 5000)
        return True

    def save_as(self):
        name, _ = QFileDialog.getSaveFileName(
            self, "Guardar presupuesto", str(self.path or Path(working_directory()) / "presupuesto.openpresto.json"),
            FILE_FILTER
        )
        if not name:
            return False
        if not name.lower().endswith(".json"):
            name += ".openpresto.json"
        previous = self.path
        destination = Path(name)
        old_documents = [dict(row) for row in self.budget.documents]
        old_undo, old_redo = list(self._undo), list(self._redo)
        def rebase(budget):
            if previous is not None and previous.parent.resolve() != destination.parent.resolve():
                for row in budget.documents:
                    target = Path(row['path'])
                    if not target.is_absolute():
                        row['path'] = str((previous.parent / target).resolve())
            return budget
        try:
            rebase(self.budget)
            rebased_undo = [replace(capture_snapshot(rebase(restore_snapshot(snapshot))),context=getattr(snapshot,'context',None)) for snapshot in old_undo]
            rebased_redo = [replace(capture_snapshot(rebase(restore_snapshot(snapshot))),context=getattr(snapshot,'context',None)) for snapshot in old_redo]
        except (ValueError,OSError,ArithmeticError,RecursionError) as exc:
            self.budget.documents = old_documents
            self._error('No se pudieron trasladar las referencias documentales: ' + str(exc))
            return False
        self.path = destination
        if not self.save():
            self.path = previous
            self.budget.documents = old_documents
            return False
        self._undo = rebased_undo
        self._redo = rebased_redo
        return True

    def add_concept(self):
        dialog = ConceptDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        from dataclasses import asdict
        self._execute_model('budget.concept.add', dialog.get_concept)

    def add_relation(self):
        if len(self.budget.concepts) < 2:
            self._error("Añade al menos dos conceptos antes de crear relaciones.")
            return
        dialog = RelationDialog(list(self.budget.concepts), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        from dataclasses import asdict
        self._execute_model('budget.relation.add', dialog.get_relation)

    def add_measurement(self):
        if not self.budget.relations:
            self._error("Primero añade una relación.")
            return
        labels = [
            f"{r.id[:8]} · {r.parent_code} → {r.child_code}"
            for r in self.budget.relations
        ]
        selected, ok = QInputDialog.getItem(
            self, "Relación", "Selecciona la relación", labels, 0, False
        )
        if not ok:
            return
        relation_id = self.budget.relations[labels.index(selected)].id
        if relation_id in self.budget.bc3_measurements:
            self.edit_bc3_line(relation_id)
            return
        dialog = MeasurementDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        from dataclasses import asdict
        self._execute_model('budget.measurement.add', lambda: dialog.get_measurement(relation_id))

    def closeEvent(self, event):
        if self._confirm_discard():
            from .session_services import cleanup_recovery
            cleanup_recovery(self)
            if hasattr(self,'_recovery_timer'):
                self._recovery_timer.stop()
            event.accept()
        else:
            event.ignore()


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    window = BudgetEditor()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
