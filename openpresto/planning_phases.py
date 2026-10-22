"""Explicit phase allocation independent of budget, certification and CPM.

Dates are stored, not recalculated. Source edges carry no assumed FS/SS type.
"""
import json
import heapq
from decimal import Decimal
from .budget import BudgetError, _decimal, special_price_kind
from .planning import iso
from .calculations import calculator_for

KEY='planning_phases_v1'


def state(budget):
    try:data=json.loads(budget.project_metadata.get(KEY,'{"end_dates":[],"approved":null,"tasks":[]}'))
    except (ValueError,TypeError) as exc:raise BudgetError('Plan por fases inválido') from exc
    if not isinstance(data,dict) or set(data)!={'end_dates','approved','tasks'}:raise BudgetError('Estructura de plan por fases inválida')
    return data


def validate(budget,data=None):
    data=state(budget) if data is None else data
    if not isinstance(data,dict) or set(data)!={'end_dates','approved','tasks'}:raise BudgetError('Plan por fases inválido')
    dates=data['end_dates']
    if not isinstance(dates,list) or len(dates)>99:raise BudgetError('Calendario de fases inválido')
    parsed=[iso(d) for d in dates]
    if any(a>=b for a,b in zip(parsed,parsed[1:])):raise BudgetError('Las fechas de fases deben crecer')
    approved=data['approved']
    if approved is not None and (type(approved) is not int or not 0<=approved<=len(dates)):raise BudgetError('Aprobación de planificación inválida')
    if not isinstance(data['tasks'],list) or len(data['tasks'])>10000:raise BudgetError('Actividades sin calendario')
    tasks={};count=0;edges=0
    for task in data['tasks']:
        columns={'relation_id','start','end','actual_start','actual_end','objective_quantity','objective_price','planned_price','source_planned_quantity','phases','predecessors'}
        if not isinstance(task,dict) or set(task)!=columns:raise BudgetError('Actividad por fases inválida')
        rid=task['relation_id']
        if not isinstance(rid,str) or rid in tasks:raise BudgetError('Actividad repetida')
        relation=budget._relation(rid)
        if special_price_kind(relation.child_code) or budget.concepts[relation.parent_code].nature.casefold() not in ('capitulo','capítulo') or (budget.concepts[relation.child_code].nature.casefold()!='partida' and budget.project_metadata.get('certification_role:'+rid)!='partida'):
            raise BudgetError('El plan requiere partidas bajo capítulo')
        for start,end in (('start','end'),('actual_start','actual_end')):
            if task[start] is not None:iso(task[start])
            if task[end] is not None:iso(task[end])
            if task[start] and task[end] and task[start]>task[end]:raise BudgetError('Final de actividad anterior a inicio')
        for field in ('objective_quantity','objective_price','planned_price','source_planned_quantity'):
            if field=='source_planned_quantity' and task[field] is None:continue
            value=_decimal(task[field],field)
            if value<0 or value>Decimal('1e15'):raise BudgetError('Objetivo o precio fuera de límites')
        if Decimal(task['planned_price'])!=Decimal(task['objective_price']):raise BudgetError('En este perfil de partidas, planificación y objetivo comparten precio')
        if not isinstance(task['phases'],dict):raise BudgetError('Reparto por fases inválido')
        cumulative=Decimal(0)
        for number in range(1,len(dates)+1):
            value=_decimal(task['phases'].get(str(number),'0'),'Cantidad de fase')
            if abs(value)>Decimal('1e15'):raise BudgetError('Cantidad de fase fuera de límites')
            cumulative+=value
            if cumulative<0:raise BudgetError('Acumulado planificado negativo')
        if any(k not in {str(n) for n in range(1,len(dates)+1)} for k in task['phases']):raise BudgetError('Cantidad fuera del calendario')
        count+=len(task['phases'])
        if count>100000:raise BudgetError('Demasiadas cantidades de fase')
        predecessors=task['predecessors']
        if not isinstance(predecessors,list) or any(not isinstance(r,str) for r in predecessors) or len(set(predecessors))!=len(predecessors):raise BudgetError('Precedencias inválidas')
        edges+=len(predecessors);tasks[rid]=task
    if edges>100000:raise BudgetError('Demasiadas precedencias')
    successors={rid:[] for rid in tasks};degree={rid:len(t['predecessors']) for rid,t in tasks.items()}
    for rid,task in tasks.items():
        for parent in task['predecessors']:
            if parent not in tasks:raise BudgetError('Precedente inexistente')
            successors[parent].append(rid)
    ready=[rid for rid,d in degree.items() if d==0];heapq.heapify(ready);processed=0
    while ready:
        rid=heapq.heappop(ready);processed+=1
        for child in successors[rid]:
            degree[child]-=1
            if degree[child]==0:heapq.heappush(ready,child)
    if processed!=len(tasks):raise BudgetError('Ciclo de precedencias')
    return data


def _save(budget,data):
    validate(budget,data);budget.project_metadata[KEY]=json.dumps(data,ensure_ascii=False)
    if data['tasks'] and not data['end_dates']:budget.project_metadata['planning_unphased_v1']='1'


