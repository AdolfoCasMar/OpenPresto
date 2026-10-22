"""Editable due schedules and explicit opening balances, never cash events."""
import json
from decimal import Decimal
from uuid import uuid4
from .budget import BudgetError
from . import management
from .planning import iso
from .calculations import calculator_for

KEY='management_schedule_v1'


def state(budget):
    try:data=json.loads(budget.project_metadata.get(KEY,'{}'))
    except (TypeError,ValueError) as exc:raise BudgetError('Calendario de vencimientos inválido') from exc
    if not isinstance(data,dict) or len(data)>10000:raise BudgetError('Calendario de vencimientos inválido')
    return data


def validate(budget):
    documents=management.indexed(management.validate(budget)['documents'])
    data=state(budget);policy=calculator_for(budget).policy;count=0
    for identifier,record in data.items():
        doc=documents.get(identifier)
        if doc is None or doc['kind'] not in ('invoice','proforma'):raise BudgetError('Vencimientos sin factura')
        if not isinstance(record,dict) or set(record)!={'dues','source_paid','opening'}:raise BudgetError('Calendario de factura inválido')
        if not isinstance(record['dues'],list) or not 1<=len(record['dues'])<=10000:raise BudgetError('Lista de vencimientos inválida')
        count+=len(record['dues'])
        if count>100000:raise BudgetError('Demasiados vencimientos en el proyecto')
        sums={'normal':Decimal(0),'guarantee':Decimal(0),'fiscal':Decimal(0)};seen=set()
        for row in record['dues']:
            if not isinstance(row,dict) or set(row)!={'id','date','kind','amount','note'}:raise BudgetError('Vencimiento inválido')
            if not isinstance(row['id'],str) or not row['id'] or row['id'] in seen:raise BudgetError('Identificador de vencimiento inválido')
            seen.add(row['id'])
            if row['kind'] not in sums or not isinstance(row['note'],str):raise BudgetError('Tipo o nota de vencimiento inválidos')
            if iso(row['date'])<iso(doc['date']):raise BudgetError('Vencimiento anterior a factura')
            amount=management.number(row['amount'],'Vencimiento')
            if policy.amount(amount)!=amount:raise BudgetError('Precisión de vencimiento inválida')
            sums[row['kind']]+=amount
        _,_,retention,payable=management.document_amounts(budget,doc)
        if sums['normal']!=payable or sums['guarantee']+sums['fiscal']!=retention:
            raise BudgetError('Los vencimientos no concilian con el total y las retenciones de la factura')
        source_paid=management.number(record['source_paid'],'Liquidado en origen')
        if policy.amount(source_paid)!=source_paid or source_paid>payable:raise BudgetError('Saldo pagado de origen inválido')
        opening=record['opening']
        if opening is not None:
            if not isinstance(opening,dict) or set(opening)!={'date','paid','note'} or not isinstance(opening['note'],str) or not opening['note'].strip():raise BudgetError('Apertura sin fecha o explicación')
            if iso(opening['date'])<iso(doc['date']):raise BudgetError('Apertura anterior a factura')
            paid=management.number(opening['paid'],'Saldo liquidado de apertura')
            if policy.amount(paid)!=paid or paid>payable or (paid>0 and doc['status']=='cancelled'):raise BudgetError('Saldo de apertura incompatible con la factura')
    return data


def _write(budget,data):
    previous=dict(budget.project_metadata)
    try:
        budget.project_metadata[KEY]=json.dumps(data,ensure_ascii=False)
        validate(budget)
        from .management_advanced import validate as validate_payments
        validate_payments(budget)
        if 'retention_openings_v1' in budget.project_metadata:
            from .retention_openings import validate as validate_retentions
            validate_retentions(budget)
        if 'retention_settlements_v1' in budget.project_metadata:
            from .retention_settlements import validate as validate_settlements
            validate_settlements(budget)
    except Exception:
        budget.project_metadata.clear();budget.project_metadata.update(previous)
        raise


