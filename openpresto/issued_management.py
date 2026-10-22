"""Native issued documents and receivables, isolated from procurement and stock."""
from copy import copy
from decimal import Decimal
import hashlib
import json
from uuid import uuid4
from .budget import BudgetError
from .planning import iso
from . import management

KEY='issued_management_v1'


def state(budget):
    try:
        data=json.loads(budget.project_metadata.get(KEY,'{"customers":[],"documents":[],"receipts":[],"source_states":{},"openings":{}}'))
        if not isinstance(data,dict) or set(data)!={'customers','documents','receipts','source_states','openings'}:raise ValueError('estructura')
        if any(not isinstance(data[k],list) or len(data[k])>10000 for k in ('customers','documents','receipts')):raise ValueError('listas')
        if any(not isinstance(data[k],dict) or len(data[k])>10000 for k in ('source_states','openings')):raise ValueError('saldos')
        return data
    except (ValueError,TypeError) as exc:raise BudgetError('Gestión emitida inválida') from exc


def _shadow(budget,data):
    shadow=copy(budget);shadow.project_metadata=dict(budget.project_metadata)
    # Purchase retention records refer to the real purchase graph, not this sales adapter.
    shadow.project_metadata.pop('retention_openings_v1',None)
    shadow.project_metadata.pop('issued_retention_openings_v1',None)
    shadow.project_metadata.pop('retention_settlements_v1',None)
    if any(not isinstance(row,dict) or 'customer_id' not in row or 'supplier_id' in row for row in data['documents']):raise BudgetError('Documento emitido sin cliente válido')
    documents=[dict((('supplier_id' if k=='customer_id' else k),v) for k,v in row.items()) for row in data['documents']]
    shadow.project_metadata[management.KEY]=json.dumps(dict(suppliers=data['customers'],documents=documents,contracts=[],consumptions=[]))
    return shadow


def _sync(data,shadow):
    native=management.state(shadow)
    data['customers']=native['suppliers']
    data['documents']=[dict((('customer_id' if k=='supplier_id' else k),v) for k,v in row.items()) for row in native['documents']]


def money(value):
    result=management.number(value,'Importe')
    if result!=result.quantize(Decimal('.01')):raise BudgetError('El importe debe tener precisión de céntimos')
    return result


def amounts(budget,document):
    return management.document_amounts(budget,document)


def validate(budget,data=None):
    data=state(budget) if data is None else data
    management.validate(_shadow(budget,data))
    docs=management.indexed(data['documents'])
    for row in docs.values():
        if any(line.get('stock') is not False for line in row['lines']):raise BudgetError('Las ventas no generan existencias ni compras')
    for rid,source in data['source_states'].items():
        if rid not in docs or not isinstance(source,dict) or set(source)!={'paid','pending','dues'} or not isinstance(source['dues'],list) or len(source['dues'])>100000:raise BudgetError('Saldo de origen emitido inválido')
        money(source['paid']);money(source['pending'])
        for due in source['dues']:
            if not isinstance(due,dict) or set(due)!={'date','kind','paid','amount','note'} or type(due['kind']) is not int or due['kind'] not in (0,1,2) or type(due['paid']) is not bool or not isinstance(due['note'],str):raise BudgetError('Vencimiento emitido inválido')
            if due['date'] is not None:iso(due['date'])
            money(due['amount'])
    allocated={}
    for rid,opening in data['openings'].items():
        if rid not in docs or not isinstance(opening,dict) or set(opening)!={'date','amount'}:raise BudgetError('Apertura emitida inválida')
        doc=docs[rid]
        if doc['kind']!='invoice' or doc['status']!='posted' or iso(opening['date'])<iso(doc['date']):raise BudgetError('La apertura requiere una factura confirmada y una fecha posterior')
        allocated[rid]=money(opening['amount'])
    for receipt in management.indexed(data['receipts']).values():
        if set(receipt)!={'id','document_id','date','amount','reference'} or not isinstance(receipt['reference'],str):raise BudgetError('Cobro inválido')
        doc=docs.get(receipt['document_id'])
        if doc is None or doc['kind']!='invoice' or doc['status']!='posted':raise BudgetError('El cobro requiere una factura confirmada')
        if iso(receipt['date'])<iso(doc['date']):raise BudgetError('El cobro es anterior a la factura')
        opening=data['openings'].get(doc['id'])
        if opening and iso(receipt['date'])<iso(opening['date']):raise BudgetError('Cobro anterior al inicio del seguimiento')
        amount=money(receipt['amount'])
        if amount<=0:raise BudgetError('Cobro no positivo')
        allocated[doc['id']]=allocated.get(doc['id'],Decimal(0))+amount
    for rid,paid in allocated.items():
        if paid>amounts(budget,docs[rid])[3]:raise BudgetError('El cobro supera el saldo de la factura')
    return data


