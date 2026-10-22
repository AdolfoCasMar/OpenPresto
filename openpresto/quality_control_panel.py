"""Checklist editor and review actions through atomic application commands."""
from PySide6.QtCore import QDate
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTableWidget,
 QDialog,QFormLayout,QLineEdit,QDateEdit,QComboBox,QTabWidget)
from .planning_panel import fill,buttons
from .production import eligible
from . import quality_control as quality


class QualityControlPanel(QWidget):
    def __init__(self,host):
        super().__init__(host);self.host=host;layout=QVBoxLayout(self);bar=QHBoxLayout()
        for label,callback in (('Nuevo control…',lambda:self.edit(True)),('Editar borrador…',self.edit),('Revisar…',lambda:self.finish('reviewed')),('Anular…',lambda:self.finish('cancelled')),('Seguimiento…',self.track),('Exportar vista…',self.export)):
            button=QPushButton(label);button.clicked.connect(callback);bar.addWidget(button)
        layout.addLayout(bar)
        note=QLabel('Comprobaciones y criterios definidos por el usuario. La revisión exige responsable, resultados completos y observación en cada «No cumple». El resultado es conforme solo si todas las comprobaciones aplicables cumplen. Los controles revisados quedan bloqueados; para corregirlos, anula y crea otro.');note.setWordWrap(True);layout.addWidget(note)
        self.status=QLabel();layout.addWidget(self.status);self.tabs=QTabWidget();layout.addWidget(self.tabs);self.table=QTableWidget();self.details=QTableWidget();self.tabs.addTab(self.table,'Controles');self.tabs.addTab(self.details,'Todas las comprobaciones')
        self.table.cellDoubleClicked.connect(lambda *_:self.edit());self.ids=[]
    def render(self):
        rows=quality.entries(self.host.budget);self.ids=[r['id'] for r in rows]
        fill(self.table,quality.HEADERS,quality.report_rows(self.host.budget));fill(self.details,quality.DETAIL_HEADERS,quality.detail_rows(self.host.budget))
        self.status.setText(f"Borradores: {sum(r['status']=='draft' for r in rows)} · Conformes revisados: {sum(quality.verdict(r)=='Conforme' for r in rows)} · No conformes revisados: {sum(quality.verdict(r)=='No conforme' for r in rows)} · Anulados: {sum(r['status']=='cancelled' for r in rows)}")
    def selected(self):
        i=self.table.currentRow()
        if self.tabs.currentIndex()!=0 or not 0<=i<len(self.ids):self.host._error('Selecciona un control en la pestaña Controles.');return None
        return next(r for r in quality.validate(self.host.budget) if r['id']==self.ids[i])
    def edit(self,new=False):
        old=None if new else self.selected()
        if not new and old is None:return
        if old and old['status']!='draft':self.host._error('Solo se editan borradores.');return
        dialog=QDialog(self);dialog.setWindowTitle('Control de calidad');dialog.resize(850,600);layout=QVBoxLayout(dialog);form=QFormLayout();layout.addLayout(form);editors={}
        for key,label in (('reference','Referencia'),('title','Control'),('inspector','Responsable de revisión'),('note','Nota')):
            editor=QLineEdit(old[key] if old else '');editor.setObjectName('quality-'+key);editors[key]=editor;form.addRow(label,editor)
        day=QDateEdit(QDate.fromString(old['date'],'yyyy-MM-dd') if old else QDate.currentDate());day.setCalendarPopup(True);day.setDisplayFormat('dd/MM/yyyy');form.addRow('Fecha del control',day)
        target=QComboBox();target.setObjectName('quality-relation');target.addItem('General / sin partida',None)
        for r in eligible(self.host.budget):
            c=self.host.budget.concepts[r.child_code];target.addItem(c.code+' · '+c.summary+' · '+r.id,r.id)
        if old and old['relation_id']:target.setCurrentIndex(target.findData(old['relation_id']))
        form.addRow('Partida',target)
        table=QTableWidget(0,3);table.setObjectName('quality-checks');table.setHorizontalHeaderLabels(('Comprobación / criterio','Resultado','Observación'));table.setColumnWidth(0,340);table.setColumnWidth(1,140);table.horizontalHeader().setStretchLastSection(True);layout.addWidget(table)
        def add(check=None):
            i=table.rowCount();table.insertRow(i);criterion=QLineEdit(check['criterion'] if check else '');result=QComboBox()
            for key,label in quality.RESULTS.items():result.addItem(label,key)
            if check:result.setCurrentIndex(result.findData(check['result']))
            note=QLineEdit(check['note'] if check else '');table.setCellWidget(i,0,criterion);table.setCellWidget(i,1,result);table.setCellWidget(i,2,note)
        for check in old['checks'] if old else [None]:add(check)
        bar=QHBoxLayout();layout.addLayout(bar);plus=QPushButton('Añadir comprobación');plus.clicked.connect(lambda:add());bar.addWidget(plus);minus=QPushButton('Retirar comprobación');minus.clicked.connect(lambda:table.removeRow(table.currentRow()));bar.addWidget(minus)
        bottom=QFormLayout();layout.addLayout(bottom);buttons(dialog,bottom)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            checks=[dict(criterion=table.cellWidget(i,0).text(),result=table.cellWidget(i,1).currentData(),note=table.cellWidget(i,2).text()) for i in range(table.rowCount())]
            self.host._execute('quality.inspection.set',reference=editors['reference'].text(),date=day.date().toString('yyyy-MM-dd'),title=editors['title'].text(),inspector=editors['inspector'].text(),note=editors['note'].text(),relation_id=target.currentData(),checks=checks,inspection_id=old['id'] if old else None)
    def finish(self,status):
        old=self.selected()
        if old is None:return
        if status=='reviewed' and old['status']!='draft' or old['status']=='cancelled':self.host._error('Cambio de estado no permitido.');return
        dialog=QDialog(self);dialog.setWindowTitle('Revisar control' if status=='reviewed' else 'Anular control');form=QFormLayout(dialog)
        day=QDateEdit(max(QDate.currentDate(),QDate.fromString(old['reviewed_on'] or old['date'],'yyyy-MM-dd')));day.setCalendarPopup(True);day.setDisplayFormat('dd/MM/yyyy');form.addRow('Fecha',day);reason=QLineEdit();reason.setObjectName('quality-cancellation-reason')
        if status=='cancelled':form.addRow('Motivo obligatorio',reason)
        buttons(dialog,form)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.host._execute('quality.inspection.status',inspection_id=old['id'],status=status,date=day.date().toString('yyyy-MM-dd'),reason=reason.text())
    def export(self):
        from .report_actions import export_report
        export_report(self.host,'calidad_comprobaciones' if self.tabs.currentIndex() else 'calidad_controles')

    def track(self):
        manager=self.host.panels['gestion'][1];manager.tabs.setCurrentWidget(manager.nonconformities)
