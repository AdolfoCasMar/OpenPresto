"""Desktop adapters for advanced engines and explicitly labelled source data."""
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QTableWidget,
    QTabWidget,QLabel,QDialog,QFormLayout,QDateEdit,QLineEdit,QComboBox,QSpinBox,
    QListWidget,QListWidgetItem,QInputDialog)
from .planning_panel import fill, buttons
from . import planning_advanced, management_advanced, management
from .pzh_operations import table
from .reports import report_table


def date_edit(value=None):
    widget=QDateEdit(QDate.fromString(value,'yyyy-MM-dd') if value else QDate.currentDate())
    widget.setDisplayFormat('yyyy-MM-dd');widget.setCalendarPopup(True)
    return widget


class SourcePanel(QWidget):
    def __init__(self,host,kinds):
        super().__init__(host);self.host=host;self.tables={};layout=QVBoxLayout(self)
        note=QLabel('Datos convertidos del PZH original, de solo lectura. Se muestran las bases recalculadas y sus diferencias. No se recalculan las fechas ni se crean movimientos de existencias. Puedes exportarlos desde Informes.');note.setWordWrap(True);layout.addWidget(note)
        self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status)
        tabs=QTabWidget();layout.addWidget(tabs)
        convert=QPushButton('Leer módulos del PZH conservado');convert.clicked.connect(lambda:host._execute('pzh.operations.convert'));layout.addWidget(convert)
        native=QPushButton('Crear copias editables de los módulos compatibles');native.clicked.connect(lambda:host._execute('pzh.native.convert'));layout.addWidget(native)
        for kind,label in kinds:
            widget=QTableWidget();self.tables[kind]=widget;tabs.addTab(widget,label)
        if 'pzh_control_records' in self.tables:
            edit=QPushButton('Editar estado y nota del registro de control seleccionado');edit.clicked.connect(self.edit_record);layout.addWidget(edit)
        if 'pzh_documents' in self.tables:
            page=QWidget();box=QVBoxLayout(page)
            label=QLabel('Crea una copia editable como borrador de compra. Conserva la fuente y comprueba la base. No confirma entradas, vencimientos ni pagos históricos.');label.setWordWrap(True);box.addWidget(label)
            grid=QTableWidget();self.tables['pzh_native_documents']=grid;box.addWidget(grid)
            copy=QPushButton('Copiar documento seleccionado a borrador');copy.clicked.connect(self.copy_document);box.addWidget(copy);tabs.addTab(page,'Conversión editable')
            copy=QPushButton('Copiar vencimientos de la factura seleccionada');copy.clicked.connect(self.copy_dues);box.addWidget(copy)
            page=QWidget();box=QVBoxLayout(page)
            label=QLabel('Copia los suministros, ofertas y adjudicación contrastada. No crea pedidos, entradas ni pagos. Los contratos adjudicados conservan sus precios como instantánea.');label.setWordWrap(True);box.addWidget(label)
            grid=QTableWidget();self.tables['pzh_native_contracts']=grid;box.addWidget(grid)
            copy=QPushButton('Copiar contrato u oferta seleccionados');copy.clicked.connect(self.copy_contract);box.addWidget(copy);tabs.addTab(page,'Contratos editables')
    def render(self):
        self.status.setText(self.host.budget.project_metadata.get('pzh_operations_notes','No hay una conversión de planificación y gestión PZH en este proyecto.'))
        for kind,widget in self.tables.items():
            fill(widget,*report_table(self.host.budget,kind))
            if kind=='pzh_control_records':widget.setColumnHidden(0,True)
    def edit_record(self):
        grid=self.tables['pzh_control_records'];index=grid.currentRow()
        if index<0:return
        from .pzh_native_modules import control_records,RECORD_STATES
        record=next(r for r in control_records(self.host.budget) if r['id']==grid.item(index,0).text())
        dialog=QDialog(self);dialog.setWindowTitle('Estado del registro de control');form=QFormLayout(dialog)
        state=QComboBox()
        for value,label in RECORD_STATES.items():state.addItem(label,value)
        state.setCurrentIndex(state.findData(record['state']));note=QLineEdit(record['note'])
        form.addRow('Estado',state);form.addRow('Nota',note);buttons(dialog,form)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.host._execute('pzh.record.set',record_id=record['id'],state=state.currentData(),note=note.text())

    def copy_document(self):
        grid=self.tables['pzh_native_documents'];index=grid.currentRow()
        if index>=0:self.host._execute('pzh.management.document.copy',source_id=int(grid.item(index,0).text()))
    def copy_contract(self):
        grid=self.tables['pzh_native_contracts'];index=grid.currentRow()
        if index>=0:self.host._execute('pzh.management.contract.copy',source_id=int(grid.item(index,0).text()))
    def copy_dues(self):
        grid=self.tables['pzh_native_documents'];index=grid.currentRow()
        if index>=0:self.host._execute('pzh.management.dues.copy',source_id=int(grid.item(index,0).text()))


