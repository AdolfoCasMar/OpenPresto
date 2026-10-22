"""Frozen phase baseline, explicit physical progress and actual costs.

No inference from certification, invoices, cash movements or missing entries.
No distribution/interpolation of measured progress between cut dates.
"""
import json
import hashlib
from decimal import Decimal, localcontext, ROUND_HALF_UP
from .budget import BudgetError, _decimal
from .planning import iso
from .economic_indicators import indicators

KEY = 'earned_value_v1'


def state(budget):
    try:
        result = json.loads(budget.project_metadata.get(KEY,'{"baseline":null,"progress":[]}'))
    except (TypeError,ValueError) as exc:
        raise BudgetError('Control de valor ganado inválido') from exc
    if not isinstance(result,dict) or set(result) != {'baseline','progress'}:
        raise BudgetError('Estructura de valor ganado inválida')
    return result


def number(value, name):
    if isinstance(value,str) and len(value)>128:raise BudgetError(name + ' demasiado largo')
    value = _decimal(value,name)
    if len(value.as_tuple().digits)>40 or (value and value.adjusted() < -18):raise BudgetError(name + ' precisión fuera de límites')
    if not 0 <= value <= Decimal('1e18'):
        raise BudgetError(name + ' fuera de límites')
    return value


def note(value):
    if not isinstance(value,str) or len(value)>4000:
        raise BudgetError('Nota de control inválida')


def validate(budget, data=None):
    data = state(budget) if data is None else data
    if not isinstance(data,dict) or set(data) != {'baseline','progress'}:
        raise BudgetError('Estructura de valor ganado inválida')
    baseline = data['baseline']; progress = data['progress']
    if not isinstance(progress,list) or len(progress)>100000:
        raise BudgetError('Demasiados registros de avance')
    if baseline is None:
        if progress: raise BudgetError('Avance sin línea base')
        return data
    if not isinstance(baseline,dict) or set(baseline) != {'end_dates','tasks','amount_decimals','source_digest','note'}:
        raise BudgetError('Línea base inválida')
    dates=baseline['end_dates'];tasks=baseline['tasks'];note(baseline['note'])
    if not isinstance(dates,list) or not 1<=len(dates)<=99:
        raise BudgetError('Calendario de control inválido')
    for value in dates: iso(value)
    if any(a>=b for a,b in zip(dates,dates[1:])):raise BudgetError('Fechas de control desordenadas')
    if type(baseline['amount_decimals']) is not int or not 0<=baseline['amount_decimals']<=12:
        raise BudgetError('Precisión de línea base inválida')
    digest=baseline['source_digest']
    if not isinstance(digest,str) or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):
        raise BudgetError('Huella de línea base inválida')
    if not isinstance(tasks,list) or not 1<=len(tasks)<=10000 or len(tasks)*len(dates)>100000:
        raise BudgetError('Actividades de control fuera de límites')
    ids={}
    for task in tasks:
        if not isinstance(task,dict) or set(task) != {'relation_id','code','quantity','price','factor','phases'}:
            raise BudgetError('Actividad de línea base inválida')
        rid=task['relation_id']
        if not isinstance(rid,str) or rid in ids:raise BudgetError('Actividad de control duplicada')
        relation=budget._relation(rid)
        if task['code']!=relation.child_code:raise BudgetError('No se puede sustituir una partida con línea base')
        quantity=number(task['quantity'],'Cantidad base');number(task['price'],'Precio base');number(task['factor'],'Factor base')
        if not isinstance(task['phases'],list) or len(task['phases'])!=len(dates):raise BudgetError('Reparto de base incompleto')
        with localcontext() as context:
            context.prec=160
            total=sum((number(v,'Cantidad planificada') for v in task['phases']),Decimal(0))
            if quantity*Decimal(task['price'])*Decimal(task['factor'])>Decimal('1e24'):raise BudgetError('Coste base fuera de límites')
        if total!=quantity:
            raise BudgetError('El reparto completo debe coincidir con la cantidad objetivo: '+task['code'])
        ids[rid]=task
    seen=set()
    for record in progress:
        if not isinstance(record,dict) or set(record) != {'phase','relation_id','quantity','actual_cost','note'}:
            raise BudgetError('Registro de avance inválido')
        phase=record['phase'];rid=record['relation_id']
        if type(phase) is not int or not 1<=phase<=len(dates) or not isinstance(rid,str) or rid not in ids:
            raise BudgetError('Periodo o partida de avance inexistente')
        if (phase,rid) in seen:raise BudgetError('Avance duplicado en el periodo')
        seen.add((phase,rid));note(record['note'])
        if record['quantity'] is not None and number(record['quantity'],'Producción acumulada')>Decimal(ids[rid]['quantity']):
            raise BudgetError('La producción supera el alcance congelado; revisa el alcance antes de medir valor ganado')
        if record['actual_cost'] is not None:number(record['actual_cost'],'Coste real acumulado')
    return data


def _save(budget,data):
    validate(budget,data)
    budget.project_metadata[KEY]=json.dumps(data,ensure_ascii=False)


