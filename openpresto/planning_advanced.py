"""Independent objective and working-day CPM; never changes budget quantities.

Finish-to-start uses an exclusive finish boundary: a one-day Monday activity
allows its zero-lag successor on Tuesday. Milestones consume zero days.
"""
import heapq
import json
from datetime import timedelta
from decimal import Decimal

from .budget import BudgetError, _decimal, special_price_kind
from .calculations import calculator_for
from .planning import iso, validate as validate_calendar

KEY = 'planning_advanced_v1'
MAX_DAYS = 36600


def state(budget):
    try:
        data = json.loads(budget.project_metadata.get(KEY, '{"start":null,"tasks":[]}'))
    except (ValueError, TypeError) as exc:
        raise BudgetError('Plan avanzado inválido') from exc
    if not isinstance(data, dict) or set(data) != {'start', 'tasks'}:
        raise BudgetError('Estructura de plan avanzado inválida')
    return data


def _validated(budget, data):
    if not isinstance(data['tasks'], list) or len(data['tasks']) > 10000:
        raise BudgetError('Lista de actividades avanzada inválida')
    if data['start'] is None:
        if data['tasks']:
            raise BudgetError('Define el inicio del plan avanzado')
    else:
        iso(data['start'])
    tasks, edges = {}, 0
    for task in data['tasks']:
        if not isinstance(task, dict) or set(task) != {'relation_id', 'duration', 'quantity', 'price', 'predecessors'}:
            raise BudgetError('Actividad avanzada inválida')
        rid = task['relation_id']
        if not isinstance(rid, str) or rid in tasks:
            raise BudgetError('Identificador de actividad inválido o duplicado')
        relation = budget._relation(rid)
        if (budget.concepts[relation.parent_code].nature.casefold() not in ('capitulo', 'capítulo')
                or (budget.concepts[relation.child_code].nature.casefold() != 'partida'
                    and budget.project_metadata.get('certification_role:' + rid) != 'partida')
                or special_price_kind(relation.child_code)):
            raise BudgetError('El objetivo requiere una partida bajo capítulo')
        if type(task['duration']) is not int or not 0 <= task['duration'] <= MAX_DAYS:
            raise BudgetError('Duración inválida; usa de 0 a 36600 días laborables')
        for field in ('quantity', 'price'):
            value = _decimal(task[field], 'Objetivo ' + field)
            if value < 0 or value > Decimal('1e18'):
                raise BudgetError('Cantidad o precio objetivo fuera de límites')
        if not isinstance(task['predecessors'], list):
            raise BudgetError('Precedencias inválidas')
        seen = set()
        for link in task['predecessors']:
            if (not isinstance(link, dict) or set(link) != {'relation_id', 'lag'}
                    or not isinstance(link['relation_id'], str)
                    or link['relation_id'] in seen
                    or type(link['lag']) is not int or not 0 <= link['lag'] <= MAX_DAYS):
                raise BudgetError('Enlace fin-inicio inválido; desfase no negativo en días laborables')
            seen.add(link['relation_id'])
            edges += 1
        tasks[rid] = task
    if edges > 100000:
        raise BudgetError('Demasiadas precedencias')
    successors = {rid: [] for rid in tasks}
    indegree = {rid: len(t['predecessors']) for rid, t in tasks.items()}
    for rid, task in tasks.items():
        for link in task['predecessors']:
            if link['relation_id'] not in tasks:
                raise BudgetError('Actividad precedente inexistente')
            successors[link['relation_id']].append((rid, link['lag']))
    ready = [rid for rid in tasks if indegree[rid] == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        rid = heapq.heappop(ready)
        order.append(rid)
        for child, _ in successors[rid]:
            indegree[child] -= 1
            if not indegree[child]:
                heapq.heappush(ready, child)
    if len(order) != len(tasks):
        raise BudgetError('Dependencias circulares en el plan avanzado')
    return tasks, successors, order


def _schedule(budget, data):
    tasks, successors, order = _validated(budget, data)
    calendar = validate_calendar(budget)
    if not tasks:
        return []
    early, finish = {}, {}
    for rid in order:
        task = tasks[rid]
        early[rid] = max((finish[p['relation_id']] + p['lag'] for p in task['predecessors']), default=0)
        finish[rid] = early[rid] + task['duration']
        if finish[rid] > MAX_DAYS:
            raise BudgetError('El plan supera 36600 días laborables')
    end = max(finish.values())
    latest = {}
    for rid in reversed(order):
        latest_finish = min((latest[child] - lag for child, lag in successors[rid]), default=end)
        latest[rid] = latest_finish - tasks[rid]['duration']
    # Build a bounded calendar once, rather than scan per activity.
    holidays = set(calendar['holidays'])
    day = iso(data['start'])
    days = []
    for _ in range(366001):
        if day.weekday() in calendar['weekdays'] and day.isoformat() not in holidays:
            days.append(day.isoformat())
            if len(days) > end:
                break
        try:
            day += timedelta(days=1)
        except OverflowError as exc:
            raise BudgetError('El plan excede el calendario admitido') from exc
    if len(days) <= end:
        raise BudgetError('Calendario sin suficientes días laborables')
    policy = calculator_for(budget).policy
    rows = []
    for rid in order:
        task = tasks[rid]
        duration = task['duration']
        quantity = policy.quantity(_decimal(task['quantity'], 'Cantidad objetivo'))
        price = policy.price(_decimal(task['price'], 'Precio objetivo'))
        rows.append(dict(relation_id=rid, duration=duration, quantity=quantity, price=price,
            amount=policy.amount(quantity * price * budget._relation(rid).factor),
            start=days[early[rid]], finish=days[max(early[rid], finish[rid]-1)],
            finish_boundary=days[finish[rid]], latest_start=days[latest[rid]],
            latest_finish=days[max(latest[rid], latest[rid]+duration-1)],
            slack=latest[rid]-early[rid], critical=latest[rid]==early[rid]))
    return rows


def validate(budget):
    data = state(budget)
    _schedule(budget, data)
    return data


def schedule(budget):
    return _schedule(budget, state(budget))


def _save(budget, data):
    _schedule(budget, data)  # Validate before mutating, including cycles/calendar.
    budget.project_metadata[KEY] = json.dumps(data, ensure_ascii=False, separators=(',', ':'))


def configure(budget, start):
    data = state(budget)
    data['start'] = start
    _save(budget, data)


def set_task(budget, relation_id, duration, quantity, price, predecessors=None):
    data = state(budget)
    task = dict(relation_id=relation_id, duration=duration,
                quantity=str(_decimal(quantity, 'Cantidad objetivo')),
                price=str(_decimal(price, 'Precio objetivo')),
                predecessors=[] if predecessors is None else predecessors)
    data['tasks'] = [t for t in data['tasks'] if t['relation_id'] != relation_id] + [task]
    _save(budget, data)


def remove_task(budget, relation_id):
    data = state(budget)
    if not any(t['relation_id'] == relation_id for t in data['tasks']):
        raise BudgetError('Actividad inexistente')
    data['tasks'] = [t for t in data['tasks'] if t['relation_id'] != relation_id]
    _save(budget, data)
