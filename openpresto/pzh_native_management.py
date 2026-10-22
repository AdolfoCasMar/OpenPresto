"""Explicit source-to-draft bridge; never posts historical stock or payments."""
import hashlib
from decimal import Decimal
from .budget import BudgetError
from . import management
from .pzh_operations import validate as source_state, effective_quantities
from .pzh_archive import pzh_source_bytes, pzh_archive_inventory


def _require_complete(data, tables):
    missing = sorted(set(data.get('unsupported', [])) & set(tables))
    if missing:
        raise BudgetError('Conversión nativa bloqueada: tablas PZH incompletas ' + ', '.join(map(str, missing)) + '. Consulta los registros sin convertir.')


def proposal(budget, source_id):
    inventory=pzh_archive_inventory(budget)
    if inventory is None:raise BudgetError('Falta el PZH original conservado')
    plan=_plan(budget,source_id,source_state(budget),'pzh:'+inventory['sha256']+':')
    return plan[-1][1],plan[-1][2]


def _proposal(budget, source_id, data):
    _require_complete(data, (13,14))
    if type(source_id) is not int:raise BudgetError('Identificador PZH inválido')
    doc=next((r for r in data.get('documents',[]) if r['id']==source_id),None)
    if doc is None:raise BudgetError('Documento PZH inexistente')
    if doc['issued']:raise BudgetError('Documento emitido: el módulo actual solo admite compras')
    if doc['proforma'] and doc['kind']!=3:raise BudgetError('Las ofertas y contratos necesitan conversión específica')
    if doc['kind'] not in (1,2,3):raise BudgetError('Tipo de documento no admitido')
    if not doc['date']:raise BudgetError('El documento no tiene fecha de emisión')
    if Decimal(doc['base_difference'] or '1')!=0:raise BudgetError('La base PZH no está conciliada')
    supplier=next((r for r in data.get('entities',[]) if r['code']==doc['entity']),None)
    if supplier is None or not supplier['name'].strip():raise BudgetError('Proveedor sin identificación completa')
    quantities=effective_quantities(data);lines=[]
    for row in data.get('supplies',[]):
        if row.get('documents',{}).get(str(doc['kind']))!=source_id:continue
        if row['code'] not in budget.concepts:raise BudgetError('Suministro PZH sin concepto en el catálogo')
        stock=not any(r.parent_code==row['code'] for r in budget.relations) and budget.concepts[row['code']].nature.casefold()!='mano de obra'
        management.purchase_resource(budget,{'code':row['code'],'stock':stock})
        f=row['fields'];q=quantities[row['id']][0]*Decimal(f.get('12','1'))
        price=Decimal(row['price'])*(1-Decimal(f.get('13','0'))/100)
        lines.append(dict(code=row['code'],quantity=str(q),unit_price=str(price),source_document=None,source_index=None))
        if not stock:lines[-1]['stock']=False
    if not lines:raise BudgetError('Documento sin suministros convertibles')
    invoice=doc['kind']==3
    result=dict(kind='proforma' if doc['proforma'] else {1:'order',2:'delivery',3:'invoice'}[doc['kind']],reference=doc['reference'],
                date=doc['date'],due_date=None,status='draft',lines=lines,
                tax_percent=str(doc['fields'].get('13','0')) if invoice else '0',
                retention_percent=str(Decimal(doc['fields'].get('14','0'))+Decimal(doc['fields'].get('15','0'))) if invoice else '0')
    # A schedule can contain multiple dues and guarantee retentions. Do not
    # collapse it to a guessed date or represent paid states as cash movements.
    base=management.document_amounts(budget,result)[0]
    if base!=Decimal(doc['calculated_base']):raise BudgetError('La base del borrador difiere del PZH')
    return result,supplier


def _origin(doc,row,documents):
    if doc['kind']==3 and '2' in row['documents']:
        identifier=row['documents']['2']
    elif doc['kind'] in (2,3) and '1' in row['documents']:
        identifier=row['documents']['1']
        parent=documents.get(identifier)
        # A quotation is a contract, not a confirmed purchase order.
        if parent and parent['proforma']:return None
    else:return None
    if identifier not in documents:raise BudgetError('Origen documental PZH inexistente')
    if documents[identifier]['kind']>=doc['kind']:raise BudgetError('Orden de documentos PZH incompatible')
    return identifier


