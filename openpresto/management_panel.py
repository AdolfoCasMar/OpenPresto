"""Procurement/execution UI adapters for native management commands."""
from PySide6.QtCore import Qt,QDate
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QLabel,QTabWidget,QTableWidget,QTableWidgetItem,
 QDialog,QFormLayout,QDialogButtonBox,QLineEdit,QComboBox,QDateEdit,QCheckBox,QInputDialog)
from .planning_panel import fill,buttons
from .management import validate,document_rows,ledger,cash_rows,remaining_source_lines,contract_order_lines,document_amounts,contract_rows,offer_rows
from .ui_icons import icon

KINDS={'Pedido':'order','Albarán':'delivery','Factura':'invoice','Proforma':'proforma'}
LABELS={v:k for k,v in KINDS.items()}
STATES={'draft':'Borrador','posted':'Confirmado','cancelled':'Cancelado'}


def choose(parent,title,rows,label):
    if not rows:
        parent.host._error('No hay elementos disponibles para esta operación.');return None
    labels=[label(r)+' · '+r['id'].split(':')[-1][:8] for r in rows]
    value,ok=QInputDialog.getItem(parent,title,'Selecciona:',labels,0,False)
    return rows[labels.index(value)] if ok else None


class LinesDialog(QDialog):
    def __init__(self,host,rows=None,contract=False,parent=None):
        super().__init__(parent);self.host=host;self.contract=contract;self.sources=[]
        self.document_names={r['id']:LABELS[r['kind']]+' '+r['reference'] for r in validate(host.budget)['documents']}
        self.setWindowTitle('Suministros del contrato' if contract else 'Líneas del documento');self.resize(820,420)
        layout=QVBoxLayout(self);self.table=QTableWidget(0,3 if contract else 5)
        self.table.setHorizontalHeaderLabels(('Suministro / trabajo','Cantidad','Genera existencias') if contract else ('Suministro / trabajo','Cantidad · vacío=importe global','Precio / importe','Origen vinculado','Genera existencias'))
        layout.addWidget(self.table);bar=QHBoxLayout()
        for text,callback in (('Añadir suministro…',self.add),('Retirar línea',self.remove)):
            b=QPushButton(text);b.clicked.connect(callback);bar.addWidget(b)
        layout.addLayout(bar);box=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);box.accepted.connect(self.accept);box.rejected.connect(self.reject);layout.addWidget(box)
        for row in rows or []:self.append(row)

    def append(self,row):
        index=self.table.rowCount();self.table.insertRow(index)
        source={key:row.get(key) for key in ('source_document','source_index')};self.sources.append(source)
        values=[row['code'],row.get('quantity','1')]
        if not self.contract:values += [row.get('unit_price','0'),(self.document_names.get(source['source_document'],source['source_document'][-12:])+' · línea '+str(source['source_index']+1)) if source['source_document'] else 'Sin vínculo']
        for col,value in enumerate(values):
            item=QTableWidgetItem('' if value is None else str(value))
            if col in (0,3):item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(index,col,item)
        stock=QCheckBox();stock.setChecked(row.get('stock',True));self.table.setCellWidget(index,2 if self.contract else 4,stock)

    def add(self):
        budget=self.host.budget
        from .management import purchase_resource
        from .budget import BudgetError
        from .calculations import calculator_for
        codes=[];flags={}
        for concept in budget.concepts.values():
            stock=not any(r.parent_code==concept.code for r in budget.relations) and concept.nature.casefold()!='mano de obra'
            try:purchase_resource(budget,{'code':concept.code,'stock':stock})
            except BudgetError:continue
            codes.append(concept.code);flags[concept.code]=stock
        if not codes:self.host._error('No hay suministros básicos en esta obra.');return
        code,ok=QInputDialog.getItem(self,'Suministro o trabajo','Concepto:',sorted(codes),0,False)
        if ok:self.append({'code':code,'quantity':'1','unit_price':str(calculator_for(budget).price(code)),'stock':flags[code]})

    def remove(self):
        index=self.table.currentRow()
        if index>=0:self.table.removeRow(index);self.sources.pop(index)

    def rows(self):
        result=[]
        for i,source in enumerate(self.sources):
            row={'code':self.table.item(i,0).text(),'quantity':self.table.item(i,1).text().strip().replace(',','.') or None}
            if not self.contract:row.update(unit_price=self.table.item(i,2).text().replace(',','.'),**source)
            row['stock']=self.table.cellWidget(i,2 if self.contract else 4).isChecked()
            result.append(row)
        return result


