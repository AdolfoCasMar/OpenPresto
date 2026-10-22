"""Explicit resource-hour entries, independent of payroll and stock accounting."""
import json
from uuid import uuid4
from decimal import Decimal, localcontext, ROUND_HALF_UP
from .budget import BudgetError, _decimal, special_price_kind
from .planning import iso
from .production import eligible as eligible_relations

KEY = 'resource_hours_v1'
HEADERS = ('Referencia','Fecha','Equipo','Estado','Recurso','Resumen','Tipo','Relación de partida','Horas','Tarifa guardada','Coste registrado','Nota','Fecha de anulación','Motivo de anulación')
RESOURCE_HEADERS = ('Recurso','Resumen','Tipo','Horas confirmadas','Coste confirmado')
WORK_HEADERS = ('Relación','Partida','Resumen','Unidad de partida','Recurso','Horas confirmadas','Coste confirmado')
KINDS = {'mano de obra':'Mano de obra','maquinaria':'Maquinaria'}
STATES = {'draft':'Borrador','posted':'Confirmado','cancelled':'Anulado'}


def resources(budget):
    return [c for c in budget.concepts.values() if c.nature.strip().casefold() in KINDS
            and c.unit.strip().casefold() in ('h','hora','horas') and not special_price_kind(c.code)]


def number(value, name, positive=False):
    if not isinstance(value,str) or len(value)>100: raise BudgetError(name+' debe ser texto decimal')
    n=_decimal(value,name)
    if not 0<=n<=Decimal('1e12') or n.as_tuple().exponent < -12 or (positive and not n):
        raise BudgetError(name+' fuera de rango')
    return n


def validate(budget, data=None):
    try:
        data=json.loads(budget.project_metadata.get(KEY,'[]')) if data is None else data
        if not isinstance(data,list) or len(data)>100000:raise BudgetError('Demasiados registros de horas')
        resource_ids={c.code for c in resources(budget)};relations={r.id for r in eligible_relations(budget)}
        ids=set();references=set()
        for row in data:
            if not isinstance(row,dict) or set(row)!={'id','reference','date','team','note','status','resource_code','relation_id','hours','rate','cancellation_date','cancellation_reason'}:
                raise BudgetError('Columnas de horas inválidas')
            for key in ('id','reference','team','note','cancellation_reason'):
                if not isinstance(row[key],str) or len(row[key])>10000:raise BudgetError('Texto de horas inválido')
            if not row['id'] or row['id'] in ids or not row['reference'].strip():raise BudgetError('Identidad de horas inválida')
            ids.add(row['id']);iso(row['date'])
            key=row['date'][:4],row['reference'].strip().casefold()
            if key in references:raise BudgetError('Referencia de horas repetida en el año')
            references.add(key)
            if not isinstance(row['resource_code'],str) or row['resource_code'] not in resource_ids:
                raise BudgetError('El recurso debe ser mano de obra o maquinaria con unidad h')
            rid=row['relation_id']
            if rid is not None and (not isinstance(rid,str) or rid not in relations):raise BudgetError('Partida de destino no válida')
            number(row['hours'],'Horas',True);number(row['rate'],'Tarifa')
            if row['status'] not in STATES:raise BudgetError('Estado de horas inválido')
            if row['status']=='cancelled':
                iso(row['cancellation_date'])
                if row['cancellation_date']<row['date'] or not row['cancellation_reason'].strip():raise BudgetError('Anulación sin fecha o motivo válido')
            elif row['cancellation_date'] is not None or row['cancellation_reason']:raise BudgetError('Anulación incompatible con el estado')
        return data
    except (ValueError,TypeError) as exc:
        raise BudgetError('Registros de horas inválidos: '+str(exc)) from exc


def _save(budget,data):
    validate(budget,data)
    budget.project_metadata[KEY]=json.dumps(data,ensure_ascii=False)


def set_entry(budget,reference,date,team,resource_code,hours,rate,relation_id=None,note='',entry_id=None):
    data=validate(budget);old=next((r for r in data if r['id']==entry_id),None)
    if entry_id is not None and old is None:raise BudgetError('Registro de horas inexistente')
    if old and old['status']!='draft':raise BudgetError('Solo se editan borradores de horas')
    row=dict(id=old['id'] if old else uuid4().hex,reference=reference,date=date,team=team,note=note,
             resource_code=resource_code,relation_id=relation_id,hours=hours,rate=rate,status='draft',
             cancellation_date=None,cancellation_reason='')
    _save(budget,[row if r['id']==row['id'] else r for r in data] if old else data+[row])


def set_status(budget,entry_id,status,cancellation_date=None,reason=''):
    data=validate(budget);old=next((r for r in data if r['id']==entry_id),None)
    if old is None:raise BudgetError('Registro de horas inexistente')
    if not ((old['status']=='draft' and status=='posted') or (old['status'] in ('draft','posted') and status=='cancelled')):
        raise BudgetError('Transición de horas no permitida')
    row=dict(old,status=status,cancellation_date=cancellation_date,cancellation_reason=reason)
    _save(budget,[row if r['id']==entry_id else r for r in data])


def cost(row):
    """Fixed two-decimal commercial rounding per entry; sum the rounded entries."""
    with localcontext() as context:
        context.prec=100
        return (Decimal(row['hours'])*Decimal(row['rate'])).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)


def entries(budget):
    return sorted(validate(budget),key=lambda r:(r['date'],r['reference'],r['id']))


def report_rows(budget):
    rows=[]
    for r in entries(budget):
        c=budget.concepts[r['resource_code']]
        rows.append((r['reference'],r['date'],r['team'],STATES[r['status']],c.code,c.summary,KINDS[c.nature.strip().casefold()],r['relation_id'] or '',Decimal(r['hours']),Decimal(r['rate']),cost(r),r['note'],r['cancellation_date'] or '',r['cancellation_reason']))
    return rows


def snapshot(budget,as_of):
    """Current confirmed states up to cutoff; no historical status reconstruction."""
    iso(as_of);by_resource={};by_work={};total=Decimal(0);count=0;unassigned=Decimal(0)
    with localcontext() as context:
        context.prec=100
        for r in validate(budget):
            if r['status']!='posted' or r['date']>as_of:continue
            count+=1;hours=Decimal(r['hours']);amount=cost(r);total+=amount
            code=r['resource_code'];rid=r['relation_id']
            for mapping,key in ((by_resource,code),(by_work,(rid,code))):
                old=mapping.get(key,(Decimal(0),Decimal(0)));mapping[key]=(old[0]+hours,old[1]+amount)
            if rid is None:unassigned+=amount
    resource_rows=[];work_rows=[]
    for code,(hours,amount) in sorted(by_resource.items()):
        c=budget.concepts[code];resource_rows.append((code,c.summary,KINDS[c.nature.strip().casefold()],hours,amount))
    for (rid,code),(hours,amount) in sorted(by_work.items(),key=lambda item:(item[0][0] or '',item[0][1])):
        c=budget.concepts[budget._relation(rid).child_code] if rid else None
        work_rows.append((rid or '',c.code if c else '',c.summary if c else 'Sin asignar',c.unit if c else '',code,hours,amount))
    return dict(as_of=as_of,count=count,total=total,unassigned=unassigned,resources=resource_rows,work_items=work_rows)