def _plan(budget, source_id, data, namespace):
    documents={r['id']:r for r in data.get('documents',[])}
    order=[];finished=set();pending=set()
    def visit(identifier):
        if identifier in finished:return
        if identifier in pending:raise BudgetError('Ciclo de documentos PZH')
        draft,supplier=_proposal(budget,identifier,data);pending.add(identifier)
        doc=documents[identifier]
        supplies=[r for r in data['supplies'] if r['documents'].get(str(doc['kind']))==identifier]
        for line,row in zip(draft['lines'],supplies):
            origin=_origin(doc,row,documents)
            if origin is None:continue
            visit(origin)
            source=documents[origin]
            source_lines=[r for r in data['supplies'] if r['documents'].get(str(source['kind']))==origin]
            matches=[i for i,r in enumerate(source_lines) if r['id']==row['id']]
            if len(matches)!=1:raise BudgetError('Línea de origen PZH sin correspondencia única')
            line.update(source_document=namespace+'document:'+str(origin),source_index=matches[0])
        pending.remove(identifier);finished.add(identifier);order.append((identifier,draft,supplier))
    visit(source_id)
    return order


def copy_document(budget, source_id):
    """Copy the requested document and its required origins, all as drafts."""
    if type(source_id) is not int:raise BudgetError('Identificador PZH inválido')
    original=pzh_source_bytes(budget)
    if original is None:raise BudgetError('Falta el PZH original conservado')
    namespace='pzh:'+hashlib.sha256(original).hexdigest()+':'
    document_id=namespace+'document:'+str(source_id)
    data=management.validate(budget)
    if any(r['id']==document_id for r in data['documents']):return
    plan=_plan(budget,source_id,source_state(budget),namespace)
    previous=dict(budget.project_metadata)
    try:
        for identifier,document,supplier in plan:
            current=management.state(budget)
            native_id=namespace+'document:'+str(identifier)
            supplier_id=namespace+'supplier:'+supplier['code']
            existing=next((r for r in current['documents'] if r['id']==native_id),None)
            if existing:
                if existing['status']=='cancelled' or any(existing[k]!=document[k] for k in ('kind','lines')) or existing['supplier_id']!=supplier_id:
                    raise BudgetError('El documento de origen ya copiado fue modificado; no se sobrescribe ni se enlaza por posición')
                continue
            if not any(r['id']==supplier_id for r in current['suppliers']):
                management.set_supplier(budget,supplier['name'],supplier['contact'],supplier_id)
            management.set_document(budget,supplier_id=supplier_id,document_id=native_id,**document)
    except Exception:
        budget.project_metadata.clear();budget.project_metadata.update(previous)
        raise


def rows(budget):
    result=[];data=source_state(budget)
    inventory=pzh_archive_inventory(budget)
    prefix='pzh:'+inventory['sha256']+':document:' if inventory else None
    existing={r['id']:r for r in management.state(budget)['documents']}
    for doc in data.get('documents',[]):
        if doc['issued'] or doc['kind'] not in (1,2,3) or (doc['kind']==1 and doc['proforma']):continue
        try:
            plan=_plan(budget,doc['id'],data,'pzh:'+(inventory['sha256'] if inventory else 'pending')+':')
            draft=plan[-1][1];status='Borrador disponible';base=management.document_amounts(budget,draft)[0]
            dates={prefix+str(i):existing.get(prefix+str(i),d)['date'] for i,d,_ in plan} if prefix else {}
            review=any(line['source_document'] in dates and dates[line['source_document']]>dates[prefix+str(i)] for i,d,_ in plan for line in d['lines']) if prefix else False
            if prefix and prefix+str(doc['id']) in existing:
                status='Ya copiado · '+{'draft':'borrador','posted':'confirmado','cancelled':'cancelado'}[existing[prefix+str(doc['id'])]['status']]
            if review:status+=' · revisar fechas'
        except BudgetError as exc:status=str(exc);base=''
        result.append((doc['id'],doc['reference'],doc['entity'],base,status))
    return result