def freeze_phases(budget, explanation=''):
    if validate(budget)['baseline'] is not None:raise BudgetError('La línea base ya está congelada; no se sobrescribe')
    from .planning_phases import validate as phase_plan
    from .calculations import calculator_for
    plan=phase_plan(budget);note(explanation)
    baseline=dict(end_dates=list(plan['end_dates']),amount_decimals=calculator_for(budget).policy.amount_decimals,
                  source_digest=hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(',',':')).encode()).hexdigest(),note=explanation,tasks=[])
    for task in plan['tasks']:
        relation=budget._relation(task['relation_id'])
        baseline['tasks'].append(dict(relation_id=relation.id,code=relation.child_code,quantity=task['objective_quantity'],
            price=task['objective_price'],factor=str(relation.factor),phases=[task['phases'].get(str(i),'0') for i in range(1,len(plan['end_dates'])+1)]))
    _save(budget,dict(baseline=baseline,progress=[]))


def set_progress(budget, phase, relation_id, quantity=None, actual_cost=None, explanation=''):
    data=validate(budget)
    record=dict(phase=phase,relation_id=relation_id,quantity=None if quantity is None else str(number(quantity,'Producción acumulada')),
                actual_cost=None if actual_cost is None else str(number(actual_cost,'Coste real acumulado')),note=explanation)
    data['progress']=[r for r in data['progress'] if (r['phase'],r['relation_id'])!=(phase,relation_id)]+[record]
    _save(budget,data)


def set_period(budget, phase, rows):
    if not isinstance(rows,list):raise BudgetError('Introduce las partidas del periodo')
    data=validate(budget)
    records=[]
    for row in rows:
        if not isinstance(row,dict) or set(row)!={'relation_id','quantity','actual_cost','note'}:
            raise BudgetError('Columnas de periodo inválidas')
        records.append(dict(phase=phase,relation_id=row['relation_id'],quantity=None if row['quantity'] is None else str(number(row['quantity'],'Producción acumulada')),
                            actual_cost=None if row['actual_cost'] is None else str(number(row['actual_cost'],'Coste real acumulado')),note=row['note']))
    if type(phase) is not int or data['baseline'] is None or not 1<=phase<=len(data['baseline']['end_dates']):
        raise BudgetError('Periodo de control inexistente')
    data['progress']=[r for r in data['progress'] if r['phase']!=phase]+records
    _save(budget,data)


def amount(baseline,value):
    return value.quantize(Decimal(1).scaleb(-baseline['amount_decimals']),rounding=ROUND_HALF_UP)


def activity_rows(budget,phase):
    data=validate(budget);base=data['baseline']
    if base is None:return []
    if type(phase) is not int or not 1<=phase<=len(base['end_dates']):raise BudgetError('Periodo de control inexistente')
    records={r['relation_id']:r for r in data['progress'] if r['phase']==phase};result=[]
    with localcontext() as context:
        context.prec=160
        for task in base['tasks']:
            rid=task['relation_id'];record=records.get(rid,{})
            rate=Decimal(task['price'])*Decimal(task['factor'])
            bac=amount(base,Decimal(task['quantity'])*rate)
            pv=amount(base,sum((Decimal(q) for q in task['phases'][:phase]),Decimal(0))*rate)
            quantity=record.get('quantity');cost=record.get('actual_cost')
            ev=amount(base,Decimal(quantity)*rate) if quantity is not None else None
            result.append(dict(relation_id=rid,code=task['code'],quantity=quantity,actual_cost=None if cost is None else amount(base,Decimal(cost)),
                               BAC=bac,PV=pv,EV=ev,note=record.get('note','')))
    return result


def curve_rows(budget):
    data=validate(budget);base=data['baseline']
    if base is None:return []
    result=[]
    for phase,end in enumerate(base['end_dates'],1):
        activities=activity_rows(budget,phase)
        with localcontext() as context:
            context.prec=160
            bac=sum((r['BAC'] for r in activities),Decimal(0));pv=sum((r['PV'] for r in activities),Decimal(0))
        known_ev=sum(r['EV'] is not None for r in activities);known_ac=sum(r['actual_cost'] is not None for r in activities)
        with localcontext() as context:
            context.prec=160
            ev=sum((r['EV'] for r in activities),Decimal(0)) if known_ev==len(activities) else None
            ac=sum((r['actual_cost'] for r in activities),Decimal(0)) if known_ac==len(activities) else None
        result.append(dict(phase=phase,date=end,known_ev=known_ev,known_ac=known_ac,total=len(activities),**indicators(bac,pv,ev,ac)))
    return result


COLUMNS=('BAC','PV','EV','AC','CV','SV','CPI','SPI','EAC_CPI','EAC_BASELINE','EAC_COMPOSITE','ETC_CPI','VAC_CPI','TCPI_BAC')


def report_rows(budget):
    data=validate(budget)
    if data['baseline'] is None:return []
    base=data['baseline'];rows=[]
    with localcontext() as context:
        context.prec=160
        for row in curve_rows(budget):
            values=[]
            for key in COLUMNS:
                value=row[key]
                if value is None: values.append('')
                elif key in ('CPI','SPI','TCPI_BAC'):values.append(value.quantize(Decimal('.0001'),rounding=ROUND_HALF_UP))
                else: values.append(amount(base,value))
            rows.append((row['phase'],row['date'],*values,str(row['known_ev'])+'/'+str(row['total']),str(row['known_ac'])+'/'+str(row['total'])))
    return rows
