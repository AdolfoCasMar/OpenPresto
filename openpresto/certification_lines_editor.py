"""Dialog edits a private copy; accepting commits one undoable transaction."""
from copy import deepcopy
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QDialogButtonBox, QLabel, QMessageBox)
from PySide6.QtCore import Qt, QSignalBlocker
from .ui_icons import icon
from .budget import BudgetMeasurement, BudgetError
from .certification_measurements import encode_line, totals


class CertificationLinesDialog(QDialog):
    def __init__(self, rid, rows, parent=None):
        super().__init__(parent)
        self.rid = rid
        self.rows = deepcopy(rows)
        self.setWindowTitle('Líneas de certificación del periodo')
        self.resize(1050, 550)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Tipo: 0 medición · 1 subtotal acumulado · 2 subtotal parcial. Fórmulas: A=N, B=longitud, C=anchura, D=altura.'))
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(('Tipo','Comentario','N','Longitud','Anchura','Altura','Fórmula','Parcial'))
        layout.addWidget(self.table)
        self.total = QLabel()
        layout.addWidget(self.total)
        controls = QHBoxLayout()
        for title, callback in (('Añadir', self.add), ('Eliminar', self.remove), ('Subir', lambda: self.move(-1)), ('Bajar', lambda: self.move(1))):
            button = QPushButton(title)
            button.setIcon(icon({'Añadir':'add', 'Eliminar':'delete', 'Subir':'up', 'Bajar':'down'}[title]))
            button.clicked.connect(callback)
            controls.addWidget(button)
        layout.addLayout(controls)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.commit)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.table.itemChanged.connect(self.calculate)
        self.render()

    def render(self):
        blocker = QSignalBlocker(self.table)
        self.table.setRowCount(len(self.rows))
        for i, row in enumerate(self.rows):
            m = row['measurement']
            values = [row['kind']] + [m.get(k) for k in ('comment','n_lines','length','width','height','formula')]
            for j, value in enumerate(values):
                self.table.setItem(i,j,QTableWidgetItem('' if value is None else str(value)))
        del blocker
        self.calculate()

    def read(self):
        result = []
        for i, old in enumerate(self.rows):
            texts = [self.table.item(i,j).text().strip() for j in range(7)]
            kind = int(texts[0])
            dims = [v.replace(',', '.') or None for v in texts[2:6]]
            line = BudgetMeasurement(self.rid, texts[1], dims[0] or '0', *dims[1:],
                id=old['measurement']['id'], formula=texts[6],
                annulled_dimensions=tuple(old['measurement'].get('annulled_dimensions', ())))
            result.append(encode_line(line, kind, old['source']))
        totals(result, self.rid)
        return result

    def calculate(self, *_):
        try:
            value, partials = totals(self.read(), self.rid)
            blocker = QSignalBlocker(self.table)
            for i, partial in enumerate(partials):
                item = QTableWidgetItem(str(partial))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(i,7,item)
            del blocker
            self.total.setText(f'Cantidad del periodo: {value}')
        except (ValueError, TypeError, ArithmeticError) as exc:
            self.total.setText(str(exc))

    def synchronize(self):
        try:
            self.rows = self.read()
            return True
        except (ValueError, TypeError, ArithmeticError) as exc:
            QMessageBox.warning(self, 'Línea inválida', str(exc))
            return False

    def add(self):
        if self.synchronize():
            self.rows.append(encode_line(BudgetMeasurement(self.rid)))
            self.render()
            self.table.setCurrentCell(len(self.rows)-1,1)

    def remove(self):
        index = self.table.currentRow()
        if index >= 0 and self.synchronize():
            self.rows.pop(index)
            self.render()

    def move(self, step):
        index = self.table.currentRow()
        target = index + step
        if 0 <= target < len(self.rows) and self.synchronize():
            self.rows[index], self.rows[target] = self.rows[target], self.rows[index]
            self.render()
            self.table.setCurrentCell(target,1)

    def commit(self):
        if self.synchronize():
            self.accept()
