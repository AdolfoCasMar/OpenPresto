"""Planning forms and tables; all changes dispatch native commands."""
from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QLabel,QTabWidget,QTableWidget,
    QTableWidgetItem,QDialog,QFormLayout,QDialogButtonBox,QComboBox,QDateEdit,QLineEdit,QListWidget,QListWidgetItem,QCheckBox,QAbstractItemView,QGraphicsView,QGraphicsScene)
from .ui_icons import icon
from PySide6.QtGui import QColor,QPen,QBrush
from datetime import timedelta
from .planning import iso
from .planning import validate, task_rows, resources
from .budget import BudgetError


def fill(table, headers, rows):
    table.setColumnCount(len(headers));table.setHorizontalHeaderLabels(headers);table.setRowCount(len(rows))
    for i,row in enumerate(rows):
        for j,value in enumerate(row):
            item=QTableWidgetItem(str(value));item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable);table.setItem(i,j,item)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.resizeColumnsToContents()
    for column in range(table.columnCount()):table.setColumnWidth(column,min(420,max(90,table.columnWidth(column)+12)))
    table.horizontalHeader().setStretchLastSection(True)


def buttons(dialog, form):
    box=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
    box.accepted.connect(dialog.accept);box.rejected.connect(dialog.reject);form.addRow(box)