def _save(budget,data):
    validate(budget,data)
    previous=dict(budget.project_metadata)
    try:
        budget.project_metadata[KEY]=json.dumps(data,ensure_ascii=False)
        if any(row['kind']=='proforma' and any(line['source_document'] for line in row['lines']) for row in data['documents']):
            budget.project_metadata['linked_proformas_v1']='1'
        if 'issued_retention_openings_v1' in budget.project_metadata:
            from .issued_retention_openings import validate as validate_retentions
            validate_retentions(budget)
        if 'retention_settlements_v1' in budget.project_metadata:
            from .retention_settlements import validate as validate_settlements
            validate_settlements(budget)
    except Exception:
        budget.project_metadata.clear();budget.project_metadata.update(previous)
        raise


def set_customer(budget,name,contact='',customer_id=None):
    data=state(budget);shadow=_shadow(budget,data)
    management.set_supplier(shadow,name,contact,customer_id)
    _sync(data,shadow);_save(budget,data)


def set_document(budget,kind,reference,customer_id,date,lines,tax_percent='0',retention_percent='0',due_date=None,status='draft',document_id=None,rounding=None):
    data=state(budget);shadow=_shadow(budget,data)
    lines=[dict(line,stock=False) for line in lines]
    management.set_document(shadow,kind,reference,customer_id,date,lines,tax_percent,retention_percent,due_date,status,document_id,rounding)
    _sync(data,shadow);_save(budget,data)


def set_status(budget,document_id,status):
    data=state(budget);shadow=_shadow(budget,data)
    management.set_document_status(shadow,document_id,status)
    _sync(data,shadow);_save(budget,data)


def record_receipt(budget,document_id,date,amount,reference='',receipt_id=None):
    data=state(budget)
    source=data['source_states'].get(document_id)
    if source and money(source['paid']) and document_id not in data['openings']:
        raise BudgetError('Revisa primero el saldo cobrado en origen y acepta una apertura; no se duplica como cobro fechado')
    data['receipts'].append(dict(id=receipt_id or uuid4().hex,document_id=document_id,date=date,amount=str(money(amount)),reference=reference))
    _save(budget,data)



def cancel_receipt(budget,receipt_id):
    data=state(budget)
    if not any(r['id']==receipt_id for r in data['receipts']):raise BudgetError('Cobro inexistente')
    data['receipts']=[r for r in data['receipts'] if r['id']!=receipt_id];_save(budget,data)


def accept_opening(budget,document_id,date):
    data=state(budget);source=data['source_states'].get(document_id)
    if source is None:raise BudgetError('La factura no conserva un saldo de origen')
    if document_id in data['openings']:raise BudgetError('La apertura ya está aceptada')
    if any(r['document_id']==document_id for r in data['receipts']):raise BudgetError('Acepta la apertura antes de registrar cobros')
    data['openings'][document_id]=dict(date=date,amount=source['paid']);_save(budget,data)


def cancel_opening(budget,document_id):
    data=state(budget)
    if document_id not in data['openings']:raise BudgetError('Apertura inexistente')
    if any(r['document_id']==document_id for r in data['receipts']):raise BudgetError('Anula los cobros posteriores antes de retirar la apertura')
    del data['openings'][document_id];_save(budget,data)