def set_schedule(budget,document_id,dues):
    if not isinstance(dues,list):raise BudgetError('Lista de vencimientos inválida')
    data=state(budget);old=data.get(document_id)
    normalized=[]
    for row in dues:
        if not isinstance(row,dict) or set(row)-{'id','date','kind','amount','note'}:raise BudgetError('Vencimiento inválido')
        normalized.append(dict(id=row.get('id') or uuid4().hex,date=row.get('date'),kind=row.get('kind'),
                               amount=str(management.number(row.get('amount'),'Vencimiento')),note=row.get('note','')))
    data[document_id]=dict(dues=normalized,source_paid=old['source_paid'] if old else '0',opening=old['opening'] if old else None)
    _write(budget,data)


def set_opening(budget,document_id,date,paid,note):
    data=state(budget)
    if document_id not in data:raise BudgetError('Define primero el calendario de la factura')
    data[document_id]['opening']=dict(date=date,paid=str(management.number(paid,'Saldo liquidado')),note=note)
    _write(budget,data)


def needs_review(budget,document_id):
    record=state(budget).get(document_id)
    return bool(record and record['opening'] is None and Decimal(record['source_paid'])>0)


def due_rows(budget):
    data=validate(budget);docs=management.indexed(management.state(budget)['documents']);result=[]
    for identifier,record in data.items():
        for row in record['dues']:
            result.append((identifier,docs[identifier]['reference'],row['date'],row['kind'],row['amount'],row['note']))
    return sorted(result,key=lambda r:(r[2],r[0],r[3]))


def opening_rows(budget):
    data=validate(budget);docs=management.indexed(management.state(budget)['documents']);result=[]
    for identifier,record in data.items():
        opening=record['opening']
        result.append((identifier,docs[identifier]['reference'],record['source_paid'],opening['date'] if opening else '',
                       opening['paid'] if opening else '', 'Revisar apertura' if opening is None and Decimal(record['source_paid'])>0 else 'Sin liquidación previa' if opening is None else 'Revisada'))
    return result


def forecast_rows(budget):
    """Allocate invoice-level settlements oldest due first; not bank history."""
    data=validate(budget)
    from .management_advanced import settlement_rows
    from .retention_openings import opening_balances
    retention_balances=opening_balances(budget)
    from .retention_settlements import events
    for entry in events(budget,'9999-12-31'):
        if entry['direction']!='out':continue
        paid=retention_balances.setdefault(entry['document_id'],{'guarantee':Decimal(0),'fiscal':Decimal(0)})
        if paid is not None:paid[entry['kind']]+=entry['value']
    settlements={r[0]:r for r in settlement_rows(budget)};result=[]
    for doc in management.state(budget)['documents']:
        if doc['status']!='posted' or doc['kind'] not in ('invoice','proforma'):continue
        record=data.get(doc['id'])
        if record is None:
            if doc['due_date']:result.append((doc['due_date'],doc['kind'],doc['reference'],management.document_amounts(budget,doc)[3]))
            continue
        settled=settlements[doc['id']][6]
        if settled is None:
            result.append((min(r['date'] for r in record['dues']),doc['kind'],doc['reference']+' · revisar apertura',''))
            continue
        retention_paid=retention_balances.get(doc['id'],{'guarantee':Decimal(0),'fiscal':Decimal(0)})
        retention_paid=None if retention_paid is None else dict(retention_paid)
        for due in sorted(record['dues'],key=lambda r:(r['date'],r['id'])):
            amount=Decimal(due['amount'])
            if due['kind']=='normal':
                covered=min(amount,settled);settled-=covered;amount-=covered
            elif retention_paid is None:
                result.append((due['date'],doc['kind'],doc['reference']+' · revisar apertura de retenciones',''));continue
            else:
                covered=min(amount,retention_paid[due['kind']]);retention_paid[due['kind']]-=covered;amount-=covered
            if amount>0:result.append((due['date'],doc['kind'],doc['reference']+(' · retención prevista' if due['kind']!='normal' else ''),amount))
    return sorted(result,key=lambda r:(r[0],r[2]))
