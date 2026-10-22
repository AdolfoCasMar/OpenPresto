"""Explicit quality-to-issue workflow; existing issues are never overwritten."""
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QCheckBox,QTableWidget,QDialog,QFormLayout,QLineEdit,QDateEdit,QComboBox
from .planning_panel import fill,buttons
from . import nonconformities as nc,site_issues as issues,quality_control as quality


class NonconformitiesPanel(QWidget):
    def __init__(self,host):
        super().__init__(host);self.host=host;layout=QVBoxLayout(self);bar=QHBoxLayout()
        for label,callback in (('Crear incidencia…',self.create),('Abrir incidencia',self.open_issue),('Exportar…',self.export)):
            button=QPushButton(label);button.clicked.connect(callback);bar.addWidget(button)
        layout.addLayout(bar);bar=QHBoxLayout();self.pending=QCheckBox('Solo sin resolver');self.cancelled=QCheckBox('Incluir controles anulados');bar.addWidget(self.pending);bar.addWidget(self.cancelled);bar.addStretch();layout.addLayout(bar)
        note=QLabel('Cada comprobación «No cumple» de un control revisado puede originar una incidencia. El vínculo conserva el control y la comprobación exactos. Resolver la incidencia no cambia el resultado del control; la verificación posterior se registra en otro control.');note.setWordWrap(True);layout.addWidget(note)
        self.status=QLabel();layout.addWidget(self.status);self.table=QTableWidget();layout.addWidget(self.table);self.table.cellDoubleClicked.connect(lambda *_:self.open_issue());self.rows=[];self.pending.toggled.connect(self.render);self.cancelled.toggled.connect(self.render)
    def render(self,*_):
        self.rows=nc.listing(self.host.budget,self.cancelled.isChecked(),self.pending.isChecked());fill(self.table,nc.HEADERS,[r['row'] for r in self.rows])
        self.status.setText(f"Comprobaciones visibles: {len(self.rows)} · Sin incidencia: {sum(r['issue_id'] is None for r in self.rows)}. Anular un control no anula su incidencia.")
    def selected(self):
        index=self.table.currentRow()
        if not 0<=index<len(self.rows):self.host._error('Selecciona una comprobación.');return None
        return self.rows[index]
    def create(self):
        row=self.selected()
        if row is None:return
        if row['issue_id']:self.host._error('Ya existe una incidencia vinculada.');return
        source=next(r for r in quality.validate(self.host.budget) if r['id']==row['inspection_id'])
        if source['status']!='reviewed':self.host._error('El control está anulado.');return
        dialog=QDialog(self);dialog.setWindowTitle('Incidencia desde no conformidad');form=QFormLayout(dialog);reference=QLineEdit();reference.setObjectName('nc-reference');form.addRow('Referencia de incidencia',reference);responsible=QLineEdit(source['inspector']);form.addRow('Responsable',responsible)
        opened=QDateEdit(max(QDate.currentDate(),QDate.fromString(source['reviewed_on'],'yyyy-MM-dd')));opened.setCalendarPopup(True);opened.setDisplayFormat('dd/MM/yyyy');form.addRow('Apertura',opened)
        priority=QComboBox()
        for key,label in issues.PRIORITIES.items():priority.addItem(label,key)
        priority.setCurrentIndex(priority.findData('normal'));form.addRow('Prioridad',priority)
        has_due=QCheckBox('Establecer vencimiento');form.addRow(has_due);due=QDateEdit(opened.date());due.setCalendarPopup(True);due.setEnabled(False);due.setDisplayFormat('dd/MM/yyyy');has_due.toggled.connect(due.setEnabled);form.addRow('Vencimiento',due);buttons(dialog,form)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.host._execute('quality.issue.create',inspection_id=row['inspection_id'],check_index=row['check_index'],reference=reference.text(),opened=opened.date().toString('yyyy-MM-dd'),responsible=responsible.text(),priority=priority.currentData(),due=due.date().toString('yyyy-MM-dd') if has_due.isChecked() else None)
    def open_issue(self):
        row=self.selected()
        if row is None:return
        if row['issue_id'] is None:self.host._error('Todavía no hay una incidencia vinculada.');return
        manager=self.host.panels['gestion'][1];panel=manager.site_issues;case=next(r for r in issues.validate(self.host.budget) if r['id']==row['issue_id']);panel.pending.setChecked(False);panel.overdue.setChecked(False)
        if panel.cut.date()<QDate.fromString(case['opened'],'yyyy-MM-dd'):panel.cut.setDate(QDate.fromString(case['opened'],'yyyy-MM-dd'))
        panel.render();panel.tabs.setCurrentIndex(0);manager.tabs.setCurrentWidget(panel)
        if row['issue_id'] in panel.ids:panel.table.setCurrentCell(panel.ids.index(row['issue_id']),0)
    def export(self):
        from .report_actions import export_report
        export_report(self.host,'no_conformidades:'+('anulados' if self.cancelled.isChecked() else 'vigentes')+':'+('pendientes' if self.pending.isChecked() else 'todas'))