def _source_proposal(budget,source_id):
    from .pzh_operations import validate as source_state,effective_quantities
    from .pzh_native_management import _require_complete
    data=source_state(budget);_require_complete(data,(13,14))
    doc=next((r for r in data.get('documents',[]) if r['id']==source_id),None)
    if doc is None or not doc['issued']:raise BudgetError('Selecciona un documento emitido')
    if doc['kind'] not in (1,2,3) or (doc['proforma'] and doc['kind']!=3):raise BudgetError('Tipo emitido fuera del perfil admitido')
    if not doc['date']:raise BudgetError('Documento emitido sin fecha')
    if doc['base_difference'] is None or Decimal(doc['base_difference'])!=0:raise BudgetError('Base emitida sin conciliar')
    customers=[r for r in data['entities'] if r['code']==doc['entity']]
    if len(customers)!=1 or not customers[0]['name'].strip():raise BudgetError('Cliente sin identificación única')
    quantities=effective_quantities(data);lines=[]
    for row in data['supplies']:
        if row['documents'].get(str(doc['kind']))!=source_id:continue
        management.purchase_resource(budget,dict(code=row['code'],stock=False))
        f=row['fields'];quantity=quantities[row['id']][0]*Decimal(f.get('12','1'))
        price=Decimal(row['price'])*(1-Decimal(f.get('13','0'))/100)
        lines.append(dict(code=row['code'],quantity=str(quantity),unit_price=str(price),source_document=None,source_index=None,stock=False))
    if not lines:raise BudgetError('Documento sin líneas convertibles')
    result=dict(kind='proforma' if doc['proforma'] else {1:'order',2:'delivery',3:'invoice'}[doc['kind']],reference=doc['reference'],date=doc['date'],due_date=None,status='draft',lines=lines,tax_percent=str(doc['fields'].get('13','0')) if doc['kind']==3 else '0',retention_percent=str(Decimal(doc['fields'].get('14','0'))+Decimal(doc['fields'].get('15','0'))) if doc['kind']==3 else '0')
    if amounts(budget,result)[0]!=Decimal(doc['calculated_base']):raise BudgetError('La copia emitida cambia la base de origen')
    return result,customers[0]


def _source_plan(budget,source_id):
    from .pzh_archive import pzh_archive_inventory
    from .pzh_operations import validate as source_state
    from .pzh_native_management import _origin
    if type(source_id) is not int:raise BudgetError('Identificador PZH inválido')
    inventory=pzh_archive_inventory(budget)
    if inventory is None:raise BudgetError('Falta el original PZH')
    prefix='pzh:'+inventory['sha256']+':issued:'
    source=source_state(budget);documents={r['id']:r for r in source['documents']}
    plan=[];visiting=set();finished=set()
    def visit(identifier):
        if identifier in finished:return
        if identifier in visiting:raise BudgetError('Ciclo de documentos emitidos PZH')
        draft,customer=_source_proposal(budget,identifier)
        visiting.add(identifier);doc=documents[identifier]
        supplies=[r for r in source['supplies'] if r['documents'].get(str(doc['kind']))==identifier]
        for line,row in zip(draft['lines'],supplies):
            origin=_origin(doc,row,documents)
            if origin is None:continue
            parent=documents[origin]
            if not parent['issued'] or parent['entity']!=doc['entity']:
                raise BudgetError('El antecedente no pertenece al mismo cliente y circuito emitido')
            visit(origin)
            previous=[r for r in source['supplies'] if r['documents'].get(str(parent['kind']))==origin]
            matches=[i for i,r in enumerate(previous) if r['id']==row['id']]
            if len(matches)!=1:raise BudgetError('Línea emitida sin correspondencia única en el antecedente')
            line.update(source_document=prefix+'document:'+str(origin),source_index=matches[0])
        visiting.remove(identifier);finished.add(identifier);plan.append((identifier,draft,customer))
    visit(source_id)
    return prefix,plan


def source_proposal(budget,source_id):
    _,plan=_source_plan(budget,source_id)
    return plan[-1][1],plan[-1][2]


def copy_source(budget,source_id):
    prefix,plan=_source_plan(budget,source_id)
    existing={r['id']:r for r in state(budget)['documents']}
    if prefix+'document:'+str(source_id) in existing:return
    shadow=copy(budget);shadow.project_metadata=dict(budget.project_metadata)
    for identifier,draft,customer in plan:
        row=existing.get(prefix+'document:'+str(identifier))
        if row is not None:
            if row['status']=='cancelled' or any(row[k]!=draft[k] for k in ('kind','lines')) or row['customer_id']!=prefix+'customer:'+customer['code']:
                raise BudgetError('El antecedente emitido ya copiado fue modificado; no se sobrescribe ni se enlaza por posición')
            continue
        _copy_source_single(shadow,identifier,draft,customer)
    validate(shadow)
    budget.project_metadata.clear();budget.project_metadata.update(shadow.project_metadata)