class ManagementPanel(QWidget):
    def __init__(self,host):
        super().__init__(host);self.host=host;layout=QVBoxLayout(self)
        note=QLabel('Documentos nativos y copias editables desde Origen PZH. Los trabajos y servicios sin existencias se facturan sin generar almacén. Los vínculos evitan duplicar entradas. Los documentos confirmados quedan bloqueados; impuestos y retenciones se declaran por documento.');note.setWordWrap(True);layout.addWidget(note)
        self.tabs=QTabWidget();layout.addWidget(self.tabs);self.tables={}
        specs=(('suppliers','Proveedores',(('Nuevo proveedor…',self.supplier),('Editar proveedor…',self.edit_supplier))),
          ('contracts','Contratos y ofertas',(('Nuevo contrato…',self.contract),('Editar contrato…',self.edit_contract),('Registrar oferta…',self.offer),('Adjudicar…',self.award),('Pedido del contrato…',self.order))),
          ('bids','Comparación de ofertas',(('Registrar oferta…',self.offer),('Adjudicar…',self.award))),
          ('documents','Pedidos, albaranes y facturas',(('Nuevo documento…',self.document),('Editar borrador…',self.edit_document),('Desde documento…',self.linked_document),('Confirmar',lambda:self.status('posted')),('Cancelar documento',lambda:self.status('cancelled')))),
          ('stocks','Existencias y consumos',(('Registrar consumo…',self.consume),)),('cash','Vencimientos',()))
        for key,title,actions in specs:
            page=QWidget();box=QVBoxLayout(page);bar=QHBoxLayout()
            for text,callback in actions:
                b=QPushButton(text);b.clicked.connect(callback);bar.addWidget(b)
            box.addLayout(bar);table=QTableWidget();box.addWidget(table);self.tables[key]=table;self.tabs.addTab(page,title)
        from .operations_panels import PaymentsPanel, SourcePanel, PaymentSchedulePanel
        self.payments=PaymentsPanel(host);self.tabs.addTab(self.payments,'Pagos y saldos')
        self.payment_schedule=PaymentSchedulePanel(host);self.tabs.addTab(self.payment_schedule,'Calendario de pagos')
        self.source=SourcePanel(host,[('pzh_entities','Entidades'),('pzh_offers','Precios'),('pzh_contracts','Comparación de ofertas'),('pzh_balances','Saldos de facturas'),('pzh_documents','Documentos'),('pzh_supplies','Suministros'),('pzh_dues','Vencimientos'),('pzh_rejected','Sin convertir'),('pzh_conversion','Conversión nativa'),('pzh_control_records','Registros de control')]);self.tabs.addTab(self.source,'Origen PZH')
        from .issued_panel import IssuedPanel
        self.issued=IssuedPanel(host);self.tabs.addTab(self.issued,'Gestión emitida')
        from .entities_panel import EntitiesPanel
        self.entities=EntitiesPanel(host);self.tabs.addTab(self.entities,'Entidades')
        from .treasury_panel import TreasuryPanel
        self.treasury=TreasuryPanel(host);self.tabs.addTab(self.treasury,'Tesorería')
        from .cost_control_panel import CostControlPanel
        self.cost_control=CostControlPanel(host);self.tabs.addTab(self.cost_control,'Control económico')
        from .procurement_tracking_panel import ProcurementTrackingPanel
        self.procurement_tracking=ProcurementTrackingPanel(host);self.tabs.addTab(self.procurement_tracking,'Seguimiento de compras')
        from .production_panel import ProductionPanel
        self.production=ProductionPanel(host);self.tabs.addTab(self.production,'Partes de obra')
        from .resource_hours_panel import ResourceHoursPanel
        self.resource_hours=ResourceHoursPanel(host);self.tabs.addTab(self.resource_hours,'Horas y equipos')
        from .site_issues_panel import SiteIssuesPanel
        self.site_issues=SiteIssuesPanel(host);self.tabs.addTab(self.site_issues,'Incidencias de obra')
        from .quality_control_panel import QualityControlPanel
        self.quality_control=QualityControlPanel(host);self.tabs.addTab(self.quality_control,'Control de calidad')
        from .productivity_panel import ProductivityPanel
        self.productivity=ProductivityPanel(host);self.tabs.addTab(self.productivity,'Rendimientos de obra')
        from .budget_baselines_panel import BudgetBaselinesPanel
        self.budget_baselines=BudgetBaselinesPanel(host);self.tabs.addTab(self.budget_baselines,'Líneas base del presupuesto')
        from .nonconformities_panel import NonconformitiesPanel
        self.nonconformities=NonconformitiesPanel(host);self.tabs.addTab(self.nonconformities,'No conformidades')
        from .inventory_control_panel import InventoryControlPanel
        self.inventory_control=InventoryControlPanel(host);self.tabs.addTab(self.inventory_control,'Inventario a fecha')
        from .technical_documents_panel import TechnicalDocumentsPanel
        self.technical_documents=TechnicalDocumentsPanel(host);self.tabs.addTab(self.technical_documents,'Documentación técnica')
        from .budget_phase_measurements_panel import BudgetPhaseMeasurementsPanel
        self.budget_phase_measurements=BudgetPhaseMeasurementsPanel(host);self.tabs.addTab(self.budget_phase_measurements,'Mediciones por fases')
        from .retention_openings_panel import RetentionOpeningsPanel
        self.retention_openings=RetentionOpeningsPanel(host);self.tabs.addTab(self.retention_openings,'Retenciones')
        from .retention_settlements_panel import RetentionSettlementsPanel
        self.retention_settlements=RetentionSettlementsPanel(host);self.tabs.addTab(self.retention_settlements,'Liquidaciones de retenciones')
        self.ids={}

    def render(self):
        self.issued.render();self.entities.render();self.treasury.render();self.cost_control.render();self.procurement_tracking.render();self.production.render();self.resource_hours.render();self.site_issues.render();self.quality_control.render();self.productivity.render();self.budget_baselines.render();self.nonconformities.render();self.inventory_control.render();self.technical_documents.render();self.budget_phase_measurements.render();self.budget_phase_measurements.render()
        self.retention_openings.render();self.payments.render();self.source.render();self.payment_schedule.render()
        self.retention_settlements.render()
        data=validate(self.host.budget);names={r['id']:r['name'] for r in data['suppliers']}
        self.ids={key:[r['id'] for r in data[key]] for key in ('suppliers','contracts','documents')}
        fill(self.tables['suppliers'],('Proveedor','Contacto'),[(r['name'],r['contact']) for r in data['suppliers']])
        fill(self.tables['contracts'],('Contrato','Suministros','Ofertas','Adjudicatario','Importe adjudicado'),contract_rows(self.host.budget))
        fill(self.tables['bids'],('Contrato','Proveedor','Suministros sin precio','Importe con precios disponibles','Adjudicatario','Importe adjudicado'),offer_rows(self.host.budget))
        fill(self.tables['documents'],('Tipo','Referencia','Fecha','Proveedor','Estado','Base','Impuesto','Retención','Total'),[(LABELS[r[1]],r[2],r[3],names[r[4]],STATES[r[5]],*r[6:]) for r in document_rows(self.host.budget)])
        fill(self.tables['stocks'],('Fecha','Suministro','Movimiento','Documento / destino','Cantidad','Valor','Existencias','Valor restante'),ledger(self.host.budget))
        fill(self.tables['cash'],('Vencimiento','Tipo','Documento','Importe previsto'),[(r[0],LABELS[r[1]],r[2],r[3]) for r in cash_rows(self.host.budget)])

    def edit_supplier(self):
        index=self.tables['suppliers'].currentRow();data=validate(self.host.budget)
        if 0<=index<len(data['suppliers']):self.supplier(data['suppliers'][index])

    def edit_document(self):
        index=self.tables['documents'].currentRow();data=validate(self.host.budget)
        if not 0<=index<len(data['documents']):return
        row=data['documents'][index]
        if row['status']!='draft':self.host._error('Solo se editan borradores.');return
        self.document(kind=row['kind'],supplier_id=row['supplier_id'],rows=row['lines'],existing=row)

    def supplier(self,existing=None):
        if not isinstance(existing,dict):existing=None
        d=QDialog(self);d.setWindowTitle('Proveedor');form=QFormLayout(d);name=QLineEdit(existing['name'] if existing else '');contact=QLineEdit(existing['contact'] if existing else '');form.addRow('Nombre',name);form.addRow('Contacto',contact);buttons(d,form)
        if d.exec()==QDialog.DialogCode.Accepted:self.host._execute('management.supplier.set',name=name.text(),contact=contact.text(),supplier_id=existing['id'] if existing else None)

    def edit_contract(self):
        index=self.tables['contracts'].currentRow();data=validate(self.host.budget)
        if not 0<=index<len(data['contracts']):return
        existing=data['contracts'][index]
        if existing['award'] is not None:self.host._error('El contrato adjudicado conserva sus suministros y precios.');return
        self.contract(existing=existing)

    def contract(self,checked=False,existing=None):
        title,ok=QInputDialog.getText(self,'Contrato','Nombre:',text=existing['title'] if existing else '')
        if not ok:return
        lines=LinesDialog(self.host,rows=existing['lines'] if existing else None,contract=True,parent=self)
        if lines.exec()==QDialog.DialogCode.Accepted:self.host._execute('management.contract.set',title=title,lines=lines.rows(),contract_id=existing['id'] if existing else None,rounding=existing.get('rounding','line') if existing else 'line')

    def offer(self):
        data=validate(self.host.budget);contract=choose(self,'Contrato',data['contracts'],lambda r:r['title'])
        if not contract:return
        supplier=choose(self,'Proveedor ofertante',data['suppliers'],lambda r:r['name'])
        if not supplier:return
        d=QDialog(self);d.setWindowTitle('Oferta · '+supplier['name']);form=QFormLayout(d);edits={}
        for line in contract['lines']:
            value=contract['offers'].get(supplier['id'],{}).get(line['code']);edit=QLineEdit('' if value is None else str(value));edit.setPlaceholderText('Vacío = no ofertado; se adjudica a cero');edits[line['code']]=edit;form.addRow(line['code'],edit)
        buttons(d,form)
        if d.exec()==QDialog.DialogCode.Accepted:self.host._execute('management.offer.set',contract_id=contract['id'],supplier_id=supplier['id'],prices={code:edit.text().strip().replace(',','.') or None for code,edit in edits.items()})

    def award(self):
        data=validate(self.host.budget);contract=choose(self,'Contrato',data['contracts'],lambda r:r['title'])
        if not contract:return
        supplier=choose(self,'Adjudicatario · precios no ofertados pasan a cero',[r for r in data['suppliers'] if r['id'] in contract['offers']],lambda r:r['name'])
        if supplier:self.host._execute('management.contract.award',contract_id=contract['id'],supplier_id=supplier['id'])

    def order(self):
        data=validate(self.host.budget);contract=choose(self,'Contrato adjudicado',[r for r in data['contracts'] if r['award']],lambda r:r['title'])
        if contract:self.document(kind='order',supplier_id=contract['award']['supplier_id'],rows=contract_order_lines(self.host.budget,contract['id']),rounding=contract.get('rounding','line'))

    def linked_document(self):
        data=validate(self.host.budget);source=choose(self,'Documento de origen',[r for r in data['documents'] if r['status']=='posted' and r['kind'] in ('order','delivery')],lambda r:LABELS[r['kind']]+' '+r['reference'])
        if not source:return
        rows=remaining_source_lines(self.host.budget,source['id'])
        if not rows:self.host._error('El documento no tiene cantidades pendientes.');return
        options=['Albarán','Factura'] if source['kind']=='order' else ['Factura']
        label,ok=QInputDialog.getItem(self,'Nuevo documento vinculado','Tipo:',options,0,False)
        if ok:self.document(kind=KINDS[label],supplier_id=source['supplier_id'],rows=rows,min_date=source['date'],rounding=source.get('rounding','line'))

    def document(self,checked=False,*,kind=None,supplier_id=None,rows=None,min_date=None,existing=None,rounding=None):
        data=validate(self.host.budget)
        if rounding is None:rounding=existing.get('rounding','line') if existing else 'line'
        if not data['suppliers']:self.host._error('Añade un proveedor antes de crear documentos.');return
        d=QDialog(self);d.setWindowTitle('Documento de gestión');form=QFormLayout(d);k=QComboBox()
        for label,value in KINDS.items():k.addItem(label,value)
        if kind:k.setCurrentIndex(k.findData(kind));k.setEnabled(False)
        supplier=QComboBox()
        for r in data['suppliers']:supplier.addItem(r['name'],r['id'])
        if supplier_id:supplier.setCurrentIndex(supplier.findData(supplier_id));supplier.setEnabled(False)
        reference=QLineEdit();day=QDateEdit(QDate.currentDate());day.setDisplayFormat('yyyy-MM-dd');day.setCalendarPopup(True)
        if min_date:day.setMinimumDate(QDate.fromString(min_date,'yyyy-MM-dd'))
        due=QDateEdit(QDate.currentDate());due.setDisplayFormat('yyyy-MM-dd');due.setCalendarPopup(True);has_due=QCheckBox('Registrar vencimiento previsto')
        tax=QLineEdit('0');retention=QLineEdit('0');posted=QCheckBox('Confirmar al guardar')
        if existing:
            reference.setText(existing['reference']);day.setDate(QDate.fromString(existing['date'],'yyyy-MM-dd'))
            tax.setText(existing['tax_percent']);retention.setText(existing['retention_percent'])
            has_due.setChecked(existing['due_date'] is not None)
            if existing['due_date']:due.setDate(QDate.fromString(existing['due_date'],'yyyy-MM-dd'))
        form.addRow('Redondeo',QLabel('Al total del documento' if rounding=='total' else 'Por línea'))
        current_lines=list(rows or [])
        edit=QPushButton('Editar suministros…')
        def edit_lines():
            dialog=LinesDialog(self.host,rows=current_lines,parent=self)
            if dialog.exec()==QDialog.DialogCode.Accepted:
                current_lines[:]=dialog.rows()
        edit.clicked.connect(edit_lines)
        for label,widget in (('Tipo',k),('Referencia',reference),('Proveedor',supplier),('Fecha',day),('Líneas',edit),('Impuesto (%)',tax),('Retención (%)',retention),('',has_due),('Vencimiento',due),('',posted)):form.addRow(label,widget)
        buttons(d,form)
        if d.exec()==QDialog.DialogCode.Accepted:self.host._execute('management.document.set',kind=k.currentData(),reference=reference.text(),supplier_id=supplier.currentData(),date=day.date().toString('yyyy-MM-dd'),lines=current_lines,tax_percent=tax.text().replace(',','.'),retention_percent=retention.text().replace(',','.'),due_date=due.date().toString('yyyy-MM-dd') if has_due.isChecked() else None,status='posted' if posted.isChecked() else 'draft',document_id=existing['id'] if existing else None,rounding=rounding)

    def status(self,status):
        index=self.tables['documents'].currentRow()
        if 0<=index<len(self.ids.get('documents',[])):self.host._execute('management.document.status',document_id=self.ids['documents'][index],status=status)

    def consume(self):
        d=QDialog(self);d.setWindowTitle('Consumo de suministro');form=QFormLayout(d);codes=sorted({r[1] for r in ledger(self.host.budget)})
        if not codes:self.host._error('Registra entradas confirmadas antes de consumir.');return
        code=QComboBox();code.addItems(codes);quantity=QLineEdit('1');destination=QLineEdit();day=QDateEdit(QDate.currentDate());day.setDisplayFormat('yyyy-MM-dd');day.setCalendarPopup(True)
        for label,widget in (('Suministro',code),('Fecha',day),('Cantidad',quantity),('Destino / actividad',destination)):form.addRow(label,widget)
        buttons(d,form)
        if d.exec()==QDialog.DialogCode.Accepted:self.host._execute('management.consumption.add',code=code.currentText(),date=day.date().toString('yyyy-MM-dd'),quantity=quantity.text().replace(',','.'),destination=destination.text())
