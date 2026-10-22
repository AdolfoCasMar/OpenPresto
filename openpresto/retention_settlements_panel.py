"""Record explicit customer/supplier retention settlements without guessed dates."""
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QLabel,QTableWidget,QDialog,QFormLayout,QLineEdit,QComboBox
from .planning_panel import fill,buttons
from . import retention_settlements as engine


class RetentionSettlementsPanel(QWidget):
    def __init__(self,host):
        super().__init__(host);self.host=host;layout=QVBoxLayout(self);bar=QHBoxLayout();layout.addLayout(bar)
        for title,action in (('Registrar pago o cobro…',self.record),('Anular liquidación…',self.cancel),('Exportar…',self.export)):
            button=QPushButton(title);button.clicked.connect(action);bar.addWidget(button)
        note=QLabel('Solo movimientos nuevos con fecha y referencia explícitas. Garantía y fiscal se liquidan por separado del neto de la factura. Revisa primero los saldos de origen. Una anulación conserva el movimiento y añade su reversión a tesorería.');note.setWordWrap(True);layout.addWidget(note);self.table=QTableWidget();layout.addWidget(self.table);self.rows=[]
    def render(self):
        self.rows=engine.report_rows(self.host.budget);fill(self.table,engine.HEADERS,self.rows);self.table.setColumnHidden(0,True)
    def record(self):
        contexts=engine.contexts(self.host.budget);choices=[(key,value) for key,value in contexts.items() if value['document']['status']=='posted']
        if not choices:self.host._error('Confirma una factura con un calendario de retenciones comprobado.');return
        dialog=QDialog(self);dialog.setWindowTitle('Liquidación real de retención');form=QFormLayout(dialog);document=QComboBox();document.setObjectName('retention-settlement-document')
        for (direction,identifier),context in choices:
            document.addItem(('Pago a proveedor' if direction=='out' else 'Cobro de cliente')+' · '+context['document']['reference']+(' · revisar apertura' if context['needs_review'] else ''),direction+'|'+identifier)
        kind=QComboBox();kind.setObjectName('retention-settlement-kind');kind.addItem('Garantía','guarantee');kind.addItem('Fiscal','fiscal');date=QLineEdit();date.setObjectName('retention-settlement-date');amount=QLineEdit();amount.setObjectName('retention-settlement-amount');reference=QLineEdit();reference.setObjectName('retention-settlement-reference')
        for label,widget in (('Factura',document),('Tipo',kind),('Fecha real (AAAA-MM-DD)',date),('Importe',amount),('Referencia del movimiento',reference)):form.addRow(label,widget)
        buttons(dialog,form)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            direction,identifier=document.currentData().split('|',1);self.host._execute('retention.settlement.record',direction=direction,document_id=identifier,kind=kind.currentData(),date=date.text().strip(),amount=amount.text().strip().replace(',','.'),reference=reference.text().strip())
    def cancel(self):
        i=self.table.currentRow()
        if not 0<=i<len(self.rows):self.host._error('Selecciona una liquidación vigente.');return
        dialog=QDialog(self);dialog.setWindowTitle('Anular liquidación de retención');form=QFormLayout(dialog);date=QLineEdit();date.setObjectName('retention-cancellation-date');reason=QLineEdit();reason.setObjectName('retention-cancellation-reason');form.addRow('Fecha de anulación (AAAA-MM-DD)',date);form.addRow('Motivo',reason);buttons(dialog,form)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.host._execute('retention.settlement.cancel',settlement_id=self.rows[i][0],date=date.text().strip(),reason=reason.text().strip())
    def export(self):
        from .report_actions import export_report
        export_report(self.host,'retention_settlements')