def _contract_template(data, source_id):
    if type(source_id) is not int:raise BudgetError('Identificador PZH inválido')
    source=next((d for d in data.get('documents',[]) if d['id']==source_id),None)
    if source is None or source['kind']!=1 or not source['proforma'] or source['issued']:
        raise BudgetError('Selecciona un contrato o una oferta recibida PZH')
    templates=[d for d in data['documents'] if d['kind']==1 and d['proforma']
               and not d['entity'] and not d['issued'] and d['reference']==source['reference']]
    if len(templates)!=1:
        raise BudgetError('Oferta sin plantilla de contrato única' if source['entity'] else 'Referencia de contrato ambigua')
    return templates[0], source


def contract_proposal(budget, source_id, data=None):
    data=source_state(budget) if data is None else data
    _require_complete(data, (13,14))
    parent,_=_contract_template(data,source_id)
    source_id=parent['id']
    quantities=effective_quantities(data);base={};lines=[]
    for row in data['supplies']:
        if row['documents'].get('1')!=source_id:continue
        if row['code'] in base:raise BudgetError('Suministro de contrato repetido: requiere reparto explícito')
        if row['code'] not in budget.concepts:raise BudgetError('Suministro PZH sin concepto en el catálogo')
        stock=not any(r.parent_code==row['code'] for r in budget.relations) and budget.concepts[row['code']].nature.casefold()!='mano de obra'
        q=quantities[row['id']][0]*Decimal(row['fields'].get('12','1'))
        line=dict(code=row['code'],quantity=str(q),stock=stock)
        management.purchase_resource(budget,line);management.number(line['quantity'],'Cantidad')
        base[row['code']]=row;lines.append(line)
    if not lines:raise BudgetError('Contrato sin suministros convertibles')
    contract=dict(title=parent['note'] or parent['reference'],lines=lines,rounding='total')
    entities={r['code']:r for r in data['entities']};offers={}
    for doc in data['documents']:
        if doc['kind']!=1 or not doc['proforma'] or not doc['entity'] or doc['issued'] or doc['reference']!=parent['reference']:continue
        if doc['entity'] in offers or doc['entity'] not in entities:raise BudgetError('Ofertante ambiguo o inexistente')
        prices={}
        for row in data['supplies']:
            if row['documents'].get('1')!=doc['id']:continue
            code=row['code']
            if code not in base or code in prices:raise BudgetError('Oferta con suministros incompatibles')
            source=base[code]
            if quantities[row['id']][0]!=Decimal(source['quantity']):raise BudgetError('La oferta cambia la cantidad del contrato')
            parent_factor=Decimal(source['fields'].get('12','1'))
            factor=Decimal(row['fields'].get('12','1'))
            if parent_factor!=factor:raise BudgetError('La oferta cambia el rendimiento del contrato')
            price=Decimal(row['price'])*(1-Decimal(row['fields'].get('13','0'))/100)
            prices[code]=str(price) if '14' in row['fields'] else None
        # Missing quotation rows remain explicitly unpriced, never fabricated
        # positive prices. The source total must still reconcile below.
        prices={code:prices.get(code) for code in base}
        amount=management.contract_amount(budget,contract,prices)
        if doc['base_difference'] is None or Decimal(doc['base_difference'])!=0 or amount!=Decimal(doc['calculated_base']):
            raise BudgetError('El importe nativo de la oferta no coincide con el PZH')
        offers[doc['entity']]=prices
    chosen=parent['fields'].get('18') or None
    if chosen:
        if chosen not in offers:raise BudgetError('Adjudicatario sin oferta convertida')
        if '20' not in parent['fields']:raise BudgetError('Falta la base adjudicada de origen')
        expected=Decimal(parent['fields']['20']).quantize(Decimal('.01'),rounding='ROUND_HALF_UP')
        if management.contract_amount(budget,contract,offers[chosen])!=expected:
            raise BudgetError('La adjudicación nativa no coincide con el PZH')
    return contract,offers,chosen,entities


