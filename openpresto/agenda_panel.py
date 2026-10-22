"""Explicit calendar notes and holiday review."""
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QLabel,QTableWidget,QDialog,QFormLayout,QLineEdit,QComboBox
from .planning_panel import fill,buttons
from . import agenda


class AgendaPanel(QWidget):
    def __init__(self,host):
        super().__init__(host);self.host=host;box=QVBoxLayout(self);bar=QHBoxLayout();box.addLayout(bar)
        for title,callback in (('Nuevo día…',lambda:self.edit(True)),('Editar día…',self.edit),('Copiar agenda PZH',lambda:host._execute('agenda.copy_pzh')),('Añadir festivos al plan',lambda:host._execute('agenda.holidays.add'))):
            button=QPushButton(title);button.clicked.connect(callback);bar.addWidget(button)
        note=QLabel('Las notas y los festivos no cambian las fechas de las actividades. Añadir festivos conserva el calendario existente y puede modificar su reparto. Los importes de origen no son movimientos de tesorería.');note.setWordWrap(True);box.addWidget(note);self.table=QTableWidget();box.addWidget(self.table);self.rows=[];self.table.cellDoubleClicked.connect(lambda *_:self.edit())
    def render(self):self.rows=agenda.report_rows(self.host.budget);fill(self.table,agenda.HEADERS,self.rows)
    def edit(self,new=False):
        i=self.table.currentRow();old=None if new else next((r for r in agenda.validate(self.host.budget) if 0<=i<len(self.rows) and r['date']==self.rows[i][0]),None)
        if not new and old is None:self.host._error('Selecciona un día de la agenda.');return
        dialog=QDialog(self);dialog.setWindowTitle('Día de agenda');form=QFormLayout(dialog);date=QLineEdit(old['date'] if old else '');date.setObjectName('agenda-date');date.setReadOnly(old is not None);note=QLineEdit(old['note'] if old else '');note.setObjectName('agenda-note');holiday=QComboBox();holiday.setObjectName('agenda-holiday')
        for title,value in (('Sin indicar',None),('Festivo',True),('No festivo',False)):holiday.addItem(title,value)
        holiday.setCurrentIndex(0 if old is None or old['holiday'] is None else 1 if old['holiday'] else 2)
        for label,widget in (('Fecha (AAAA-MM-DD)',date),('Festivo',holiday),('Nota',note)):form.addRow(label,widget)
        buttons(dialog,form)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.host._execute('agenda.day.set',date=date.text().strip(),holiday=holiday.currentData(),note=note.text())
