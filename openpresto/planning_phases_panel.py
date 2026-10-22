"""Desktop adapter for fixed phase quantities; no implicit date distribution."""
from PySide6.QtCore import QDate,Qt
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QLabel,QTabWidget,
    QTableWidget,QDialog,QFormLayout,QLineEdit,QComboBox,QDateEdit,QCheckBox,QListWidget,QListWidgetItem)
from .planning_panel import fill,buttons
from . import planning_phases as engine
from .reports import report_table


class PhasePlanningPanel(QWidget):
    def __init__(self,host):
        super().__init__(host);self.host=host;layout=QVBoxLayout(self);bar=QHBoxLayout()
        for text,callback in (('Copiar planificación PZH',lambda:host._execute('planning.phases.copy_pzh')),
                              ('Calendario y aprobación…',self.calendar),('Nueva actividad…',lambda:self.task(True)),('Editar actividad…',self.task)):
            b=QPushButton(text);b.clicked.connect(callback);bar.addWidget(b)
        layout.addLayout(bar)
        note=QLabel('Reparto explícito por fases, independiente del presupuesto y la certificación. Cambiar fechas no redistribuye cantidades. Las precedencias se conservan sin asumir su tipo. La aprobación se elige expresamente.');note.setWordWrap(True);layout.addWidget(note)
        self.status=QLabel();layout.addWidget(self.status);tabs=QTabWidget();self.activities=QTableWidget();self.phases=QTableWidget()
        tabs.addTab(self.activities,'Actividades y objetivo');tabs.addTab(self.phases,'Reparto editable');layout.addWidget(tabs)
        self.activities.cellDoubleClicked.connect(lambda *_:self.task());self.ids=[]
    def render(self):
        data=engine.validate(self.host.budget);self.ids=[r['relation_id'] for r in data['tasks']]
        self.status.setText('Aprobación sin definir' if data['approved'] is None else 'Fase aprobada: '+str(data['approved']))
        fill(self.activities,*report_table(self.host.budget,'plan_fases_actividades'));self.activities.setColumnHidden(0,True)
        fill(self.phases,*report_table(self.host.budget,'plan_fases_reparto'))
    def calendar(self):
        data=engine.validate(self.host.budget);d=QDialog(self);d.setWindowTitle('Calendario del plan por fases');layout=QVBoxLayout(d);grid=QTableWidget(0,1);grid.setHorizontalHeaderLabels(('Final de fase',));layout.addWidget(grid)
        approved=QComboBox();approved.addItem('Sin definir',None);approved.addItem('0',0)
        def append(value=None):
            i=grid.rowCount();grid.insertRow(i)
            day=QDateEdit(QDate.fromString(value,'yyyy-MM-dd') if value else QDate.currentDate());day.setCalendarPopup(True);day.setDisplayFormat('dd/MM/yyyy');grid.setCellWidget(i,0,day)
            approved.addItem(str(i+1),i+1)
        for value in data['end_dates']:append(value)
        b=QPushButton('Añadir fase');b.clicked.connect(lambda:append());layout.addWidget(b)
        approved.setCurrentIndex(max(0,approved.findData(data['approved'])))
        form=QFormLayout();layout.addLayout(form);form.addRow('Aprobada hasta',approved);buttons(d,form)
        if d.exec()==QDialog.DialogCode.Accepted:self.host._execute('planning.phases.configure',end_dates=[grid.cellWidget(i,0).date().toString('yyyy-MM-dd') for i in range(grid.rowCount())],approved=approved.currentData())
    def task(self,new=False):
        data=engine.validate(self.host.budget)
        selected=self.activities.currentRow();old=next((t for t in data['tasks'] if not new and 0<=selected<len(self.ids) and t['relation_id']==self.ids[selected]),None)
        if not new and old is None:self.host._error('Selecciona una actividad para editarla.');return
        d=QDialog(self);d.setWindowTitle('Actividad y reparto por fases');d.resize(760,680);layout=QVBoxLayout(d);form=QFormLayout();layout.addLayout(form);relation=QComboBox()
        for r in self.host.budget.relations:
            if new and any(t['relation_id']==r.id for t in data['tasks']):continue
            b=self.host.budget
            if b.concepts[r.parent_code].nature.casefold() in ('capitulo','capítulo') and (b.concepts[r.child_code].nature.casefold()=='partida' or b.project_metadata.get('certification_role:'+r.id)=='partida'):
                relation.addItem(r.parent_code+' → '+r.child_code,r.id)
        if not relation.count():self.host._error('Añade capítulos y partidas.');return
        if old:relation.setCurrentIndex(relation.findData(old['relation_id']));relation.setEnabled(False)
        form.addRow('Partida',relation);dates={}
        for key,label in (('start','Inicio previsto'),('end','Final previsto'),('actual_start','Inicio real'),('actual_end','Final real')):
            value=old[key] if old else None;w=QWidget();bar=QHBoxLayout(w);bar.setContentsMargins(0,0,0,0);known=QCheckBox('Definida');known.setChecked(value is not None)
            day=QDateEdit(QDate.fromString(value,'yyyy-MM-dd') if value else QDate.currentDate());day.setDisplayFormat('dd/MM/yyyy');day.setCalendarPopup(True);day.setEnabled(known.isChecked());known.toggled.connect(day.setEnabled);bar.addWidget(known);bar.addWidget(day);form.addRow(label,w);dates[key]=(known,day)
        quantity=QLineEdit(old['objective_quantity'] if old else '0');price=QLineEdit(old['objective_price'] if old else '0');form.addRow('Cantidad objetivo',quantity);form.addRow('Precio objetivo y plan',price)
        tabs=QTabWidget();layout.addWidget(tabs);grid=QTableWidget(len(data['end_dates']),1);grid.setHorizontalHeaderLabels(('Cantidad de fase',));grid.setVerticalHeaderLabels([str(i+1)+' · '+end for i,end in enumerate(data['end_dates'])])
        for i in range(len(data['end_dates'])):grid.setCellWidget(i,0,QLineEdit(old['phases'].get(str(i+1),'0') if old else '0'))
        tabs.addTab(grid,'Cantidades');previous=QListWidget()
        for t in data['tasks']:
            if old and t['relation_id']==old['relation_id']:continue
            r=self.host.budget._relation(t['relation_id']);item=QListWidgetItem(r.parent_code+' → '+r.child_code);item.setData(Qt.ItemDataRole.UserRole,r.id);item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable);item.setCheckState(Qt.CheckState.Checked if old and r.id in old['predecessors'] else Qt.CheckState.Unchecked);previous.addItem(item)
        tabs.addTab(previous,'Precedentes sin tipo');bottom=QFormLayout();layout.addLayout(bottom);buttons(d,bottom)
        if d.exec()==QDialog.DialogCode.Accepted:
            params={key:day.date().toString('yyyy-MM-dd') if known.isChecked() else None for key,(known,day) in dates.items()}
            self.host._execute('planning.phases.task.set',relation_id=relation.currentData(),objective_quantity=quantity.text().replace(',','.'),objective_price=price.text().replace(',','.'),
                phases={str(i+1):grid.cellWidget(i,0).text().replace(',','.') or '0' for i in range(grid.rowCount())},
                predecessors=[previous.item(i).data(Qt.ItemDataRole.UserRole) for i in range(previous.count()) if previous.item(i).checkState()==Qt.CheckState.Checked],**params)
