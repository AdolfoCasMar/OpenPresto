"""Desktop review of retention opening balances."""
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QLabel,QTableWidget,QDialog,QFormLayout,QLineEdit
from .planning_panel import fill,buttons
from . import retention_openings as engine


class RetentionOpeningsPanel(QWidget):
    def __init__(self,host,issued=False):
        super().__init__(host);self.host=host;self.engine=engine;self.command='management.retention.opening.';self.report='retenciones_apertura'
        if issued:
            from . import issued_retention_openings
            self.engine=issued_retention_openings;self.command='issued.retention.opening.';self.report='retenciones_emitidas_apertura'
        layout=QVBoxLayout(self);bar=QHBoxLayout()
        for title,action in (('Revisar apertura…',self.edit),('Retirar revisión',self.clear),('Exportar…',self.export)):
            button=QPushButton(title);button.clicked.connect(action);bar.addWidget(button)
        settlements=QPushButton('Pagos y cobros de retenciones');settlements.clicked.connect(lambda:host.section_ui.ribbon.show_view('gestion:retention_settlements'));bar.addWidget(settlements)
        layout.addLayout(bar);note=QLabel('Garantías y retenciones fiscales separadas. Revisa la fecha de inicio del seguimiento y los importes ya liquidados. La apertura no crea pagos bancarios ni reconstruye movimientos anteriores.');note.setWordWrap(True);layout.addWidget(note);self.table=QTableWidget();layout.addWidget(self.table);self.table.cellDoubleClicked.connect(lambda *_:self.edit());self.rows=[]
    def render(self):
        current=self.rows[self.table.currentRow()][0] if 0<=self.table.currentRow()<len(self.rows) else None
        self.rows=self.engine.report_rows(self.host.budget);fill(self.table,self.engine.HEADERS,self.rows);self.table.setColumnHidden(0,True)
        if self.rows:self.table.setCurrentCell(next((i for i,r in enumerate(self.rows) if r[0]==current),0),1)
    def edit(self):
        i=self.table.currentRow()
        if not 0<=i<len(self.rows):self.host._error('Selecciona una factura con retenciones programadas.');return
        identifier=self.rows[i][0];record=self.engine.validate(self.host.budget).get(identifier,{});old=record.get('opening');source=record.get('source') or dict(guarantee=str(self.rows[i][4] or '0'),fiscal=str(self.rows[i][5] or '0'));dialog=QDialog(self);dialog.setWindowTitle('Revisar apertura de retenciones');form=QFormLayout(dialog);fields={}
        for key,label,value in (('date','Inicio del seguimiento (AAAA-MM-DD)',old['date'] if old else ''),('guarantee','Garantía ya liquidada',old['guarantee'] if old else source.get('guarantee','0')),('fiscal','Retención fiscal ya liquidada',old['fiscal'] if old else source.get('fiscal','0')),('note','Explicación de la revisión',old['note'] if old else '')):
            edit=QLineEdit(value);edit.setObjectName('retention-'+key);fields[key]=edit;form.addRow(label,edit)
        buttons(dialog,form)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.host._execute(self.command+'set',document_id=identifier,date=fields['date'].text().strip(),guarantee=fields['guarantee'].text().strip().replace(',','.'),fiscal=fields['fiscal'].text().strip().replace(',','.'),note=fields['note'].text())
    def clear(self):
        i=self.table.currentRow()
        if not 0<=i<len(self.rows):self.host._error('Selecciona una factura.');return
        self.host._execute(self.command+'clear',document_id=self.rows[i][0])
    def export(self):
        from .report_actions import export_report
        export_report(self.host,self.report)