def _copy_source_single(budget,source_id,proposal,customer):
    from .pzh_archive import pzh_source_bytes
    from .pzh_operations import validate as source_state
    raw=pzh_source_bytes(budget)
    if raw is None:raise BudgetError('Falta el original PZH')
    prefix='pzh:'+hashlib.sha256(raw).hexdigest()+':issued:'
    rid=prefix+'document:'+str(source_id);data=state(budget)
    if any(r['id']==rid for r in data['documents']):return
    shadow=copy(budget);shadow.project_metadata=dict(budget.project_metadata)
    cid=prefix+'customer:'+customer['code']
    if not any(r['id']==cid for r in data['customers']):set_customer(shadow,customer['name'],customer['contact'],cid)
    set_document(shadow,customer_id=cid,document_id=rid,**proposal)
    data=state(shadow);source=source_state(budget)
    doc=next(d for d in source['documents'] if d['id']==source_id)
    matches=[d for d in source['documents'] if d['kind']==3 and (d['reference'],d['entity'])==(doc['reference'],doc['entity'])]
    if doc['kind']==3 and not doc['proforma'] and len(matches)==1 and 15 not in source['unsupported']:
        dues=[{k:r[k] for k in ('date','kind','paid','amount','note')} for r in source['dues'] if (r['reference'],r['entity'])==(doc['reference'],doc['entity'])]
        paid=sum((Decimal(r['amount']) for r in dues if r['kind']==0 and r['paid']),Decimal(0))
        pending=sum((Decimal(r['amount']) for r in dues if r['kind']==0 and not r['paid']),Decimal(0))
        # Ordinary due states must reconcile with the net invoice; retentions remain separate.
        if dues:
            if paid+pending!=amounts(budget,next(r for r in data['documents'] if r['id']==rid))[3]:raise BudgetError('Los vencimientos emitidos no concilian con el neto; requiere revisión')
            data['source_states'][rid]=dict(paid=str(paid),pending=str(pending),dues=dues)
    if doc['kind']==3 and not doc['proforma'] and rid not in data['source_states'] and any(Decimal(doc['fields'].get(key,'0'))!=0 for key in ('7','16')):
        raise BudgetError('Factura con estados de cobro sin vencimientos conciliables; se conserva en origen para revisión')
    _save(budget,data)
    from .issued_retention_openings import copy_source as copy_retentions
    copy_retentions(budget,rid)


def document_rows(budget):
    data=validate(budget);names={r['id']:r['name'] for r in data['customers']};rows=[]
    for doc in data['documents']:
        source=data['source_states'].get(doc['id'],{});opening=data['openings'].get(doc['id'],{})
        received=sum((Decimal(r['amount']) for r in data['receipts'] if r['document_id']==doc['id']),Decimal(0))
        total=amounts(budget,doc)[3];historical=Decimal(opening.get('amount','0'))
        rows.append((doc['id'],doc['kind'],doc['reference'],names[doc['customer_id']],doc['date'],doc['status'],*amounts(budget,doc),received,historical,total-received-historical if doc['kind']=='invoice' and doc['status']=='posted' else '',source.get('paid',''),'Revisar apertura' if source and money(source['paid']) and not opening else ''))
    return rows


def source_rows(budget):
    from .pzh_operations import validate as source_state
    from .pzh_archive import pzh_archive_inventory
    inventory=pzh_archive_inventory(budget)
    prefix='pzh:'+inventory['sha256']+':issued:document:' if inventory else ''
    existing={r['id']:r for r in state(budget)['documents']}
    result=[]
    for doc in source_state(budget).get('documents',[]):
        if not doc['issued'] or doc['kind'] not in (1,2,3):continue
        try:
            proposed,_=source_proposal(budget,doc['id']);status='Disponible como borrador';base=amounts(budget,proposed)[0]
            if prefix+str(doc['id']) in existing:status='Ya copiado · '+{'draft':'Borrador','posted':'Confirmado','cancelled':'Cancelado'}[existing[prefix+str(doc['id'])]['status']]
        except (BudgetError,ArithmeticError) as exc:status=str(exc);base=''
        result.append((doc['id'],doc['reference'],doc['date'] or '',doc['proforma'],base,status))
    return result
