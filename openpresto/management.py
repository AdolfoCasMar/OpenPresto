"""Native procurement and execution with explicit document links and stock.

OpenPresto's own bounded model: no inferred proprietary PZH fields or tax rates.
"""
import json
from uuid import uuid4
from decimal import Decimal
from .budget import BudgetError, _decimal, special_price_kind
from .planning import iso
from .calculations import calculator_for

KEY = 'management_v1'


def state(budget):
    try:
        data = json.loads(budget.project_metadata.get(KEY,'{"suppliers":[],"contracts":[],"documents":[],"consumptions":[]}'))
        if not isinstance(data,dict) or set(data) != {'suppliers','contracts','documents','consumptions'} or any(not isinstance(v,list) or len(v)>10000 for v in data.values()):
            raise BudgetError('Gestión inválida')
        return data
    except (ValueError,TypeError) as exc:
        raise BudgetError('Gestión inválida: '+str(exc)) from exc


def number(value, label):
    result = _decimal(value,label)
    if result < 0:
        raise BudgetError(label+' no puede ser negativo')
    return result


def resource(budget, code, *, parents=None):
    if code not in budget.concepts or special_price_kind(code) or (code in parents if parents is not None else any(r.parent_code==code for r in budget.relations)):
        raise BudgetError('El suministro debe ser un concepto básico existente: '+str(code))


def purchase_resource(budget, line, *, parents=None):
    """A composed work item can be procured as a non-stock service only."""
    stock=line.get('stock',True)
    if type(stock) is not bool:raise BudgetError('Indicador de existencias inválido')
    code=line['code']
    if stock:
        resource(budget,code,parents=parents);return
    if code not in budget.concepts or special_price_kind(code) or code==budget.root_code:
        raise BudgetError('Trabajo contratado inexistente o especial')
    concept=budget.concepts[code]
    if concept.nature.casefold() in ('capitulo','capítulo'):
        raise BudgetError('Un capítulo no es un trabajo contratable')


def indexed(rows):
    result = {}
    for row in rows:
        if not isinstance(row,dict) or not isinstance(row.get('id'),str) or not row['id'] or row['id'] in result:
            raise BudgetError('Identificador de gestión inválido o repetido')
        result[row['id']] = row
    return result


def validate(budget):
    return validate_with_ledger(budget)[0]


