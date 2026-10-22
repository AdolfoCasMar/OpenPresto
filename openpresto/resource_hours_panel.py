"""Qt adapter for explicit daily labour and equipment-hour entries."""
from PySide6.QtCore import QDate
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTableWidget,
    QDialog,QFormLayout,QLineEdit,QDateEdit,QComboBox,QTabWidget)
from .planning_panel import fill,buttons
from . import resource_hours as hours
from .production import eligible


class ResourceHoursPanel(QWidget):
    def __init__(self,host):
        super().__init__(host);self.host=host;layout=QVBoxLayout(self);bar=QHBoxLayout()
        for label,callback in (('Registrar horas…',lambda:self.edit(True)),('Editar…',self.edit),('Confirmar',self.confirm),('Anular…',self.cancel),('Exportar vista…',self.export)):
            button=QPushButton(label);button.clicked.connect(callback);bar.addWidget(button)
        layout.addLayout(bar)
        note=QLabel('Horas de mano de obra y maquinaria con unidad h. La tarifa se introduce y queda guardada en cada registro. El coste se redondea a dos decimales por registro. No genera nóminas, facturas, pagos ni movimientos de existencias.');note.setWordWrap(True);layout.addWidget(note)
        bar=QHBoxLayout();bar.addWidget(QLabel('Resúmenes hasta'))
        self.cut=QDateEdit(QDate.currentDate());self.cut.setCalendarPopup(True);self.cut.setDisplayFormat('dd/MM/yyyy');bar.addWidget(self.cut);bar.addStretch();layout.addLayout(bar)
        self.status=QLabel();layout.addWidget(self.status);self.tabs=QTabWidget();layout.addWidget(self.tabs)
        self.table=QTableWidget();self.resources=QTableWidget();self.work=QTableWidget()
        for table,label in ((self.table,'Registros'),(self.resources,'Por recurso'),(self.work,'Por partida')):self.tabs.addTab(table,label)
        note=QLabel('Los resúmenes incluyen solo registros actualmente confirmados hasta la fecha de corte. Registros muestra todos los estados y fechas. Las horas pueden ser acumuladas de una cuadrilla; no representan necesariamente la jornada de una persona. Los registros sin partida se muestran por separado.');note.setWordWrap(True);layout.addWidget(note)
        self.table.cellDoubleClicked.connect(lambda *_:self.edit());self.cut.dateChanged.connect(self.render);self.ids=[]
    def render(self,*_):
        self.ids=[r['id'] for r in hours.entries(self.host.budget)]
        fill(self.table,hours.HEADERS,hours.report_rows(self.host.budget));view=hours.snapshot(self.host.budget,self.cut.date().toString('yyyy-MM-dd'))
        fill(self.resources,hours.RESOURCE_HEADERS,view['resources']);fill(self.work,hours.WORK_HEADERS,view['work_items'])
        self.status.setText(f"Registros confirmados al corte: {view['count']} · Coste registrado: {view['total']} · Sin asignar a partida: {view['unassigned']}. Estados actuales; no es una reconstrucción histórica.")
    def selected(self):
        i=self.table.currentRow()
        if self.tabs.currentIndex()!=0 or not 0<=i<len(self.ids):self.host._error('Selecciona un registro en la pestaña Registros.');return None
        return next(r for r in hours.validate(self.host.budget) if r['id']==self.ids[i])
    def edit(self,new=False):
        old=None if new else self.selected()
        if not new and old is None:return
        if old and old['status']!='draft':self.host._error('Solo se editan borradores. Anula el registro para corregirlo.');return
        available=hours.resources(self.host.budget)
        if not available:self.host._error('Añade conceptos de mano de obra o maquinaria con unidad h.');return
        dialog=QDialog(self);dialog.setWindowTitle('Horas y equipos');dialog.resize(650,400);form=QFormLayout(dialog);editors={}
        for key,label in (('reference','Referencia'),('team','Equipo / cuadrilla'),('hours','Horas acumuladas'),('rate','Tarifa por hora'),('note','Nota')):
            editor=QLineEdit(old[key] if old else ('1' if key=='hours' else '0' if key=='rate' else ''));editor.setObjectName('hours-'+key);editors[key]=editor;form.addRow(label,editor)
        day=QDateEdit(QDate.fromString(old['date'],'yyyy-MM-dd') if old else QDate.currentDate());day.setCalendarPopup(True);day.setDisplayFormat('dd/MM/yyyy');day.setObjectName('hours-date');form.addRow('Fecha',day)
        resource=QComboBox();resource.setObjectName('hours-resource')
        for c in available:resource.addItem(c.code+' · '+c.summary,c.code)
        if old:resource.setCurrentIndex(resource.findData(old['resource_code']))
        form.addRow('Recurso en horas',resource)
        target=QComboBox();target.setObjectName('hours-relation');target.addItem('Sin asignar',None)
        for r in eligible(self.host.budget):
            c=self.host.budget.concepts[r.child_code];target.addItem(c.code+' · '+c.summary+' · '+r.id,r.id)
        if old and old['relation_id']:target.setCurrentIndex(target.findData(old['relation_id']))
        form.addRow('Partida de destino',target)
        hint=QLabel('Introduce decimales con punto. Tarifa explícita por hora; no se actualiza al cambiar los precios del presupuesto.');hint.setWordWrap(True);form.addRow(hint);buttons(dialog,form)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            self.host._execute('resource.hours.set',reference=editors['reference'].text(),date=day.date().toString('yyyy-MM-dd'),team=editors['team'].text(),resource_code=resource.currentData(),hours=editors['hours'].text().strip(),rate=editors['rate'].text().strip(),relation_id=target.currentData(),note=editors['note'].text(),entry_id=old['id'] if old else None)
    def confirm(self):
        row=self.selected()
        if row:self.host._execute('resource.hours.status',entry_id=row['id'],status='posted')
    def cancel(self):
        row=self.selected()
        if row is None:return
        dialog=QDialog(self);dialog.setWindowTitle('Anular horas');form=QFormLayout(dialog);day=QDateEdit(QDate.currentDate());day.setCalendarPopup(True);form.addRow('Fecha',day)
        reason=QLineEdit();reason.setObjectName('hours-cancellation-reason');form.addRow('Motivo obligatorio',reason);buttons(dialog,form)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.host._execute('resource.hours.status',entry_id=row['id'],status='cancelled',cancellation_date=day.date().toString('yyyy-MM-dd'),reason=reason.text())
    def export(self):
        from .report_actions import export_report
        kind='horas_recursos'
        if self.tabs.currentIndex():kind+=':'+self.cut.date().toString('yyyy-MM-dd')+':'+('recursos' if self.tabs.currentIndex()==1 else 'partidas')
        export_report(self.host,kind)
