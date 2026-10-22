"""Qt editing of explicit certification periods, without an invented agenda."""
from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QTableWidget, QTableWidgetItem, QAbstractItemView,
    QDialog, QFormLayout, QLineEdit, QPlainTextEdit, QSpinBox, QDialogButtonBox)

from .ui_icons import icon
from .budget import BudgetError
from .certifications import CertificationAtOrigin
from .certification_phases import CertificationSchedule, project_phases


class PhaseScheduleDialog(QDialog):
    def __init__(self, schedule, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Calendario de certificaciones')
        form = QFormLayout(self)
        self.start = QLineEdit((schedule.start_date or '') if schedule else '')
        self.start.setPlaceholderText('YYYY-MM-DD · vacío si el inicio es desconocido')
        self.ends = QPlainTextEdit('\n'.join(schedule.end_dates) if schedule else '')
        self.ends.setPlaceholderText('Una fecha final YYYY-MM-DD por línea, en orden creciente')
        self.approved = QSpinBox()
        self.approved.setRange(0, 9999)
        self.approved.setValue(schedule.current_phase if schedule else 0)
        self.approved.setSpecialValueText('Ninguna aprobada')
        form.addRow('Inicio de obra', self.start)
        form.addRow('Fechas finales', self.ends)
        form.addRow('Última fase aprobada', self.approved)
        form.addRow(QLabel('Con cantidades registradas solo se pueden añadir fechas al final.\nIntroducir cantidad por fase sustituye el dato a origen de esa relación.'))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def schedule(self):
        return CertificationSchedule(self.start.text().strip() or None,
            tuple(line.strip() for line in self.ends.toPlainText().splitlines() if line.strip()),
            self.approved.value())


class CertificationPhasePanel(QWidget):
    def __init__(self, host):
        super().__init__(host)
        self.host = host
        self._rendering = False
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        configure = QPushButton('Calendario y aprobación…')
        configure.setIcon(icon('calendar'))
        configure.clicked.connect(self.configure)
        controls.addWidget(configure)
        controls.addWidget(QLabel('Editar periodo:'))
        self.phase = QComboBox()
        self.phase.currentIndexChanged.connect(lambda _: self.render())
        controls.addWidget(self.phase)
        lines = QPushButton('Líneas del periodo…')
        lines.setIcon(icon('measure'))
        lines.clicked.connect(self.edit_lines)
        controls.addWidget(lines)
        layout.addLayout(controls)
        self.info = QLabel('Configura el inicio y las fechas de certificación.')
        self.info.setWordWrap(True)
        layout.addWidget(self.info)
        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(('Capítulo','Partida','CanPres','Cantidad del periodo',
            'Cantidad aprobada','Precio certificado','Anterior a última aprobada','Acumulado aprobado','Última fase aprobada','Importe del periodo editado'))
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed)
        self.table.itemChanged.connect(self.edit_cell)
        layout.addWidget(self.table)
        self.ids = []

    def edit_lines(self):
        from .certification_measurements import find, replace, encode_line
        from .certification_lines_editor import CertificationLinesDialog
        from .budget import BudgetMeasurement
        index = self.table.currentRow()
        number = self.phase.currentData()
        if index < 0 or number is None:
            self.info.setText('Selecciona una partida para editar sus líneas del periodo.')
            return
        rid = self.ids[index]
        from .certification_editing import editable_lines
        rows = editable_lines(self.host.budget, number, rid)
        dialog = CertificationLinesDialog(rid, rows, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.host._execute('certification.lines.replace', phase=number, relation_id=rid, rows=dialog.rows)

    def configure(self):
        old = self.host.budget.certification_schedule
        dialog = PhaseScheduleDialog(old, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.host._execute('certification.schedule.set', start_date=dialog.start.text().strip() or None,
            end_dates=[line.strip() for line in dialog.ends.toPlainText().splitlines() if line.strip()],
            current_phase=dialog.approved.value())

    def render(self):
        if self._rendering:
            return
        self._rendering = True
        blockers = [QSignalBlocker(self.phase), QSignalBlocker(self.table)]
        try:
            budget = self.host.budget
            selected = self.phase.currentData()
            self.phase.clear()
            view = project_phases(budget)
            self.ids = []
            self.table.setRowCount(0)
            if view is None:
                self.info.setText('Configura el inicio y las fechas de certificación. No hay un calendario asignado.')
                return
            schedule = view.schedule
            for number, end in enumerate(schedule.end_dates, 1):
                self.phase.addItem(f'{number} · {end}', number)
            chosen = self.phase.findData(selected)
            self.phase.setCurrentIndex(chosen if chosen >= 0 else 0)
            selected = self.phase.currentData()
            self.info.setText(f'Editando periodo {selected}. Última fase aprobada: {schedule.current_phase}. La cantidad y el importe del periodo editado están separados de los acumulados aprobados. El precio certificado no cambia el presupuesto.' +
                (' Inicio de la primera fase desconocido.' if schedule.start_date is None else ''))
            if selected is None:
                return
            from .certification_editing import period_rows
            rendered = period_rows(budget, selected)
            self.ids = [rid for rid,values in rendered]
            self.table.setRowCount(len(self.ids))
            from .certification_measurements import groups
            detailed_ids = {g['relation'] for g in groups(budget) if g['phase'] == selected}
            for row, rid in enumerate(self.ids):
                values = rendered[row][1]
                for col, value in enumerate(values):
                    item = QTableWidgetItem(str(value))
                    detailed = rid in detailed_ids
                    if col not in (3, 5) or (col == 3 and detailed):
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    if col == 3 and detailed:
                        item.setToolTip('Cantidad calculada: edita las líneas del periodo.')
                    if rid in budget.certified_quantities:
                        item.setToolTip('Introducir una cantidad aquí cambia a fases y sustituye el dato a origen. Deshacer recupera el valor anterior.')
                    self.table.setItem(row, col, item)
        finally:
            blockers.clear()
            self._rendering = False

    def edit_cell(self, item):
        if self._rendering or item.column() not in (3, 5):
            return
        number = self.phase.currentData()
        if number is None:
            return
        rid = self.ids[item.row()]
        text = item.text().strip()
        if item.column() == 5:
            self.host._execute('certification.price.set', relation_id=rid, value=text.replace(',', '.') or None)
        else:
            self.host._execute('certification.phase.quantity.set', phase=number,
                relation_id=rid, value=text.replace(',', '.') or None)
