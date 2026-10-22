"""Site issue forms and filters; all mutations dispatch native commands."""
from PySide6.QtCore import QDate
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTableWidget,
 QDialog,QFormLayout,QLineEdit,QDateEdit,QComboBox,QCheckBox,QTabWidget,QPlainTextEdit)
from .planning_panel import fill,buttons
from .production import eligible
from . import site_issues as issues


class SiteIssuesPanel(QWidget):
    def __init__(self,host):
        super().__init__(host);self.host=host;layout=QVBoxLayout(self);bar=QHBoxLayout()
        for label,callback in (('Nueva incidencia…',lambda:self.edit(True)),('Editar…',self.edit),('Cambiar estado…',self.transition),('Exportar vista…',self.export)):
            button=QPushButton(label);button.clicked.connect(callback);bar.addWidget(button)
        layout.addLayout(bar);bar=QHBoxLayout();bar.addWidget(QLabel('Fecha de revisión'))
        self.cut=QDateEdit(QDate.currentDate());self.cut.setCalendarPopup(True);self.cut.setDisplayFormat('dd/MM/yyyy');bar.addWidget(self.cut)
        self.pending=QCheckBox('Solo pendientes');self.overdue=QCheckBox('Solo vencidas');bar.addWidget(self.pending);bar.addWidget(self.overdue);bar.addStretch();layout.addLayout(bar)
        note=QLabel('Incidencias por partida o generales, con responsable, prioridad y vencimiento. Resolver, anular o reabrir exige una nota. La revisión aplica estados actuales; no reconstruye estados históricos. Vencida significa pendiente con vencimiento anterior a la fecha elegida.');note.setWordWrap(True);layout.addWidget(note)
        self.status=QLabel();layout.addWidget(self.status);self.tabs=QTabWidget();layout.addWidget(self.tabs);self.table=QTableWidget();self.history=QTableWidget();self.tabs.addTab(self.table,'Incidencias');self.tabs.addTab(self.history,'Historial de estados')
        note=QLabel('El historial conserva todas las transiciones de estado, sin los filtros de la lista. El responsable es texto libre; no se envían notificaciones.');note.setWordWrap(True);layout.addWidget(note)
        self.ids=[];self.table.cellDoubleClicked.connect(lambda *_:self.edit());self.cut.dateChanged.connect(self.render);self.pending.toggled.connect(self.render);self.overdue.toggled.connect(self.render)
    def render(self,*_):
        date=self.cut.date().toString('yyyy-MM-dd');rows=issues.listing(self.host.budget,date,self.pending.isChecked(),self.overdue.isChecked());self.ids=[r['id'] for r in rows]
        fill(self.table,issues.HEADERS,issues.report_rows(self.host.budget,date,self.pending.isChecked(),self.overdue.isChecked()));fill(self.history,issues.EVENT_HEADERS,issues.event_rows(self.host.budget))
        self.status.setText(f"Incidencias visibles: {len(rows)} · Vencidas visibles: {sum(r['overdue'] for r in rows)}")
    def selected(self):
        i=self.table.currentRow()
        if self.tabs.currentIndex()!=0 or not 0<=i<len(self.ids):self.host._error('Selecciona una incidencia en la lista.');return None
        return next(r for r in issues.validate(self.host.budget) if r['id']==self.ids[i])
    def edit(self,new=False):
        old=None if new else self.selected()
        if not new and old is None:return
        if old and old['status'] not in ('open','in_progress'):self.host._error('Reabre la incidencia antes de editarla.');return
        dialog=QDialog(self);dialog.setWindowTitle('Incidencia de obra');dialog.resize(650,560);form=QFormLayout(dialog);editors={}
        for key,label in (('reference','Referencia'),('title','Título'),('responsible','Responsable')):
            editor=QLineEdit(old[key] if old else '');editor.setObjectName('issue-'+key);editors[key]=editor;form.addRow(label,editor)
        editors['reference'].setReadOnly(old is not None)
        opened=QDateEdit(QDate.fromString(old['opened'],'yyyy-MM-dd') if old else QDate.currentDate());opened.setCalendarPopup(True);opened.setDisplayFormat('dd/MM/yyyy');opened.setEnabled(old is None);form.addRow('Apertura',opened)
        due_enabled=QCheckBox('Establecer vencimiento');due_enabled.setObjectName('issue-has-due');due_enabled.setChecked(bool(old and old['due']));form.addRow(due_enabled)
        due=QDateEdit(QDate.fromString(old['due'],'yyyy-MM-dd') if old and old['due'] else opened.date());due.setCalendarPopup(True);due.setDisplayFormat('dd/MM/yyyy');due.setEnabled(due_enabled.isChecked());due_enabled.toggled.connect(due.setEnabled);form.addRow('Vencimiento',due)
        priority=QComboBox();priority.setObjectName('issue-priority')
        for key,label in issues.PRIORITIES.items():priority.addItem(label,key)
        priority.setCurrentIndex(priority.findData(old['priority'] if old else 'normal'));form.addRow('Prioridad',priority)
        category=QComboBox()
        for key,label in issues.CATEGORIES.items():category.addItem(label,key)
        if old:category.setCurrentIndex(category.findData(old['category']))
        form.addRow('Categoría',category);target=QComboBox();target.setObjectName('issue-relation');target.addItem('General / sin partida',None)
        for r in eligible(self.host.budget):
            c=self.host.budget.concepts[r.child_code];target.addItem(c.code+' · '+c.summary+' · '+r.id,r.id)
        if old and old['relation_id']:target.setCurrentIndex(target.findData(old['relation_id']))
        form.addRow('Partida',target);description=QPlainTextEdit(old['description'] if old else '');description.setObjectName('issue-description');form.addRow('Descripción',description);buttons(dialog,form)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            self.host._execute('site.issue.set',reference=editors['reference'].text(),opened=opened.date().toString('yyyy-MM-dd'),title=editors['title'].text(),responsible=editors['responsible'].text(),priority=priority.currentData(),category=category.currentData(),due=due.date().toString('yyyy-MM-dd') if due_enabled.isChecked() else None,relation_id=target.currentData(),description=description.toPlainText(),issue_id=old['id'] if old else None)
    def transition(self):
        old=self.selected()
        if old is None:return
        allowed=issues.TRANSITIONS[old['status']]
        if not allowed:self.host._error('La incidencia está anulada y no admite más cambios.');return
        dialog=QDialog(self);dialog.setWindowTitle('Estado de incidencia');form=QFormLayout(dialog);status=QComboBox();status.setObjectName('issue-status')
        for key in allowed:status.addItem(issues.STATES[key],key)
        form.addRow('Nuevo estado',status);day=QDateEdit(max(QDate.currentDate(),QDate.fromString(old['events'][-1]['date'],'yyyy-MM-dd')));day.setCalendarPopup(True);day.setDisplayFormat('dd/MM/yyyy');form.addRow('Fecha del cambio',day)
        note=QPlainTextEdit();note.setObjectName('issue-event-note');form.addRow('Nota / motivo',note);buttons(dialog,form)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.host._execute('site.issue.status',issue_id=old['id'],status=status.currentData(),date=day.date().toString('yyyy-MM-dd'),note=note.toPlainText())
    def export(self):
        from .report_actions import export_report
        if self.tabs.currentIndex():kind='incidencias_historial'
        else:kind='incidencias:'+self.cut.date().toString('yyyy-MM-dd')+':'+('vencidas' if self.overdue.isChecked() else 'pendientes' if self.pending.isChecked() else 'todas')
        export_report(self.host,kind)