def copy_contract(budget, source_id):
    data=source_state(budget)
    _require_complete(data,(13,14))
    parent,requested=_contract_template(data,source_id)
    source_id=parent['id']
    original=pzh_source_bytes(budget)
    if original is None:raise BudgetError('Falta el PZH original conservado')
    namespace='pzh:'+hashlib.sha256(original).hexdigest()+':'
    contract_id=namespace+'contract:'+str(source_id)
    existing=next((r for r in management.validate(budget)['contracts'] if r['id']==contract_id),None)
    if existing is not None:
        if requested['entity'] and namespace+'supplier:'+requested['entity'] not in existing['offers']:
            raise BudgetError('La oferta no está en el contrato nativo existente; se conserva sin sobrescribir')
        return
    contract,offers,chosen,entities=contract_proposal(budget,source_id,data)
    previous=dict(budget.project_metadata)
    try:
        management.set_contract(budget,contract_id=contract_id,**contract)
        for code,prices in offers.items():
            supplier_id=namespace+'supplier:'+code
            if not any(r['id']==supplier_id for r in management.state(budget)['suppliers']):
                management.set_supplier(budget,entities[code]['name'],entities[code]['contact'],supplier_id)
            management.set_offer(budget,contract_id,supplier_id,prices)
        if chosen:management.award_contract(budget,contract_id,namespace+'supplier:'+chosen)
    except Exception:
        budget.project_metadata.clear();budget.project_metadata.update(previous)
        raise


def contract_rows(budget):
    result=[];data=source_state(budget)
    inventory=pzh_archive_inventory(budget);namespace='pzh:'+inventory['sha256']+':' if inventory else ''
    existing={r['id']:r for r in management.state(budget)['contracts']}
    names={r['code']:r['name'] for r in data.get('entities',[])}
    for doc in data.get('documents',[]):
        if doc['kind']!=1 or not doc['proforma'] or doc['issued']:continue
        party=names.get(doc['entity'],doc['entity']) if doc['entity'] else ''
        try:
            parent,_=_contract_template(data,doc['id'])
            contract,offers,chosen,entities=contract_proposal(budget,doc['id'],data)
            native=existing.get(namespace+'contract:'+str(parent['id']))
            if native is None:status='Oferta disponible' if doc['entity'] else 'Contrato disponible'
            elif doc['entity'] and namespace+'supplier:'+doc['entity'] not in native['offers']:
                status='Oferta no incluida en el contrato nativo; se conserva sin sobrescribir'
            else:status='Ya copiado'
            amount=management.contract_amount(budget,contract,offers[chosen]) if chosen else ''
            result.append((doc['id'],doc['reference'],party,contract['title'],len(offers),entities[chosen]['name'] if chosen else 'Sin adjudicar',amount,status))
        except BudgetError as exc:result.append((doc['id'],doc['reference'],party,doc['note'],'','','',str(exc)))
    return result


def copy_dues(budget,source_id):
    if type(source_id) is not int:raise BudgetError('Identificador PZH inválido')
    data=source_state(budget)
    _require_complete(data, (13,14,15))
    doc=next((d for d in data.get('documents',[]) if d['id']==source_id),None)
    if doc is None or doc['kind']!=3 or doc['issued'] or doc['proforma']:
        raise BudgetError('Selecciona una factura recibida en firme')
    if sum(d['kind']==3 and d['reference']==doc['reference'] and d['entity']==doc['entity'] for d in data['documents'])!=1:
        raise BudgetError('Factura de vencimientos ambigua')
    dues=[r for r in data['dues'] if r['reference']==doc['reference'] and r['entity']==doc['entity']]
    if not dues:raise BudgetError('Esta factura no tiene vencimientos en el PZH; no se inventan')
    original=pzh_source_bytes(budget)
    if original is None:raise BudgetError('Falta el PZH original conservado')
    namespace='pzh:'+hashlib.sha256(original).hexdigest()+':'
    native_id=namespace+'document:'+str(source_id)
    from . import management_schedule as schedules
    schedule=schedules.state(budget)
    if native_id in schedule:return
    previous=dict(budget.project_metadata)
    try:
        copy_document(budget,source_id)
        schedule[native_id]=dict(dues=[dict(id=namespace+'due:'+str(row['id']),date=row['date'],
            kind={0:'normal',1:'guarantee',2:'fiscal'}[row['kind']],amount=row['amount'],note=row['note']) for row in dues],
            source_paid=str(sum((Decimal(r['amount']) for r in dues if r['kind']==0 and r['paid']),Decimal(0))),opening=None)
        schedules._write(budget,schedule)
        from .retention_openings import copy_source as copy_retentions
        copy_retentions(budget,native_id,source_id,dues)
    except Exception:
        budget.project_metadata.clear();budget.project_metadata.update(previous)
        raise
