"""Daily site reports edited through atomic native commands."""
from PySide6.QtCore import QDate
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTableWidget,
    QDialog,QFormLayout,QLineEdit,QDateEdit,QComboBox)
from .planning_panel import fill,buttons
from .production import validate,eligible,report_rows,quantities,HEADERS


class ProductionPanel(QWidget):
    def __init__(self,host):
        super().__init__(host);self.host=host;layout=QVBoxLayout(self);bar=QHBoxLayout()
        for label,callback in (('Nuevo parte…',lambda:self.edit(True)),('Editar…',self.edit),('Confirmar',self.confirm),('Anular…',self.cancel),('Exportar partes…',self.export)):
            button=QPushButton(label);button.clicked.connect(callback);bar.addWidget(button)
        layout.addLayout(bar)
        note=QLabel('Producción diaria en unidades de cada partida. Solo los partes confirmados cuentan en el resumen. No modifica mediciones, certificaciones, facturas ni existencias. Para corregir un parte confirmado, anúlalo y crea otro.');note.setWordWrap(True);layout.addWidget(note)
        self.table=QTableWidget();layout.addWidget(self.table);self.table.cellDoubleClicked.connect(lambda *_:self.edit())
        bar=QHBoxLayout();bar.addWidget(QLabel('Producción confirmada hasta'))
        self.cut=QDateEdit(QDate.currentDate());self.cut.setCalendarPopup(True);self.cut.setDisplayFormat('dd/MM/yyyy');bar.addWidget(self.cut);bar.addStretch();layout.addLayout(bar)
        self.summary=QTableWidget();layout.addWidget(self.summary);self.cut.dateChanged.connect(self.render)
        note=QLabel('El resumen aplica el estado actual de los partes; no reconstruye estados históricos. Las cantidades se agrupan por relación, sin sumar unidades distintas ni aplicar otra vez el factor presupuestario.');note.setWordWrap(True);layout.addWidget(note);self.ids=[]
    def render(self,*_):
        rows=sorted(validate(self.host.budget),key=lambda r:(r['date'],r['reference']))
        self.ids=[r['id'] for r in rows for _ in r['lines']];fill(self.table,HEADERS,report_rows(self.host.budget))
        values=quantities(self.host.budget,self.cut.date().toString('yyyy-MM-dd'));rows=[]
        for rid,q in values.items():
            r=self.host.budget._relation(rid);c=self.host.budget.concepts[r.child_code]
            rows.append((rid,c.code,c.summary,c.unit,q))
        fill(self.summary,('Relación','Código','Resumen','Unidad','Cantidad confirmada'),rows)
    def selected(self):
        index=self.table.currentRow()
        if not 0<=index<len(self.ids):self.host._error('Selecciona un parte.');return None
        return next(r for r in validate(self.host.budget) if r['id']==self.ids[index])
    def edit(self,new=False):
        old=None if new else self.selected()
        if not new and old is None:return
        if old and old['status']!='draft':self.host._error('Solo se editan borradores.');return
        relations=eligible(self.host.budget)
        if not relations:self.host._error('Añade partidas dentro de un capítulo antes de crear partes.');return
        dialog=QDialog(self);dialog.setWindowTitle('Parte de obra');dialog.resize(760,520);layout=QVBoxLayout(dialog);form=QFormLayout();layout.addLayout(form)
        editors={}
        for key,label in (('reference','Referencia'),('team','Equipo'),('note','Nota')):
            editor=QLineEdit(old[key] if old else '');editor.setObjectName('production-'+key);editors[key]=editor;form.addRow(label,editor)
        day=QDateEdit(QDate.fromString(old['date'],'yyyy-MM-dd') if old else QDate.currentDate());day.setCalendarPopup(True);form.addRow('Fecha',day)
        table=QTableWidget(0,2);table.setObjectName('production-lines');table.setHorizontalHeaderLabels(('Partida / relación','Cantidad producida'));table.horizontalHeader().setStretchLastSection(True);table.setColumnWidth(0,510);layout.addWidget(table)
        def add(line=None):
            i=table.rowCount();table.insertRow(i);combo=QComboBox()
            for r in relations:
                c=self.host.budget.concepts[r.child_code];combo.addItem(c.code+' · '+c.summary+' ['+c.unit+'] · '+r.id,r.id)
            if line:combo.setCurrentIndex(combo.findData(line['relation_id']))
            quantity=QLineEdit(line['quantity'] if line else '1');table.setCellWidget(i,0,combo);table.setCellWidget(i,1,quantity)
        for line in old['lines'] if old else [None]:add(line)
        bar=QHBoxLayout();layout.addLayout(bar)
        plus=QPushButton('Añadir línea');plus.clicked.connect(lambda:add());bar.addWidget(plus)
        minus=QPushButton('Retirar línea');minus.clicked.connect(lambda:table.removeRow(table.currentRow()));bar.addWidget(minus)
        bottom=QFormLayout();layout.addLayout(bottom);buttons(dialog,bottom)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            lines=[dict(relation_id=table.cellWidget(i,0).currentData(),quantity=table.cellWidget(i,1).text().strip()) for i in range(table.rowCount())]
            self.host._execute('production.report.set',reference=editors['reference'].text(),date=day.date().toString('yyyy-MM-dd'),team=editors['team'].text(),note=editors['note'].text(),lines=lines,report_id=old['id'] if old else None)
    def confirm(self):
        row=self.selected()
        if row:self.host._execute('production.report.status',report_id=row['id'],status='posted')
    def cancel(self):
        row=self.selected()
        if row is None:return
        dialog=QDialog(self);dialog.setWindowTitle('Anular parte');form=QFormLayout(dialog);day=QDateEdit(QDate.currentDate());day.setCalendarPopup(True);form.addRow('Fecha',day)
        reason=QLineEdit();reason.setObjectName('production-cancellation-reason');form.addRow('Motivo obligatorio',reason);buttons(dialog,form)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.host._execute('production.report.status',report_id=row['id'],status='cancelled',cancellation_date=day.date().toString('yyyy-MM-dd'),reason=reason.text())
    def export(self):
        from .report_actions import export_report
        export_report(self.host,'partes_obra')
