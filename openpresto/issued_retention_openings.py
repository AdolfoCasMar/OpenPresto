"""Reviewed customer retention balances, separate from dated cash receipts."""
import json
from decimal import Decimal
from .budget import BudgetError
from .planning import iso
from .calculations import calculator_for
from . import issued_management as sales,management
from .retention_openings import KINDS

KEY='issued_retention_openings_v1'
HEADERS=('Documento','Factura','Garantía programada','Fiscal programada','Garantía cobrada en origen','Fiscal cobrada en origen','Inicio de seguimiento','Garantía revisada','Fiscal revisada','Revisión','Nota')


def state(budget):
    try:
        data=json.loads(budget.project_metadata.get(KEY,'{}'))
        if not isinstance(data,dict) or len(data)>10000:raise ValueError('registros')
        return data
    except (ValueError,TypeError) as exc:raise BudgetError('Aperturas de retenciones emitidas inválidas') from exc


def _context(budget):
    data=sales.validate(budget)
    return management.indexed(data['documents']),data['source_states']


def _source(identifier,doc,source,budget):
    if doc['kind']!='invoice' or source is None:raise BudgetError('La apertura requiere vencimientos de una factura emitida en firme')
    limits={kind:sum((Decimal(d['amount']) for d in source['dues'] if d['kind']==index),Decimal(0)) for index,kind in ((1,'guarantee'),(2,'fiscal'))}
    if not any(limits.values()) or sum(limits.values())>sales.amounts(budget,doc)[2]:raise BudgetError('Las retenciones emitidas no concilian con la factura')
    paid={kind:str(sum((Decimal(d['amount']) for d in source['dues'] if d['kind']==index and d['paid']),Decimal(0))) for index,kind in ((1,'guarantee'),(2,'fiscal'))}
    from .pzh_archive import pzh_archive_inventory
    archive=pzh_archive_inventory(budget)
    prefix='pzh:'+archive['sha256']+':issued:document:' if archive else ''
    if not prefix or not identifier.startswith(prefix):raise BudgetError('Falta la identidad PZH de la retención emitida')
    suffix=identifier[len(prefix):]
    if not suffix.isascii() or not suffix.isdecimal() or str(int(suffix))!=suffix:raise BudgetError('Identidad de factura emitida inválida')
    return limits,dict(sha256=archive['sha256'],source_id=int(suffix),**paid)


def validate(budget):
    data=state(budget);docs,sources=_context(budget);policy=calculator_for(budget).policy
    for identifier,record in data.items():
        if identifier not in docs or not isinstance(record,dict) or set(record)!={'source','opening'}:raise BudgetError('Apertura de retención emitida sin factura')
        doc=docs[identifier];limits,source=_source(identifier,doc,sources.get(identifier),budget)
        stored=record['source']
        if not isinstance(stored,dict) or stored!=source or type(stored.get('source_id')) is not int:raise BudgetError('El saldo de retención emitida no coincide con sus vencimientos de origen')
        opening=record['opening']
        if opening is None:continue
        if not isinstance(opening,dict) or set(opening)!={'date','note',*KINDS} or not isinstance(opening['note'],str) or not opening['note'].strip():raise BudgetError('La apertura de retenciones emitidas requiere una explicación')
        if iso(opening['date'])<iso(doc['date']):raise BudgetError('Apertura de retenciones anterior a la factura')
        for kind in KINDS:
            if not isinstance(opening[kind],str):raise BudgetError('La retención debe ser texto decimal')
            amount=management.number(opening[kind],'Retención cobrada')
            if amount>limits[kind] or policy.amount(amount)!=amount:raise BudgetError('La retención cobrada supera su importe o precisión')
            if doc['status']=='cancelled' and amount>0:raise BudgetError('Retención cobrada de una factura emitida cancelada')
    return data


def _write(budget,data):
    previous=budget.project_metadata.get(KEY)
    try:
        budget.project_metadata[KEY]=json.dumps(data,ensure_ascii=False);validate(budget)
        if 'retention_settlements_v1' in budget.project_metadata:
            from .retention_settlements import validate as validate_settlements
            validate_settlements(budget)
    except Exception:
        if previous is None:budget.project_metadata.pop(KEY,None)
        else:budget.project_metadata[KEY]=previous
        raise


def copy_source(budget,document_id):
    data=state(budget)
    if document_id in data:return
    docs,sources=_context(budget);doc=docs[document_id];source=sources.get(document_id)
    if source is None or not any(d['paid'] and d['kind']!=0 and Decimal(d['amount'])>0 for d in source['dues']):return
    _,source=_source(document_id,doc,source,budget)
    data[document_id]=dict(source=source,opening=None);_write(budget,data)


def set_opening(budget,document_id,date,guarantee,fiscal,note):
    data=state(budget);docs,sources=_context(budget)
    if document_id not in docs:raise BudgetError('Factura emitida inexistente')
    _,source=_source(document_id,docs[document_id],sources.get(document_id),budget)
    data[document_id]=dict(source=source,opening=dict(date=date,guarantee=str(management.number(guarantee,'Garantía cobrada')),fiscal=str(management.number(fiscal,'Retención fiscal cobrada')),note=note));_write(budget,data)


def clear_opening(budget,document_id):
    data=state(budget)
    if document_id not in data:raise BudgetError('No hay apertura de retenciones emitidas')
    data[document_id]['opening']=None;_write(budget,data)


def opening_balances(budget,as_of=None):
    if as_of is not None:iso(as_of)
    balances={}
    for identifier,record in validate(budget).items():
        opening=record['opening']
        if opening is None:balances[identifier]=None if any(Decimal(record['source'][k])>0 for k in KINDS) else dict.fromkeys(KINDS,Decimal(0))
        elif as_of is not None and opening['date']>as_of and any(Decimal(opening[k])>0 for k in KINDS):balances[identifier]=None
        else:balances[identifier]={k:Decimal(opening[k]) for k in KINDS}
    return balances


def report_rows(budget):
    data=validate(budget);docs,sources=_context(budget);rows=[]
    for identifier,source_state in sources.items():
        doc=docs[identifier]
        if doc['kind']!='invoice' or not any(d['kind']!=0 and Decimal(d['amount'])>0 for d in source_state['dues']):continue
        try:limits,source=_source(identifier,doc,source_state,budget)
        except BudgetError as exc:
            limits={kind:sum((Decimal(d['amount']) for d in source_state['dues'] if d['kind']==index),Decimal(0)) for index,kind in ((1,'guarantee'),(2,'fiscal'))}
            rows.append((identifier,doc['reference'],limits['guarantee'],limits['fiscal'],'','','','','','Revisar origen',str(exc)))
            continue
        opening=data.get(identifier,{}).get('opening');review=opening is None and any(Decimal(source[k])>0 for k in KINDS)
        rows.append((identifier,doc['reference'],limits['guarantee'],limits['fiscal'],source['guarantee'],source['fiscal'],opening['date'] if opening else '',opening['guarantee'] if opening else '',opening['fiscal'] if opening else '', 'Revisar apertura' if review else 'Revisada' if opening else 'Sin cobro previo',opening['note'] if opening else ''))
    return rows