def validate_with_ledger(budget):
    """Return validated data and its ledger from one read-only evaluation."""
    data = state(budget)
    parents = ({relation.parent_code for relation in budget.relations}
               if data['contracts'] or data['documents'] or data['consumptions'] else set())
    suppliers,contracts,documents,consumptions = [indexed(data[key]) for key in ('suppliers','contracts','documents','consumptions')]
    for row in suppliers.values():
        if set(row) != {'id','name','contact'} or not isinstance(row['name'],str) or not row['name'].strip() or not isinstance(row['contact'],str):
            raise BudgetError('Proveedor inválido')
    for row in contracts.values():
        if set(row) not in ({'id','title','lines','offers','award'},{'id','title','lines','offers','award','rounding'}) or row.get('rounding','line') not in ('line','total') or not isinstance(row['title'],str) or not row['title'].strip() or not isinstance(row['lines'],list) or not row['lines'] or not isinstance(row['offers'],dict):
            raise BudgetError('Contrato inválido')
        seen = set()
        for line in row['lines']:
            if not isinstance(line,dict) or set(line) not in ({'code','quantity'},{'code','quantity','stock'}) or line['code'] in seen:
                raise BudgetError('Suministro de contrato inválido o repetido')
            purchase_resource(budget,line,parents=parents);number(line['quantity'],'Cantidad contratada');seen.add(line['code'])
        for supplier,prices in row['offers'].items():
            if supplier not in suppliers or not isinstance(prices,dict) or set(prices)-seen:
                raise BudgetError('Oferta sin proveedor o suministro válido')
            for price in prices.values():
                if price is not None:number(price,'Precio ofertado')
        award = row['award']
        if award is not None:
            if not isinstance(award,dict) or set(award) != {'supplier_id','prices'} or award['supplier_id'] not in suppliers or set(award['prices']) != seen:
                raise BudgetError('Adjudicación inválida')
            for price in award['prices'].values():number(price,'Precio adjudicado')
    used = {}
    references = set()
    for row in documents.values():
        columns={'id','kind','reference','supplier_id','date','due_date','status','lines','tax_percent','retention_percent'}
        if set(row) not in (columns,columns|{'rounding'}) or row.get('rounding','line') not in ('line','total'):
            raise BudgetError('Documento inválido')
        if row['kind'] not in ('order','delivery','invoice','proforma') or row['status'] not in ('draft','posted','cancelled') or row['supplier_id'] not in suppliers or not isinstance(row['reference'],str) or not row['reference'].strip() or not isinstance(row['lines'],list) or not row['lines']:
            raise BudgetError('Tipo, estado o proveedor de documento inválidos')
        iso(row['date'])
        if row['status']=='posted':
            reference=(row['kind'],row['supplier_id'],row['date'][:4],row['reference'].strip().casefold())
            if reference in references:raise BudgetError('Referencia documental confirmada repetida para ese proveedor y año')
            references.add(reference)
        if row['due_date'] is not None and iso(row['due_date']) < iso(row['date']):
            raise BudgetError('El vencimiento no puede ser anterior al documento')
        for key in ('tax_percent','retention_percent'):
            if number(row[key],key)>100:raise BudgetError('El porcentaje debe estar entre 0 y 100')
            if row['kind'] not in ('invoice','proforma') and number(row[key],key)!=0:raise BudgetError('Impuestos y retenciones solo en facturas o proformas')
        for line in row['lines']:
            if not isinstance(line,dict) or set(line) not in ({'code','quantity','unit_price','source_document','source_index'},{'code','quantity','unit_price','source_document','source_index','stock'}):
                raise BudgetError('Línea documental inválida')
            purchase_resource(budget,line,parents=parents);number(line['unit_price'],'Precio documental')
            if line['quantity'] is not None:number(line['quantity'],'Cantidad documental')
            source_id,index = line['source_document'],line['source_index']
            if source_id is None:
                if index is not None:raise BudgetError('Índice sin documento de origen')
                continue
            source = documents.get(source_id)
            if source is None or source_id==row['id'] or type(index) is not int or not 0 <= index < len(source['lines']):
                raise BudgetError('Vínculo documental inexistente')
            if (source['kind'],row['kind']) not in (('order','delivery'),('order','invoice'),('delivery','invoice'),('order','proforma'),('delivery','proforma')):
                raise BudgetError('Enlace documental no admitido')
            previous = source['lines'][index]
            source_ready=source['status']=='posted' or row['status']=='cancelled' or (source['status']=='draft' and row['status']=='draft')
            if not source_ready or source['supplier_id']!=row['supplier_id'] or previous['code']!=line['code'] or previous.get('stock',True)!=line.get('stock',True) or (row['status']=='posted' and iso(source['date'])>iso(row['date'])) or previous['quantity'] is None or line['quantity'] is None:
                raise BudgetError('Documento de origen incompatible, sin contabilizar o posterior')
            if row['status']=='posted' and row['kind']!='proforma':
                # Proformas forecast costs without consuming an order/delivery balance.
                # Direct invoices against an order and deliveries consume the same order balance.
                key = source_id,index
                used[key] = used.get(key,Decimal(0))+number(line['quantity'],'Cantidad vinculada')
                if used[key]>number(previous['quantity'],'Cantidad de origen'):
                    raise BudgetError('Las cantidades vinculadas superan la cantidad del documento de origen')
    for row in consumptions.values():
        if set(row) != {'id','code','date','quantity','destination'} or not isinstance(row['destination'],str) or not row['destination'].strip():
            raise BudgetError('Consumo inválido')
        resource(budget,row['code'],parents=parents);iso(row['date']);number(row['quantity'],'Cantidad consumida')
    return data, ledger(budget,data)


def write(budget,data):
    previous=dict(budget.project_metadata)
    try:
        budget.project_metadata[KEY] = json.dumps(data,ensure_ascii=False)
        documents=indexed(data['documents'])
        if any(row['kind']=='proforma' and any(line['source_document'] for line in row['lines']) for row in documents.values()):
            budget.project_metadata['linked_proformas_v1']='1'
        if any(row['status']=='draft' and any(line['source_document'] in documents and documents[line['source_document']]['status']=='draft' for line in row['lines']) for row in documents.values()):
            budget.project_metadata['management_linked_drafts_v1']='1'
        if any('stock' in line for key in ('documents','contracts') for row in data[key] for line in row['lines']):
            budget.project_metadata['management_services_v1']='1'
        if any('rounding' in row for key in ('contracts','documents') for row in data[key]):
            budget.project_metadata['management_pricing_v1']='1'
        validate(budget)
        if 'retention_openings_v1' in budget.project_metadata:
            from .retention_openings import validate as validate_retentions
            validate_retentions(budget)
        if 'retention_settlements_v1' in budget.project_metadata:
            from .retention_settlements import validate as validate_settlements
            validate_settlements(budget)
    except Exception:
        budget.project_metadata.clear();budget.project_metadata.update(previous)
        raise


