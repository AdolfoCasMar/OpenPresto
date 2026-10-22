"""Editable certification measurements, separate from budget measurements."""
import json
from dataclasses import asdict
from decimal import Decimal
from .budget import BudgetError, BudgetMeasurement

KEY = 'certification_lines_v1'


def groups(budget):
    try:
        data = json.loads(budget.project_metadata.get(KEY, '[]'))
        if not isinstance(data, list):
            raise ValueError('lista esperada')
        seen = set()
        for group in data:
            if not isinstance(group, dict):
                raise ValueError('grupo inválido')
            if set(group) != {'phase', 'relation', 'rows'} or type(group['phase']) is not int or not isinstance(group['rows'], list):
                raise ValueError('grupo inválido')
            key = group['phase'], group['relation']
            if key in seen:
                raise ValueError('grupo repetido')
            seen.add(key)
            totals(group['rows'], group['relation'])
        return data
    except (ValueError, TypeError, KeyError) as exc:
        raise BudgetError('Líneas de certificación inválidas: ' + str(exc)) from exc


def totals(rows, rid):
    running = Decimal(0)
    segment = Decimal(0)
    values = []
    ids = set()
    for row in rows:
        if not isinstance(row, dict):
            raise BudgetError('Línea inválida')
        if set(row) != {'measurement', 'kind', 'source'} or type(row['kind']) is not int or row['kind'] not in (0, 1, 2) or not isinstance(row['source'], dict):
            raise BudgetError('Tipo de línea de certificación inválido')
        data = dict(row['measurement'])
        data['annulled_dimensions'] = tuple(data.get('annulled_dimensions', ()))
        line = BudgetMeasurement(**data)
        if line.relation_id != rid or line.id in ids:
            raise BudgetError('Referencia o identificador de línea inválido')
        ids.add(line.id)
        if row['kind'] == 1:
            value = running
        elif row['kind'] == 2:
            value = segment
            segment = Decimal(0)
        else:
            value = line.partial(2)
            running += value
            segment += value
        values.append(value)
    return running, values


def encode_line(line, kind=0, source=None):
    data = asdict(line)
    for key, value in data.items():
        if isinstance(value, Decimal):
            data[key] = str(value)
    return {'measurement': data, 'kind': kind, 'source': source or {}}


def find(budget, phase, rid):
    return next((g for g in groups(budget) if (g['phase'], g['relation']) == (phase, rid)), None)


def validate(budget):
    for group in groups(budget):
        if budget.certification_schedule is None:
            raise BudgetError('Líneas de certificación sin calendario')
        budget.certification_schedule.validate_phase(group['phase'])
        budget._relation(group['relation'])
        quantity = budget.phase_certified_quantities.get(group['phase'], {}).get(group['relation'])
        if quantity != totals(group['rows'], group['relation'])[0]:
            raise BudgetError('La cantidad certificada no coincide con sus líneas')


def replace(budget, phase, rid, rows):
    from .certifications import CertificationAtOrigin
    if budget.certification_schedule is None:
        raise BudgetError('Configura el calendario antes de introducir líneas')
    budget.certification_schedule.validate_phase(phase)
    CertificationAtOrigin(budget, {})._eligible(rid)
    quantity, _ = totals(rows, rid)
    data = [g for g in groups(budget) if (g['phase'], g['relation']) != (phase, rid)]
    data.append({'phase': phase, 'relation': rid, 'rows': rows})
    budget.project_metadata[KEY] = json.dumps(data, ensure_ascii=False)
    budget.phase_certified_quantities.setdefault(phase, {})[rid] = quantity
    budget.certified_quantities.pop(rid, None)