class PlanningPanel(QWidget):
    def __init__(self,host):
        super().__init__(host);self.host=host
        layout=QVBoxLayout(self);bar=QHBoxLayout()
        for text,symbol,callback in (('Calendario laboral…','calendar',self.calendar),('Programar partida…','add',lambda:self.task(True)),('Retirar actividad','delete',self.remove)):
            b=QPushButton(text);b.setIcon(icon(symbol));b.clicked.connect(callback);bar.addWidget(b)
        layout.addLayout(bar)
        note=QLabel('Plan creado en OpenPresto. La planificación original importada se consulta en Origen PZH. Independiente del presupuesto y la certificación. Fechas inclusivas; reparto según días laborables. Selecciona una actividad para editarla.');note.setWordWrap(True);layout.addWidget(note)
        self.tabs=QTabWidget();self.activities=QTableWidget();self.distribution=QTableWidget();self.resource_table=QTableWidget()
        for widget,label in ((self.activities,'Actividades'),(self.distribution,'Reparto mensual'),(self.resource_table,'Recursos')):self.tabs.addTab(widget,label)
        self.chart=QGraphicsView();self.scene=QGraphicsScene(self.chart);self.chart.setScene(self.scene);self.tabs.addTab(self.chart,'Diagrama temporal')
        layout.addWidget(self.tabs)
        self.activities.cellDoubleClicked.connect(lambda *_:self.task())
        from .operations_panels import AdvancedPlanningPanel, SourcePanel
        self.advanced=AdvancedPlanningPanel(host);self.tabs.addTab(self.advanced,'Ruta crítica y objetivo')
        self.source=SourcePanel(host,[('pzh_plan','Actividades'),('pzh_phases','Fases'),('pzh_edges','Precedencias'),('pzh_unresolved','Referencias sin resolver')]);self.tabs.addTab(self.source,'Origen PZH')
        from .planning_phases_panel import PhasePlanningPanel
        self.phase_plan=PhasePlanningPanel(host);self.tabs.addTab(self.phase_plan,'Plan por fases editable')
        from .earned_value_panel import EarnedValuePanel
        self.earned_value=EarnedValuePanel(host);self.tabs.addTab(self.earned_value,'Valor ganado y curvas S')
        from .agenda_panel import AgendaPanel
        self.agenda=AgendaPanel(host);self.tabs.addTab(self.agenda,'Agenda y festivos')
        self.ids=[]

    def render(self):
        self.agenda.render()
        self.advanced.render();self.source.render();self.phase_plan.render();self.earned_value.render()
        data=validate(self.host.budget);self.ids=[t['relation_id'] for t in data['tasks']]
        fill(self.activities,('Capítulo','Partida','Inicio','Final','Cantidad objetivo','Precedentes'),[
            (self.host.budget._relation(t['relation_id']).parent_code,self.host.budget._relation(t['relation_id']).child_code,t['start'],t['end'],t['quantity'],', '.join(self.host.budget._relation(r).child_code for r in t['predecessors'])) for t in data['tasks']])
        fill(self.distribution,('Capítulo','Partida','Inicio','Final','Mes','Días laborales','Cantidad','Importe estimado'),task_rows(self.host.budget))
        fill(self.resource_table,('Mes','Recurso','Unidad','Cantidad'),resources(self.host.budget))
        self.render_chart(data['tasks'])

    def render_chart(self,tasks):
        self.scene.clear();self.scene.setBackgroundBrush(QColor('#ffffff'))
        if not tasks:
            text=self.scene.addText('Programa partidas para ver el diagrama temporal.');text.setDefaultTextColor(QColor('#28313c'));return
        first=min(iso(t['start']) for t in tasks);last=max(iso(t['end']) for t in tasks);span=(last-first).days+1
        width=800;scale=width/span;left=170;positions={}
        for n in range(0,span,max(1,span//10)):
            x=left+n*scale;self.scene.addLine(x,28,x,45+len(tasks)*34,QPen(QColor('#d6dce5')))
            label=self.scene.addText((first+timedelta(days=n)).isoformat());label.setDefaultTextColor(QColor('#536477'));label.setPos(x,0)
        for i,task in enumerate(tasks):
            relation=self.host.budget._relation(task['relation_id']);y=40+i*34
            text=self.scene.addText(relation.child_code);text.setDefaultTextColor(QColor('#28313c'));text.setPos(0,y-4)
            x=left+(iso(task['start'])-first).days*scale;length=max(3,((iso(task['end'])-iso(task['start'])).days+1)*scale)
            bar=self.scene.addRect(x,y,length,18,QPen(QColor('#288c99')),QBrush(QColor('#57b7c3')))
            bar.setToolTip(relation.child_code+' · '+task['start']+' → '+task['end']+' · '+task['quantity'])
            positions[task['relation_id']]=(x,x+length,y+9)
        for task in tasks:
            for previous in task['predecessors']:
                a=positions[previous];b=positions[task['relation_id']]
                pen=QPen(QColor('#478c86'));self.scene.addLine(a[1],a[2],a[1]+5,a[2],pen);self.scene.addLine(a[1]+5,a[2],a[1]+5,b[2],pen);self.scene.addLine(a[1]+5,b[2],b[0],b[2],pen)
        self.scene.setSceneRect(0,0,left+width+100,75+len(tasks)*34)

    def calendar(self):
        data=validate(self.host.budget);d=QDialog(self);d.setWindowTitle('Calendario laboral del plan');form=QFormLayout(d)
        days=[]
        for i,name in enumerate(('Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo')):
            check=QCheckBox(name);check.setChecked(i in data['weekdays']);days.append(check);form.addRow(check)
        holidays=QLineEdit(', '.join(data['holidays']));holidays.setPlaceholderText('YYYY-MM-DD, YYYY-MM-DD');form.addRow('Festivos',holidays);buttons(d,form)
        if d.exec()==QDialog.DialogCode.Accepted:self.host._execute('planning.calendar.set',weekdays=[i for i,c in enumerate(days) if c.isChecked()],holidays=[s.strip() for s in holidays.text().split(',') if s.strip()])

    def task(self,new=False):
        data=validate(self.host.budget);index=self.activities.currentRow();old=data['tasks'][index] if not new and 0<=index<len(data['tasks']) else None
        d=QDialog(self);d.setWindowTitle('Actividad de planificación');form=QFormLayout(d);relation=QComboBox()
        budget=self.host.budget
        for r in budget.relations:
            parent=budget.concepts[r.parent_code];child=budget.concepts[r.child_code]
            if parent.nature.casefold() in ('capitulo','capítulo') and (child.nature.casefold()=='partida' or budget.project_metadata.get('certification_role:'+r.id)=='partida'):
                relation.addItem(r.parent_code+' → '+r.child_code+' · '+child.summary,r.id)
        if old:relation.setCurrentIndex(relation.findData(old['relation_id']));relation.setEnabled(False)
        elif self.host.selected_relation:relation.setCurrentIndex(max(0,relation.findData(self.host.selected_relation)))
        if relation.count()==0:self.host._error('Define capítulos y partidas antes de planificar.');return
        start=QDateEdit(QDate.fromString(old['start'],'yyyy-MM-dd') if old else QDate.currentDate());end=QDateEdit(QDate.fromString(old['end'],'yyyy-MM-dd') if old else QDate.currentDate());start.setCalendarPopup(True);end.setCalendarPopup(True)
        start.setDisplayFormat('yyyy-MM-dd');end.setDisplayFormat('yyyy-MM-dd')
        quantity=QLineEdit(old['quantity'] if old else str(budget.relation_quantity(relation.currentData())))
        if not old:relation.currentIndexChanged.connect(lambda _:quantity.setText(str(budget.relation_quantity(relation.currentData()))))
        previous=QListWidget()
        for t in data['tasks']:
            if old and t['relation_id']==old['relation_id']:continue
            item=QListWidgetItem(budget._relation(t['relation_id']).child_code+' · '+t['end']);item.setData(Qt.ItemDataRole.UserRole,t['relation_id']);item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable);item.setCheckState(Qt.CheckState.Checked if old and t['relation_id'] in old['predecessors'] else Qt.CheckState.Unchecked);previous.addItem(item)
        for label,widget in (('Partida',relation),('Inicio',start),('Final',end),('Cantidad objetivo',quantity),('Debe terminar antes',previous)):form.addRow(label,widget)
        buttons(d,form)
        if d.exec()==QDialog.DialogCode.Accepted:self.host._execute('planning.task.set',relation_id=relation.currentData(),start=start.date().toString('yyyy-MM-dd'),end=end.date().toString('yyyy-MM-dd'),quantity=quantity.text().replace(',','.'),predecessors=[previous.item(i).data(Qt.ItemDataRole.UserRole) for i in range(previous.count()) if previous.item(i).checkState()==Qt.CheckState.Checked])

    def remove(self):
        index=self.activities.currentRow()
        if 0<=index<len(self.ids):self.host._execute('planning.task.remove',relation_id=self.ids[index])