def set_supplier(budget, name, contact='', supplier_id=None):
    data = state(budget)
    rid = supplier_id or uuid4().hex
    data['suppliers'] = [r for r in data['suppliers'] if r['id']!=rid]+[{'id':rid,'name':name,'contact':contact}]
    write(budget,data)


def set_contract(budget, title, lines, contract_id=None, rounding=None):
    data = state(budget);rid=contract_id or uuid4().hex
    old = next((r for r in data['contracts'] if r['id']==rid),None)
    if old and old['award'] is not None:raise BudgetError('Un contrato adjudicado no admite modificar sus suministros')
    if rounding is None:rounding=old.get('rounding','line') if old else 'line'
    row = {'id':rid,'title':title,'lines':lines,'offers':old['offers'] if old else {},'award':None}
    if rounding!='line' or (old and 'rounding' in old):row['rounding']=rounding
    data['contracts'] = [r for r in data['contracts'] if r['id']!=rid]+[row]
    write(budget,data)


def set_offer(budget, contract_id, supplier_id, prices):
    data = state(budget)
    row = next((r for r in data['contracts'] if r['id']==contract_id),None)
    if row is None:raise BudgetError('Contrato inexistente')
    row['offers'][supplier_id] = prices
    write(budget,data)


def award_contract(budget, contract_id, supplier_id):
    data = state(budget)
    row = next((r for r in data['contracts'] if r['id']==contract_id),None)
    if row is None or supplier_id not in row['offers']:raise BudgetError('Oferta inexistente')
    offer = row['offers'][supplier_id]
    if set(offer) != {line['code'] for line in row['lines']}:
        raise BudgetError('Completa los precios de todos los suministros; usa nulo explícito para no ofertado')
    row['award'] = {'supplier_id':supplier_id,'prices':{code:'0' if price is None else str(number(price,'Precio ofertado')) for code,price in offer.items()}}
    write(budget,data)


def set_document(budget, kind, reference, supplier_id, date, lines, tax_percent='0', retention_percent='0', due_date=None, status='draft', document_id=None, rounding=None):
    data = state(budget);rid=document_id or uuid4().hex
    old = next((r for r in data['documents'] if r['id']==rid),None)
    if old and old['status']!='draft':raise BudgetError('Un documento confirmado no se edita; cancélalo explícitamente')
    if rounding is None:rounding=old.get('rounding','line') if old else 'line'
    data['documents'] = [r for r in data['documents'] if r['id']!=rid]+[{'id':rid,'kind':kind,'reference':reference,
        'supplier_id':supplier_id,'date':date,'due_date':due_date,'status':status,'lines':lines,
        'tax_percent':str(number(tax_percent,'Impuesto')),'retention_percent':str(number(retention_percent,'Retención'))}]
    if rounding!='line' or (old and 'rounding' in old):data['documents'][-1]['rounding']=rounding
    write(budget,data)


def set_document_status(budget, document_id, status):
    data = state(budget)
    row = next((r for r in data['documents'] if r['id']==document_id),None)
    if row is None or (row['status'],status) not in (('draft','posted'),('draft','cancelled'),('posted','cancelled')):
        raise BudgetError('Transición documental no admitida')
    row['status']=status
    write(budget,data)


def consume(budget, code, date, quantity, destination, consumption_id=None):
    data = state(budget);rid=consumption_id or uuid4().hex
    if any(r['id']==rid for r in data['consumptions']):raise BudgetError('Consumo repetido')
    data['consumptions'].append({'id':rid,'code':code,'date':date,'quantity':str(number(quantity,'Consumo')),'destination':destination})
    write(budget,data)


def document_amounts(budget,row):
    policy=calculator_for(budget).policy
    base=sum(document_line_amounts(budget,row),Decimal(0))
    tax=policy.amount(base*number(row['tax_percent'],'Impuesto')/100)
    retention=policy.amount(base*number(row['retention_percent'],'Retención')/100)
    return base,tax,retention,policy.amount(base+tax-retention)


def document_line_amounts(budget,row):
    """Allocate total rounding monotonically, keeping cents and stock aligned."""
    policy=calculator_for(budget).policy;result=[];cumulative=Decimal(0);previous=Decimal(0)
    for line in row['lines']:
        raw=number(line['unit_price'],'Precio')*(Decimal(1) if line['quantity'] is None else number(line['quantity'],'Cantidad'))
        if row.get('rounding','line')=='total':
            cumulative+=raw;rounded=policy.amount(cumulative);result.append(rounded-previous);previous=rounded
        else:result.append(policy.amount(raw))
    return result


