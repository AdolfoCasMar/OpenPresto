"""Native planning: explicit calendars, dependencies and monthly allocation.

This is OpenPresto's own contract, not a decoder of proprietary PZH planning.
Dates are inclusive; only configured weekdays outside holidays carry weight.
"""
import json
from datetime import date, timedelta
from decimal import Decimal
from .budget import BudgetError, _decimal, special_price_kind
from .calculations import calculator_for

KEY = 'planning_v1'


def iso(value):
    if not isinstance(value, str):
        raise BudgetError('La fecha debe ser YYYY-MM-DD')
    try:
        result = date.fromisoformat(value)
    except ValueError as exc:
        raise BudgetError('Fecha de planificación inválida') from exc
    if result.isoformat() != value:
        raise BudgetError('La fecha debe ser YYYY-MM-DD')
    return result


def state(budget):
    try:
        data = json.loads(budget.project_metadata.get(KEY, '{"weekdays":[0,1,2,3,4],"holidays":[],"tasks":[]}'))
        if not isinstance(data, dict) or set(data) != {'weekdays','holidays','tasks'}:
            raise BudgetError('Planificación inválida')
        return data
    except (ValueError, TypeError) as exc:
        raise BudgetError('Planificación inválida: ' + str(exc)) from exc


def validate(budget):
    data = state(budget)
    days, holidays, tasks = data['weekdays'], data['holidays'], data['tasks']
    if not isinstance(days,list) or not days or any(type(n) is not int or not 0 <= n <= 6 for n in days) or len(set(days)) != len(days):
        raise BudgetError('Calendario laboral inválido')
    if not isinstance(holidays,list) or len(set(holidays)) != len(holidays):
        raise BudgetError('Festivos inválidos')
    for day in holidays:
        iso(day)
    if not isinstance(tasks,list) or len(tasks)>10000:
        raise BudgetError('Lista de actividades inválida')
    by_id = {}
    total_days = 0
    for task in tasks:
        if not isinstance(task,dict) or set(task) != {'relation_id','start','end','quantity','predecessors'}:
            raise BudgetError('Actividad inválida')
        rid = task['relation_id']
        relation = budget._relation(rid)
        if rid in by_id or budget.concepts[relation.parent_code].nature.casefold() not in ('capitulo','capítulo') or (budget.concepts[relation.child_code].nature.casefold() != 'partida' and budget.project_metadata.get('certification_role:'+rid) != 'partida') or special_price_kind(relation.child_code):
            raise BudgetError('Selecciona una partida bajo capítulo; no se planifican resúmenes ni cargos porcentuales')
        start,end = iso(task['start']), iso(task['end'])
        if end < start or (end-start).days > 36600 or _decimal(task['quantity'],'Cantidad planificada') < 0:
            raise BudgetError('Intervalo o cantidad de actividad inválidos')
        total_days += (end-start).days+1
        if total_days > 1000000:raise BudgetError('El plan supera el límite de un millón de días de actividad')
        predecessors = task['predecessors']
        if not isinstance(predecessors,list) or len(set(predecessors)) != len(predecessors):
            raise BudgetError('Precedencias inválidas')
        if not any((start+timedelta(days=n)).weekday() in days and (start+timedelta(days=n)).isoformat() not in holidays for n in range((end-start).days+1)):
            raise BudgetError('La actividad no contiene ningún día laborable')
        by_id[rid] = task
    visiting, done = set(), set()
    def visit(rid,depth=0):
        if depth>128:raise BudgetError('Cadena de precedencias demasiado profunda')
        if rid in visiting:
            raise BudgetError('Dependencias circulares en planificación')
        if rid in done:
            return
        visiting.add(rid)
        for previous in by_id[rid]['predecessors']:
            if previous not in by_id:
                raise BudgetError('Actividad precedente inexistente')
            visit(previous,depth+1)
            if iso(by_id[previous]['end']) >= iso(by_id[rid]['start']):
                raise BudgetError('La actividad debe comenzar después de terminar sus precedentes')
        visiting.remove(rid)
        done.add(rid)
    for rid in by_id:
        visit(rid)
    return data


def configure_calendar(budget, weekdays, holidays):
    data = state(budget)
    data.update(weekdays=weekdays, holidays=holidays)
    budget.project_metadata[KEY] = json.dumps(data,ensure_ascii=False)
    validate(budget)


def set_task(budget, relation_id, start, end, quantity, predecessors=None):
    data = state(budget)
    task = {'relation_id':relation_id,'start':start,'end':end,
            'quantity':str(_decimal(quantity,'Cantidad planificada')),'predecessors':predecessors or []}
    data['tasks'] = [t for t in data['tasks'] if t['relation_id'] != relation_id] + [task]
    budget.project_metadata[KEY] = json.dumps(data,ensure_ascii=False)
    validate(budget)


def remove_task(budget, relation_id):
    data = state(budget)
    if not any(t['relation_id']==relation_id for t in data['tasks']):
        raise BudgetError('Actividad inexistente')
    if any(relation_id in t['predecessors'] for t in data['tasks']):
        raise BudgetError('Retira primero los enlaces de las actividades dependientes')
    data['tasks'] = [t for t in data['tasks'] if t['relation_id'] != relation_id]
    budget.project_metadata[KEY] = json.dumps(data,ensure_ascii=False)


def allocation(budget, task, _data=None):
    data = validate(budget) if _data is None else _data
    start,end = iso(task['start']),iso(task['end'])
    weights = {}
    for n in range((end-start).days+1):
        day = start + timedelta(days=n)
        if day.weekday() in data['weekdays'] and day.isoformat() not in data['holidays']:
            key = day.strftime('%Y-%m')
            weights[key] = weights.get(key,0)+1
    policy = calculator_for(budget).policy
    total = policy.quantity(_decimal(task['quantity'],'Cantidad planificada'))
    result, assigned = [], Decimal(0)
    for index,(month,weight) in enumerate(weights.items()):
        value = total-assigned if index==len(weights)-1 else min(total-assigned, policy.quantity(total*weight/sum(weights.values())))
        assigned += value
        result.append((month,weight,value))
    return result


def task_rows(budget):
    data = validate(budget)
    calculator = calculator_for(budget)
    rows = []
    for task in data['tasks']:
        relation = budget._relation(task['relation_id'])
        for month,days,quantity in allocation(budget,task,data):
            rows.append((relation.parent_code,relation.child_code,task['start'],task['end'],month,days,
                quantity,calculator.policy.amount(quantity*relation.factor*calculator.price(relation.child_code))))
    return rows


def resources(budget):
    calculator = calculator_for(budget)
    children = {}
    for relation in budget.relations:
        children.setdefault(relation.parent_code,[]).append(relation)
    result = {}
    def walk(code, quantity, month, visiting):
        if code in visiting or len(visiting)>128:
            raise BudgetError('Descomposición circular o demasiado profunda')
        if special_price_kind(code):
            return  # Economic charges are not physical resources.
        if not children.get(code):
            key = month,code
            result[key] = result.get(key,Decimal(0))+quantity
            return
        for relation in children[code]:
            walk(relation.child_code,quantity*relation.factor*calculator.quantity(relation.id),month,visiting|{code})
    data=validate(budget)
    for task in data['tasks']:
        relation = budget._relation(task['relation_id'])
        for month,_,quantity in allocation(budget,task,data):
            walk(relation.child_code,quantity*relation.factor,month,set())
    return [(month,code,budget.concepts[code].unit,calculator.policy.quantity(quantity))
            for (month,code),quantity in sorted(result.items())]
