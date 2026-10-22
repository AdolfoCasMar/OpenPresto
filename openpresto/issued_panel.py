"""Desktop forms for isolated issued documents and actual receipts."""
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QTabWidget,QTableWidget,QTableWidgetItem,QLabel,QDialog,QFormLayout,QLineEdit,QComboBox,QInputDialog
from .planning_panel import fill,buttons
from .operations_panels import date_edit
from . import issued_management as engine
from .reports import report_table

KINDS={'Pedido':'order','Albarán':'delivery','Factura':'invoice','Proforma':'proforma'}


class IssuedPanel(QWidget):
    def __init__(self,host):
        super().__init__(host);self.host=host;layout=QVBoxLayout(self)
        note=QLabel('Ventas y cobros separados de compras y existencias. Los documentos PZH se copian como borradores. Un estado cobrado sin fecha se revisa como saldo de apertura; no se inventa un cobro histórico.');note.setWordWrap(True);layout.addWidget(note)
        self.tabs=QTabWidget();layout.addWidget(self.tabs);self.tables={}
        actions={
            'issued_documents':(('Nuevo…',lambda:self.document(True)),('Editar…',self.document),('Confirmar',lambda:self.status('posted')),('Cancelar',lambda:self.status('cancelled')),('Cobrar…',self.receipt),('Aceptar apertura…',self.opening),('Retirar apertura',self.cancel_opening)),
            'issued_customers':(('Nuevo cliente…',self.customer),),
            'issued_receipts':(('Anular cobro seleccionado',self.cancel_receipt),),
            'issued_source':(('Copiar PZH seleccionado a borrador',self.copy_source),)}
        for key,label in (('issued_documents','Documentos emitidos'),('issued_customers','Clientes'),('issued_receipts','Cobros'),('issued_dues','Vencimientos de origen'),('issued_source','Origen PZH')):
            page=QWidget();box=QVBoxLayout(page);bar=QHBoxLayout();box.addLayout(bar)
            for title,callback in actions.get(key,()):
                button=QPushButton(title);button.clicked.connect(callback);bar.addWidget(button)
            table=QTableWidget();self.tables[key]=table;box.addWidget(table);self.tabs.addTab(page,label)
        from .retention_openings_panel import RetentionOpeningsPanel
        self.retention_openings=RetentionOpeningsPanel(host,issued=True)
        self.tabs.addTab(self.retention_openings,'Retenciones')
        self.ids=[]

    def render(self):
        self.retention_openings.render()
        self.ids=[r['id'] for r in engine.state(self.host.budget)['documents']]
        for key,table in self.tables.items():
            fill(table,*report_table(self.host.budget,key))
            if key in ('issued_documents','issued_customers','issued_receipts'):table.setColumnHidden(0,True)

    def selected(self):
        row=self.tables['issued_documents'].currentRow()
        return next((r for r in engine.state(self.host.budget)['documents'] if 0<=row<len(self.ids) and r['id']==self.ids[row]),None)

    def copy_source(self):
        table=self.tables['issued_source'];row=table.currentRow()
        if row>=0:self.host._execute('pzh.issued.copy',source_id=int(table.item(row,0).text()))

    def customer(self):
        name,ok=QInputDialog.getText(self,'Cliente','Nombre')
        if ok and name.strip():self.host._execute('issued.customer.set',name=name.strip())

    def status(self,status):
        doc=self.selected()
        if doc:self.host._execute('issued.document.status',document_id=doc['id'],status=status)

    def receipt(self):
        doc=self.selected()
        if not doc:return
        dialog=QDialog(self);dialog.setWindowTitle('Registrar cobro real');form=QFormLayout(dialog)
        date=date_edit();amount=QLineEdit();reference=QLineEdit()
        form.addRow('Fecha real del cobro',date);form.addRow('Importe',amount);form.addRow('Referencia',reference);buttons(dialog,form)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.host._execute('issued.receipt.record',document_id=doc['id'],date=date.date().toString('yyyy-MM-dd'),amount=amount.text().replace(',','.'),reference=reference.text())

    def cancel_receipt(self):
        row=self.tables['issued_receipts'].currentRow()
        if row>=0:self.host._execute('issued.receipt.cancel',receipt_id=self.tables['issued_receipts'].item(row,0).text())

    def opening(self):
        doc=self.selected()
        if not doc:return
        dialog=QDialog(self);dialog.setWindowTitle('Revisar apertura de cobros');form=QFormLayout(dialog)
        source=engine.state(self.host.budget)['source_states'].get(doc['id'],{})
        form.addRow(QLabel('Importe cobrado en origen sin fecha: '+source.get('paid','sin saldo conciliado')))
        date=date_edit();form.addRow('Inicio del seguimiento nativo',date);buttons(dialog,form)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.host._execute('issued.opening.accept',document_id=doc['id'],date=date.date().toString('yyyy-MM-dd'))

    def cancel_opening(self):
        doc=self.selected()
        if doc:self.host._execute('issued.opening.cancel',document_id=doc['id'])

    def document(self,new=False):
        old=None if new else self.selected()
        if not new and old is None:return
        data=engine.state(self.host.budget)
        if not data['customers']:self.host._error('Crea un cliente antes de emitir un documento.');return
        dialog=QDialog(self);dialog.setWindowTitle('Documento emitido');dialog.resize(680,500);form=QFormLayout(dialog)
        kind=QComboBox()
        for label,value in KINDS.items():kind.addItem(label,value)
        if old:kind.setCurrentIndex(list(KINDS.values()).index(old['kind']))
        customer=QComboBox()
        for c in data['customers']:customer.addItem(c['name'],c['id'])
        if old:customer.setCurrentIndex(customer.findData(old['customer_id']))
        reference=QLineEdit(old['reference'] if old else '')
        date=date_edit(old['date'] if old else None)
        tax=QLineEdit(old['tax_percent'] if old else '0');retention=QLineEdit(old['retention_percent'] if old else '0')
        for label,widget in (('Tipo',kind),('Cliente',customer),('Referencia',reference),('Fecha',date),('Impuesto %',tax),('Retención %',retention)):form.addRow(label,widget)
        table=QTableWidget(0,3);table.setHorizontalHeaderLabels(('Código del concepto','Cantidad · vacío=global','Precio / importe'))
        sources=[]
        def append(line=None):
            line=line or dict(code='',quantity='1',unit_price='0',source_document=None,source_index=None)
            row=table.rowCount();table.insertRow(row);sources.append((line.get('source_document'),line.get('source_index')))
            for col,key in enumerate(('code','quantity','unit_price')):table.setItem(row,col,QTableWidgetItem('' if line[key] is None else line[key]))
        for line in old['lines'] if old else []:append(line)
        add=QPushButton('Añadir línea');add.clicked.connect(lambda:append());form.addRow(add);form.addRow(table);buttons(dialog,form)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        lines=[]
        for row in range(table.rowCount()):
            code,quantity,price=[table.item(row,c).text().strip() for c in range(3)]
            lines.append(dict(code=code,quantity=quantity.replace(',','.') or None,unit_price=price.replace(',','.'),source_document=sources[row][0],source_index=sources[row][1]))
        self.host._execute('issued.document.set',kind=kind.currentData(),reference=reference.text(),customer_id=customer.currentData(),date=date.date().toString('yyyy-MM-dd'),lines=lines,tax_percent=tax.text().replace(',','.'),retention_percent=retention.text().replace(',','.'),document_id=old['id'] if old else None,due_date=old['due_date'] if old else None,rounding=old.get('rounding','line') if old else 'line')