class AdvancedPlanningPanel(QWidget):
    def __init__(self,host):
        super().__init__(host);self.host=host;layout=QVBoxLayout(self);bar=QHBoxLayout()
        for label,callback in (('Inicio del plan…',self.configure),('Nueva actividad…',lambda:self.task(True)),('Editar actividad…',self.task),('Retirar actividad',self.remove)):
            button=QPushButton(label);button.clicked.connect(callback);bar.addWidget(button)
        layout.addLayout(bar);note=QLabel('Ruta crítica por días laborables. Dependencias fin-inicio con desfase no negativo. Duración 0 = hito. Objetivo independiente del presupuesto.');note.setWordWrap(True);layout.addWidget(note)
        self.grid=QTableWidget();layout.addWidget(self.grid);self.ids=[]
    def render(self):
        self.ids=[r['relation_id'] for r in planning_advanced.schedule(self.host.budget)]
        fill(self.grid,*report_table(self.host.budget,'ruta_critica'))
    def configure(self):
        d=QDialog(self);d.setWindowTitle('Inicio del plan avanzado');form=QFormLayout(d)
        start=date_edit(planning_advanced.state(self.host.budget)['start']);form.addRow('Inicio',start);buttons(d,form)
        if d.exec()==QDialog.DialogCode.Accepted:self.host._execute('planning.advanced.configure',start=start.date().toString('yyyy-MM-dd'))
    def task(self,new=False):
        data=planning_advanced.state(self.host.budget)
        if data['start'] is None:self.host._error('Define primero el inicio del plan avanzado.');return
        selected=self.grid.currentRow();rid=self.ids[selected] if not new and 0<=selected<len(self.ids) else None
        old=next((r for r in data['tasks'] if r['relation_id']==rid),None)
        d=QDialog(self);d.setWindowTitle('Actividad, objetivo y precedencias');form=QFormLayout(d);relation=QComboBox()
        for r in self.host.budget.relations:
            b=self.host.budget
            if b.concepts[r.parent_code].nature.casefold() in ('capitulo','capítulo') and (b.concepts[r.child_code].nature.casefold()=='partida' or b.project_metadata.get('certification_role:'+r.id)=='partida'):
                relation.addItem(r.parent_code+' → '+r.child_code,r.id)
        if not relation.count():self.host._error('Añade capítulos y partidas antes de planificar.');return
        if old:relation.setCurrentIndex(relation.findData(rid));relation.setEnabled(False)
        duration=QSpinBox();duration.setRange(0,36600);duration.setValue(old['duration'] if old else 1)
        quantity=QLineEdit(old['quantity'] if old else str(self.host.budget.relation_quantity(relation.currentData())))
        price=QLineEdit(old['price'] if old else '0');previous=QListWidget();lag=QSpinBox();lag.setRange(0,36600)
        oldlinks={r['relation_id']:r['lag'] for r in old['predecessors']} if old else {}
        for t in data['tasks']:
            if t['relation_id']==rid:continue
            item=QListWidgetItem(self.host.budget._relation(t['relation_id']).child_code);item.setData(Qt.ItemDataRole.UserRole,t['relation_id']);item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable);item.setCheckState(Qt.CheckState.Checked if t['relation_id'] in oldlinks else Qt.CheckState.Unchecked);previous.addItem(item)
        for label,w in (('Partida',relation),('Duración laboral',duration),('Cantidad objetivo',quantity),('Precio objetivo',price),('Precedentes',previous),('Desfase de nuevos enlaces',lag)):form.addRow(label,w)
        buttons(d,form)
        if d.exec()==QDialog.DialogCode.Accepted:
            links=[{'relation_id':previous.item(i).data(Qt.ItemDataRole.UserRole),'lag':oldlinks.get(previous.item(i).data(Qt.ItemDataRole.UserRole),lag.value())} for i in range(previous.count()) if previous.item(i).checkState()==Qt.CheckState.Checked]
            self.host._execute('planning.advanced.task.set',relation_id=relation.currentData(),duration=duration.value(),quantity=quantity.text().replace(',','.'),price=price.text().replace(',','.'),predecessors=links)
    def remove(self):
        index=self.grid.currentRow()
        if 0<=index<len(self.ids):self.host._execute('planning.advanced.task.remove',relation_id=self.ids[index])