def configure(budget,end_dates,approved=None):
    data=state(budget);data.update(end_dates=end_dates,approved=approved);_save(budget,data)


def set_task(budget,relation_id,start=None,end=None,actual_start=None,actual_end=None,objective_quantity='0',objective_price='0',planned_price=None,phases=None,predecessors=None):
    data=state(budget);old=next((t for t in data['tasks'] if t['relation_id']==relation_id),None)
    if not isinstance(phases,dict):raise BudgetError('Indica las cantidades por fase')
    task=dict(relation_id=relation_id,start=start,end=end,actual_start=actual_start,actual_end=actual_end,
              objective_quantity=str(_decimal(objective_quantity,'Objetivo')),objective_price=str(_decimal(objective_price,'Precio objetivo')),
              planned_price=str(_decimal(objective_price if planned_price is None else planned_price,'Precio plan')),source_planned_quantity=old['source_planned_quantity'] if old else None,
              phases={k:str(_decimal(v,'Fase')) for k,v in phases.items()},predecessors=predecessors or [])
    data['tasks']=[task if t['relation_id']==relation_id else t for t in data['tasks']] if old else data['tasks']+[task]
    _save(budget,data)


def copy_pzh(budget):
    if KEY in budget.project_metadata:raise BudgetError('Ya existe un plan por fases; no se sobrescribe')
    from .pzh_archive import pzh_source_bytes
    from .pzh_importer import _Reader,_fields,_code,_unpack,CONCEPT_FIELDS
    from .pzh_operations import validate as source_state,day
    original=pzh_source_bytes(budget)
    if original is None:raise BudgetError('Falta el PZH original conservado')
    reader=_Reader(original);source=source_state(budget)
    if not source.get('activities'):raise BudgetError('Convierte primero la planificación PZH de origen')
    concepts={_code(b[:13]):_fields(b[13:],CONCEPT_FIELDS,'Precio objetivo') for _,_,b in reader.records(0,8)}
    dates={}
    for _,_,row in reader.records(17,8):
        if len(row)<4 or row[1]!=1 or row[0] in dates:raise BudgetError('Calendario PZH no admitido')
        dates[row[0]]=day(_unpack(row,2,'H')[0])
    if sorted(dates)!=list(range(1,len(dates)+1)):raise BudgetError('Calendario PZH incompleto')
    policy=calculator_for(budget).policy;tasks=[];ids={r['relation_id'] for r in source['activities']}
    phases={rid:{} for rid in ids};previous={rid:[] for rid in ids}
    for row in source['phases']:
        if row['relation_id'] in ids:
            value=policy.quantity(Decimal(row['quantity']));phases[row['relation_id']][str(row['phase'])]=str(value)
    for row in source['precedences']:
        if row['before'] not in ids or row['after'] not in ids:raise BudgetError('Precedencia fuera de las actividades convertibles')
        previous[row['after']].append(row['before'])
    for row in source['activities']:
        rid=row['relation_id'];price=policy.price(concepts[row['code']].get(12,Decimal(0)))
        tasks.append(dict(relation_id=rid,start=row['planned_start'],end=row['planned_finish'],actual_start=row['actual_start'],actual_end=row['actual_finish'],
            objective_quantity=str(policy.quantity(Decimal(row['objective_quantity']))),objective_price=str(price),planned_price=str(price),
            source_planned_quantity=str(policy.quantity(Decimal(row['planned_quantity']))),phases=phases[rid],predecessors=previous[rid]))
    _save(budget,dict(end_dates=[dates[n] for n in sorted(dates)],approved=None,tasks=tasks))


def activity_rows(budget):
    data=validate(budget);policy=calculator_for(budget).policy;rows=[]
    for task in data['tasks']:
        r=budget._relation(task['relation_id']);total=sum((Decimal(v) for v in task['phases'].values()),Decimal(0))
        approved=sum((Decimal(task['phases'].get(str(n),'0')) for n in range(1,data['approved']+1)),Decimal(0)) if data['approved'] is not None else None
        objective=policy.amount(Decimal(task['objective_quantity'])*Decimal(task['objective_price'])*r.factor)
        planned=policy.amount(total*Decimal(task['planned_price'])*r.factor)
        rows.append((r.id,r.parent_code,r.child_code,task['start'] or '',task['end'] or '',task['objective_quantity'],task['objective_price'],objective,
                     total,task['planned_price'],planned,approved if approved is not None else '',task['source_planned_quantity'] if task['source_planned_quantity'] is not None else '',len(task['predecessors'])))
    return rows


def phase_rows(budget):
    data=validate(budget);policy=calculator_for(budget).policy;rows=[]
    for task in data['tasks']:
        r=budget._relation(task['relation_id']);cumulative=Decimal(0)
        for n,end in enumerate(data['end_dates'],1):
            quantity=Decimal(task['phases'].get(str(n),'0'));cumulative+=quantity
            rows.append((r.parent_code,r.child_code,n,end,quantity,cumulative,task['planned_price'],policy.amount(quantity*Decimal(task['planned_price'])*r.factor)))
    return rows