def ledger(budget,data=None):
    data=state(budget) if data is None else data
    documents=indexed(data['documents']);events=[]
    policy=calculator_for(budget).policy
    for row in documents.values():
        if row['status']!='posted' or row['kind'] not in ('delivery','invoice'):continue
        costs=document_line_amounts(budget,row)
        for i,line in enumerate(row['lines']):
            if not line.get('stock',True):continue
            if line['quantity'] is None:continue
            source=documents.get(line['source_document'])
            if row['kind']=='invoice' and source and source['kind']=='delivery':continue
            q=number(line['quantity'],'Cantidad adquirida')
            if q==0:continue
            events.append((row['date'],0,row['id']+str(i),line['code'],q,costs[i],row['reference']))
    for row in data['consumptions']:
        events.append((row['date'],1,row['id'],row['code'],number(row['quantity'],'Consumo'),Decimal(0),row['destination']))
    stocks,values={},{}
    result=[]
    for day,kind,identity,code,quantity,cost,reference in sorted(events):
        available=stocks.get(code,Decimal(0));value=values.get(code,Decimal(0))
        if kind:
            if quantity>available:raise BudgetError('Consumo superior a existencias disponibles en '+day+': '+code)
            cost=policy.amount(value*quantity/available) if available else Decimal(0)
            stocks[code]=available-quantity;values[code]=value-cost
        else:
            stocks[code]=available+quantity;values[code]=value+cost
        result.append((day,code,'Consumo' if kind else 'Entrada',reference,quantity,cost,stocks[code],values[code]))
    return result


def document_rows(budget):
    return [(r['id'],r['kind'],r['reference'],r['date'],r['supplier_id'],r['status'],*document_amounts(budget,r)) for r in validate(budget)['documents']]


def cash_rows(budget):
    if 'management_schedule_v1' in budget.project_metadata:
        from .management_schedule import forecast_rows
        return forecast_rows(budget)
    return [(r['due_date'],r['kind'],r['reference'],document_amounts(budget,r)[3]) for r in validate(budget)['documents']
            if r['status']=='posted' and r['kind'] in ('invoice','proforma') and r['due_date']]

def remaining_source_lines(budget, document_id):
    data=validate(budget);documents=indexed(data['documents']);source=documents.get(document_id)
    if source is None or source['status']!='posted' or source['kind'] not in ('order','delivery'):
        raise BudgetError('Selecciona un pedido o albarán confirmado')
    used={}
    for row in documents.values():
        if row['status']!='posted' or row['kind']=='proforma':continue
        for line in row['lines']:
            if line['source_document']==document_id:
                used[line['source_index']]=used.get(line['source_index'],Decimal(0))+number(line['quantity'],'Cantidad vinculada')
    result=[]
    for index,line in enumerate(source['lines']):
        if line['quantity'] is None:continue
        remaining=number(line['quantity'],'Cantidad origen')-used.get(index,Decimal(0))
        if remaining>0:
            result.append(dict(line,quantity=str(remaining),source_document=document_id,source_index=index))
    return result


def contract_order_lines(budget, contract_id):
    contract=next((r for r in validate(budget)['contracts'] if r['id']==contract_id),None)
    if contract is None or contract['award'] is None:raise BudgetError('Selecciona un contrato adjudicado')
    return [dict(line,unit_price=contract['award']['prices'][line['code']],source_document=None,source_index=None) for line in contract['lines']]

def contract_rows(budget):
    data=validate(budget);names={r['id']:r['name'] for r in data['suppliers']};policy=calculator_for(budget).policy
    return [(r['title'],len(r['lines']),len(r['offers']),names[r['award']['supplier_id']] if r['award'] else 'Sin adjudicar',
        contract_amount(budget,r,r['award']['prices']) if r['award'] else '') for r in data['contracts']]


def contract_amount(budget, contract, prices):
    policy=calculator_for(budget).policy
    amounts=[number(line['quantity'],'Cantidad')*number(prices.get(line['code']) or '0','Precio') for line in contract['lines']]
    if contract.get('rounding','line')=='total':return policy.amount(sum(amounts,Decimal(0)))
    return sum((policy.amount(value) for value in amounts),Decimal(0))


def offer_rows(budget):
    data=validate(budget);names={r['id']:r['name'] for r in data['suppliers']};result=[]
    for contract in data['contracts']:
        for supplier,prices in contract['offers'].items():
            missing=sum(prices.get(line['code']) is None for line in contract['lines'])
            awarded=contract['award'] is not None and contract['award']['supplier_id']==supplier
            snapshot=contract_amount(budget,contract,contract['award']['prices']) if awarded else ''
            result.append((contract['title'],names[supplier],missing,contract_amount(budget,contract,prices),awarded,snapshot))
    return result