class PaymentsPanel(QWidget):
    def __init__(self,host):
        super().__init__(host);self.host=host;layout=QVBoxLayout(self);bar=QHBoxLayout()
        for label,callback in (('Registrar pago…',self.pay),('Anular pago…',self.cancel)):
            b=QPushButton(label);b.clicked.connect(callback);bar.addWidget(b)
        layout.addLayout(bar);self.saldos=QTableWidget();self.payments=QTableWidget();layout.addWidget(QLabel('Facturas y saldos'));layout.addWidget(self.saldos);layout.addWidget(QLabel('Pagos registrados'));layout.addWidget(self.payments)
    def render(self):
        from datetime import date
        rows=management_advanced.settlement_rows(self.host.budget,date.today().isoformat())
        fill(self.saldos,('Documento','Tipo','Referencia','Proveedor','Próximo vencimiento','A pagar','Liquidado con apertura','Pendiente','Vencido'),[tuple('Revisar apertura' if value is None and i in (6,7) else '' if value is None else value for i,value in enumerate(row)) for row in rows])
        fill(self.payments,('ID','Fecha','Referencia','Proveedor','Medio','Importe','Estado','Anulación'),management_advanced.payment_rows(self.host.budget))
    def pay(self):
        b=self.host.budget;rows=[r for r in management_advanced.settlement_rows(b) if r[7] is not None and r[7]>0]
        if not rows:self.host._error('No hay facturas confirmadas con saldo disponible. Revisa las aperturas importadas en Calendario de pagos.');return
        d=QDialog(self);d.setWindowTitle('Pago de factura');form=QFormLayout(d);invoice=QComboBox()
        for row in rows:invoice.addItem(str(row[2])+' · pendiente '+str(row[7]),row)
        amount=QLineEdit(str(rows[0][7]));invoice.currentIndexChanged.connect(lambda _:amount.setText(str(invoice.currentData()[7])))
        reference=QLineEdit();method=QLineEdit('Transferencia');day=date_edit()
        for label,w in (('Factura',invoice),('Referencia pago',reference),('Fecha',day),('Medio',method),('Importe pagado',amount)):form.addRow(label,w)
        buttons(d,form)
        if d.exec()==QDialog.DialogCode.Accepted:
            row=invoice.currentData();self.host._execute('management.payment.record',supplier_id=row[3],reference=reference.text(),date=day.date().toString('yyyy-MM-dd'),allocations=[{'document_id':row[0],'amount':amount.text().replace(',','.')}],method=method.text())
    def cancel(self):
        rows=management_advanced.payment_rows(self.host.budget);index=self.payments.currentRow()
        if not 0<=index<len(rows):return
        d=QDialog(self);d.setWindowTitle('Anular pago');form=QFormLayout(d);day=date_edit();reason=QLineEdit();form.addRow('Fecha',day);form.addRow('Motivo',reason);buttons(d,form)
        if d.exec()==QDialog.DialogCode.Accepted:self.host._execute('management.payment.cancel',payment_id=rows[index][0],date=day.date().toString('yyyy-MM-dd'),reason=reason.text())


