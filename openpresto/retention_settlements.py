"""Explicit dated retention payments/receipts, separate from ordinary invoice net."""
import json
from decimal import Decimal
from uuid import uuid4
from .budget import BudgetError
from .planning import iso
from .calculations import calculator_for
from . import management,management_schedule,issued_management,retention_openings,issued_retention_openings

KEY='retention_settlements_v1'
HEADERS=('ID','Circuito','Factura','Tipo','Fecha real','Importe','Referencia','Estado','Anulación','Motivo')


def contexts(budget):
    purchases=management.validate(budget);sales=issued_management.validate(budget);schedules=management_schedule.validate(budget)
    received=retention_openings.validate(budget);issued=issued_retention_openings.validate(budget);result={}
    for direction,docs in (('out',purchases['documents']),('in',sales['documents'])):
        for doc in docs:
            if doc['kind']!='invoice':continue
            if direction=='out':
                schedule=schedules.get(doc['id'])
                if schedule is None:continue
                limits=retention_openings._limits(schedule);record=received.get(doc['id']);unreviewed=bool(record and record['source'] and any(Decimal(record['source'][k])>0 for k in retention_openings.KINDS))
            else:
                source=sales['source_states'].get(doc['id'])
                if source is None:continue
                limits={kind:sum((Decimal(r['amount']) for r in source['dues'] if r['kind']==index),Decimal(0)) for index,kind in ((1,'guarantee'),(2,'fiscal'))};record=issued.get(doc['id']);unreviewed=any(r['kind'] in (1,2) and r['paid'] and Decimal(r['amount'])>0 for r in source['dues'])
                if sum(limits.values())>issued_management.amounts(budget,doc)[2]:continue
            if not any(limits.values()):continue
            opening=record['opening'] if record else None
            result[(direction,doc['id'])]=dict(document=doc,limits=limits,opening=opening,needs_review=unreviewed and opening is None)
    return result


def state(budget):
    try:
        rows=json.loads(budget.project_metadata.get(KEY,'[]'))
        if not isinstance(rows,list) or len(rows)>10000:raise ValueError('registros')
        return rows
    except (ValueError,TypeError) as exc:raise BudgetError('Liquidaciones de retenciones inválidas') from exc


def validate(budget):
    rows=state(budget)
    if not rows:return rows
    ctx=contexts(budget);ids=set();references=set();events=[];policy=calculator_for(budget).policy
    balances={key:{kind:Decimal(c['opening'][kind]) if c['opening'] else Decimal(0) for kind in retention_openings.KINDS} for key,c in ctx.items()}
    for row in rows:
        if not isinstance(row,dict) or set(row)!={'id','direction','document_id','kind','date','amount','reference','status','cancellation_date','cancellation_reason'}:raise BudgetError('Columnas de liquidación de retención inválidas')
        for key in ('id','direction','document_id','kind','date','amount','reference','status'):
            if not isinstance(row[key],str) or not row[key].strip() or len(row[key])>10000:raise BudgetError('Liquidación de retención inválida')
        key=row['direction'],row['document_id'];context=ctx.get(key)
        if row['id'] in ids or context is None or row['kind'] not in retention_openings.KINDS or row['status'] not in ('posted','cancelled'):raise BudgetError('Retención sin factura o tipo válidos')
        ids.add(row['id']);doc=context['document']
        if doc['status']!='posted' and not (doc['status']=='cancelled' and row['status']=='cancelled'):raise BudgetError('La liquidación requiere una factura confirmada')
        if context['needs_review']:raise BudgetError('Revisa primero la apertura de retenciones de origen')
        if iso(row['date'])<iso(doc['date']) or (context['opening'] and row['date']<context['opening']['date']):raise BudgetError('Liquidación anterior al inicio de seguimiento o a la factura')
        amount=management.number(row['amount'],'Liquidación de retención')
        if amount<=0 or policy.amount(amount)!=amount:raise BudgetError('Liquidación no positiva o con precisión inválida')
        if amount>context['limits'][row['kind']]-(Decimal(context['opening'][row['kind']]) if context['opening'] else Decimal(0)):raise BudgetError('La liquidación supera la retención disponible tras la apertura')
        reference=key+(row['kind'],row['date'][:4],row['reference'].strip().casefold())
        if reference in references:raise BudgetError('Referencia de liquidación repetida para la misma retención')
        references.add(reference);events.append((row['date'],0,row['id'],key,row['kind'],amount))
        if row['status']=='cancelled':
            if iso(row['cancellation_date'])<iso(row['date']) or not isinstance(row['cancellation_reason'],str) or not row['cancellation_reason'].strip():raise BudgetError('Anulación de retención sin fecha o motivo válidos')
            events.append((row['cancellation_date'],1,row['id'],key,row['kind'],-amount))
        elif row['cancellation_date'] is not None or row['cancellation_reason'] is not None:raise BudgetError('Liquidación vigente con datos de anulación')
    daily={}
    for day,_,_,key,kind,amount in events:daily[(day,key,kind)]=daily.get((day,key,kind),Decimal(0))+amount
    for (_,key,kind),amount in sorted(daily.items()):
        balances[key][kind]+=amount
        if not 0<=balances[key][kind]<=ctx[key]['limits'][kind]:raise BudgetError('La liquidación supera el saldo disponible de esa retención')
    return rows


def _save(budget,rows):
    old=budget.project_metadata.get(KEY)
    try:budget.project_metadata[KEY]=json.dumps(rows,ensure_ascii=False);validate(budget)
    except Exception:
        if old is None:budget.project_metadata.pop(KEY,None)
        else:budget.project_metadata[KEY]=old
        raise


def record(budget,direction,document_id,kind,date,amount,reference):
    rows=state(budget);rows.append(dict(id=uuid4().hex,direction=direction,document_id=document_id,kind=kind,date=date,amount=str(management.number(amount,'Liquidación de retención')),reference=reference,status='posted',cancellation_date=None,cancellation_reason=None));_save(budget,rows)


def cancel(budget,settlement_id,date,reason):
    rows=state(budget);row=next((r for r in rows if r['id']==settlement_id),None)
    if row is None or row['status']!='posted':raise BudgetError('Liquidación inexistente o ya anulada')
    row.update(status='cancelled',cancellation_date=date,cancellation_reason=reason);_save(budget,rows)


def events(budget,as_of):
    iso(as_of);result=[]
    for row in validate(budget):
        if row['date']<=as_of:result.append(dict(row,event_date=row['date'],value=Decimal(row['amount']),reversal=False))
        if row['status']=='cancelled' and row['cancellation_date']<=as_of:result.append(dict(row,event_date=row['cancellation_date'],value=-Decimal(row['amount']),reversal=True))
    return sorted(result,key=lambda r:(r['event_date'],r['reversal'],r['id']))


def report_rows(budget):
    ctx=contexts(budget)
    return [(r['id'],'Pago a proveedor' if r['direction']=='out' else 'Cobro de cliente',ctx[(r['direction'],r['document_id'])]['document']['reference'], 'Garantía' if r['kind']=='guarantee' else 'Fiscal',r['date'],r['amount'],r['reference'],'Vigente' if r['status']=='posted' else 'Anulada',r['cancellation_date'] or '',r['cancellation_reason'] or '') for r in validate(budget)]
