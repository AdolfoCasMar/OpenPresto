"""Reviewed retention opening balances; no historical cash events are invented."""
import json
from decimal import Decimal
from .budget import BudgetError
from . import management,management_schedule
from .calculations import calculator_for
from .planning import iso

KEY='retention_openings_v1'
KINDS=('guarantee','fiscal')
HEADERS=('Documento','Factura','Garantía programada','Fiscal programada','Garantía liquidada en origen','Fiscal liquidada en origen','Inicio de seguimiento','Garantía revisada','Fiscal revisada','Revisión','Nota')


def state(budget):
    try:
        data=json.loads(budget.project_metadata.get(KEY,'{}'))
        if not isinstance(data,dict) or len(data)>10000:raise ValueError('registros')
        return data
    except (ValueError,TypeError) as exc:raise BudgetError('Saldos de retenciones inválidos') from exc


def _limits(schedule):
    return {kind:sum((Decimal(r['amount']) for r in schedule['dues'] if r['kind']==kind),Decimal(0)) for kind in KINDS}


def validate(budget):
    data=state(budget);schedules=management_schedule.validate(budget);docs=management.indexed(management.validate(budget)['documents']);policy=calculator_for(budget).policy
    def amounts(record,limits):
        for kind in KINDS:
            value=record[kind]
            if not isinstance(value,str):raise BudgetError('El saldo de retención debe ser texto decimal')
            value=management.number(value,'Retención liquidada')
            if policy.amount(value)!=value or value>limits[kind]:raise BudgetError('La retención liquidada supera su importe o precisión')
    for identifier,record in data.items():
        if not isinstance(identifier,str) or identifier not in schedules or docs[identifier]['kind']!='invoice':raise BudgetError('Retención sin calendario de factura en firme')
        if not isinstance(record,dict) or set(record)!={'source','opening'}:raise BudgetError('Saldo de retención inválido')
        limits=_limits(schedules[identifier])
        if sum(limits.values(),Decimal(0))<=0:raise BudgetError('La factura no tiene retenciones programadas')
        source=record['source'];opening=record['opening']
        if source is not None:
            if not isinstance(source,dict) or set(source)!={'sha256','source_id',*KINDS}:raise BudgetError('Origen de retención inválido')
            if (not isinstance(source['sha256'],str) or len(source['sha256'])!=64 or any(c not in '0123456789abcdef' for c in source['sha256']) or type(source['source_id']) is not int or source['source_id']<0):raise BudgetError('Identidad de retención de origen inválida')
            if identifier!='pzh:'+source['sha256']+':document:'+str(source['source_id']):raise BudgetError('La retención de origen no corresponde a la factura nativa')
            amounts(source,limits)
        if opening is not None:
            if not isinstance(opening,dict) or set(opening)!={'date','note',*KINDS} or not isinstance(opening['note'],str) or not opening['note'].strip():raise BudgetError('La apertura de retenciones requiere una explicación')
            if iso(opening['date'])<iso(docs[identifier]['date']):raise BudgetError('Apertura de retenciones anterior a la factura')
            amounts(opening,limits)
            if docs[identifier]['status']=='cancelled' and any(Decimal(opening[k])>0 for k in KINDS):raise BudgetError('Retención liquidada de una factura cancelada')
    return data


def _write(budget,data):
    old=budget.project_metadata.get(KEY)
    try:
        budget.project_metadata[KEY]=json.dumps(data,ensure_ascii=False)
        validate(budget)
        if 'retention_settlements_v1' in budget.project_metadata:
            from .retention_settlements import validate as validate_settlements
            validate_settlements(budget)
    except Exception:
        if old is None:budget.project_metadata.pop(KEY,None)
        else:budget.project_metadata[KEY]=old
        raise


def copy_source(budget,document_id,source_id,dues):
    paid={kind:sum((Decimal(row['amount']) for row in dues if row['paid'] and row['kind']==index),Decimal(0)) for index,kind in ((1,'guarantee'),(2,'fiscal'))}
    if not any(paid.values()):return
    from .pzh_archive import pzh_archive_inventory
    archive=pzh_archive_inventory(budget)
    if archive is None:raise BudgetError('Falta el origen PZH de las retenciones')
    data=state(budget)
    if document_id in data:return
    data[document_id]=dict(source=dict(sha256=archive['sha256'],source_id=source_id,**{kind:str(value) for kind,value in paid.items()}),opening=None)
    _write(budget,data)


def set_opening(budget,document_id,date,guarantee,fiscal,note):
    data=state(budget);old=data.get(document_id)
    data[document_id]=dict(source=old['source'] if old else None,opening=dict(date=date,guarantee=str(management.number(guarantee,'Garantía liquidada')),fiscal=str(management.number(fiscal,'Retención fiscal liquidada')),note=note))
    _write(budget,data)


def clear_opening(budget,document_id):
    data=state(budget)
    if document_id not in data:raise BudgetError('No hay apertura de retenciones')
    data[document_id]['opening']=None
    _write(budget,data)


def opening_balances(budget,as_of=None):
    if as_of is not None:iso(as_of)
    balances={}
    for identifier,record in validate(budget).items():
        opening=record['opening'];source=record['source']
        if opening is None:
            balances[identifier]=None if source and any(Decimal(source[k])>0 for k in KINDS) else dict.fromkeys(KINDS,Decimal(0))
        elif as_of is not None and opening['date']>as_of and any(Decimal(opening[k])>0 for k in KINDS):balances[identifier]=None
        else:balances[identifier]={k:Decimal(opening[k]) for k in KINDS}
    return balances


def report_rows(budget):
    data=validate(budget);docs=management.indexed(management.state(budget)['documents']);rows=[]
    for identifier,schedule in management_schedule.validate(budget).items():
        if docs[identifier]['kind']!='invoice':continue
        limits=_limits(schedule)
        if not any(limits.values()):continue
        record=data.get(identifier,{});source=record.get('source');opening=record.get('opening');review=source and any(Decimal(source[k])>0 for k in KINDS) and opening is None
        rows.append((identifier,docs[identifier]['reference'],limits['guarantee'],limits['fiscal'],source['guarantee'] if source else '',source['fiscal'] if source else '',opening['date'] if opening else '',opening['guarantee'] if opening else '',opening['fiscal'] if opening else '', 'Revisar apertura' if review else 'Revisada' if opening else 'Sin liquidación previa',opening['note'] if opening else ''))
    return rows