class PaymentSchedulePanel(QWidget):
    def __init__(self,host):
        super().__init__(host);self.host=host;layout=QVBoxLayout(self);bar=QHBoxLayout()
        for text,callback in (('Editar vencimientos…',self.edit),('Revisar saldo de apertura…',self.opening)):
            button=QPushButton(text);button.clicked.connect(callback);bar.addWidget(button)
        layout.addLayout(bar)
        label=QLabel('El saldo de apertura requiere una fecha de inicio de seguimiento. No crea un pago bancario histórico. La previsión aplica lo liquidado a los vencimientos normales más antiguos; las retenciones se muestran por separado.');label.setWordWrap(True);layout.addWidget(label)
        self.dues=QTableWidget();self.openings=QTableWidget();layout.addWidget(QLabel('Vencimientos programados'));layout.addWidget(self.dues);layout.addWidget(QLabel('Aperturas y revisión'));layout.addWidget(self.openings)
    def render(self):
        fill(self.dues,*report_table(self.host.budget,'calendario_pagos'));self.dues.setColumnHidden(0,True)
        fill(self.openings,*report_table(self.host.budget,'saldos_apertura'));self.openings.setColumnHidden(0,True)
    def choose(self,scheduled=False):
        from .management_schedule import state
        data=management.validate(self.host.budget);calendars=state(self.host.budget)
        rows=[r for r in data['documents'] if r['kind'] in ('invoice','proforma') and r['status']!='cancelled' and (not scheduled or r['id'] in calendars)]
        if not rows:self.host._error('No hay facturas disponibles con calendario.' if scheduled else 'Crea primero una factura.');return None
        labels=[r['reference']+' · '+r['supplier_id'].split(':')[-1]+' · '+r['status'] for r in rows]
        value,ok=QInputDialog.getItem(self,'Factura','Selecciona:',labels,0,False)
        return rows[labels.index(value)] if ok else None
    def edit(self):
        from .management_schedule import state
        doc=self.choose()
        if doc is None:return
        record=state(self.host.budget).get(doc['id']);d=QDialog(self);d.setWindowTitle('Calendario de '+doc['reference']);d.resize(780,420);layout=QVBoxLayout(d)
        _,_,retained,payable=management.document_amounts(self.host.budget,doc)
        label=QLabel('La suma normal debe ser '+str(payable)+' y las retenciones '+str(retained)+'.');label.setWordWrap(True);layout.addWidget(label)
        grid=QTableWidget(0,4);grid.setHorizontalHeaderLabels(('Fecha','Tipo','Importe','Nota'));layout.addWidget(grid);ids=[]
        def append(row=None):
            row=row or {};i=grid.rowCount();grid.insertRow(i);ids.append(row.get('id'))
            day=date_edit(row.get('date',doc['date']));kind=QComboBox()
            for label,value in (('Normal','normal'),('Garantía','guarantee'),('Fiscal','fiscal')):kind.addItem(label,value)
            kind.setCurrentIndex(max(0,kind.findData(row.get('kind','normal'))))
            for j,w in enumerate((day,kind,QLineEdit(row.get('amount','0')),QLineEdit(row.get('note','')))):grid.setCellWidget(i,j,w)
        for row in record['dues'] if record else [dict(date=doc['due_date'] or doc['date'],kind='normal',amount=str(payable))]:append(row)
        bar=QHBoxLayout();add=QPushButton('Añadir vencimiento');add.clicked.connect(lambda:append());bar.addWidget(add);remove=QPushButton('Retirar seleccionado');bar.addWidget(remove);layout.addLayout(bar)
        def remove_row():
            i=grid.currentRow()
            if i>=0:grid.removeRow(i);ids.pop(i)
        remove.clicked.connect(remove_row)
        form=QFormLayout();layout.addLayout(form);buttons(d,form)
        if d.exec()==QDialog.DialogCode.Accepted:
            rows=[dict(id=ids[i],date=grid.cellWidget(i,0).date().toString('yyyy-MM-dd'),kind=grid.cellWidget(i,1).currentData(),amount=grid.cellWidget(i,2).text().replace(',','.'),note=grid.cellWidget(i,3).text()) for i in range(grid.rowCount())]
            self.host._execute('management.schedule.set',document_id=doc['id'],dues=rows)
    def opening(self):
        from .management_schedule import state
        doc=self.choose(True)
        if doc is None:return
        if QDate.fromString(doc['date'],'yyyy-MM-dd')>QDate.currentDate():self.host._error('La apertura no puede empezar antes de la fecha de la factura.');return
        record=state(self.host.budget)[doc['id']];old=record['opening'];d=QDialog(self);d.setWindowTitle('Inicio del seguimiento del saldo');form=QFormLayout(d)
        day=date_edit(old['date'] if old else None);day.setMinimumDate(QDate.fromString(doc['date'],'yyyy-MM-dd'));day.setMaximumDate(QDate.currentDate())
        paid=QLineEdit(old['paid'] if old else record['source_paid']);note=QLineEdit(old['note'] if old else '');note.setPlaceholderText('Explica el saldo revisado; no es un movimiento de caja')
        for label,w in (('Factura',QLabel(doc['reference'])),('Pagado marcado en origen',QLabel(record['source_paid'])),('Inicio de seguimiento',day),('Importe ya liquidado',paid),('Explicación',note)):form.addRow(label,w)
        buttons(d,form)
        if d.exec()==QDialog.DialogCode.Accepted:self.host._execute('management.opening.set',document_id=doc['id'],date=day.date().toString('yyyy-MM-dd'),paid=paid.text().replace(',','.'),note=note.text())
