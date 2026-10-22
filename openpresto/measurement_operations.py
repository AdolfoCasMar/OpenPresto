"""Operaciones sobre líneas de medición nativas y BC3."""
from dataclasses import replace
from uuid import uuid4
from .budget import BudgetError, BudgetMeasurement
from .history_snapshots import capture_snapshot as dumps, restore_snapshot as loads


def insert_subtotal(budget, relation_id, accumulated=False):
    result = loads(dumps(budget))
    result._relation(relation_id)
    if relation_id in result.bc3_measurements:
        from .bc3_measurements import BC3MeasurementLine, rebuild_record
        record = result.bc3_measurements[relation_id]
        line = BC3MeasurementLine('2' if accumulated else '1', 'Subtotal', '', '', '', '', None)
        result.bc3_measurements[relation_id] = rebuild_record(record, [*record.lines, line])
    else:
        line = BudgetMeasurement(relation_id, comment='Subtotal acumulado' if accumulated else 'Subtotal parcial', n_lines='0')
        result.add_measurement(line)
        result.project_metadata['measurement_kind:' + line.id] = '2' if accumulated else '1'
    return result


def _native_display_rows(budget, relation_id=None):
    from decimal import Decimal
    totals = {}
    for row in budget.measurements:
        if relation_id is not None and row.relation_id != relation_id:
            continue
        total, partial = totals.get(row.relation_id, (Decimal('0'), Decimal('0')))
        kind = budget.project_metadata.get('measurement_kind:' + row.id, '')
        if kind in ('1','2'):
            values = ('', total if kind == '2' else partial,
                      'Subtotal acumulado' if kind == '2' else 'Subtotal parcial')
            partial = Decimal('0')
        else:
            value = budget.measurement_partial(row)
            total += value
            partial += value
            values = (value, '', 'Fórmula' if row.formula else 'Normal')
        totals[row.relation_id] = (total, partial)
        yield row.id, values


def native_displays(budget):
    """Return all native line values in one pass, with totals per relationship."""
    return dict(_native_display_rows(budget))


def native_display(budget, measurement_id):
    target = next((m for m in budget.measurements if m.id == measurement_id), None)
    if target is not None:
        for identity, values in _native_display_rows(budget, target.relation_id):
            if identity == measurement_id:
                return values
    raise BudgetError('Medición desconocida')


def move_native_line(budget, measurement_id, delta):
    result = loads(dumps(budget))
    row = next((m for m in result.measurements if m.id == measurement_id),None)
    if row is None or delta not in (-1,1):
        raise BudgetError('Movimiento de medición inválido')
    indices=[i for i,m in enumerate(result.measurements) if m.relation_id == row.relation_id]
    source=indices.index(result.measurements.index(row))
    destination=source+delta
    if 0 <= destination < len(indices):
        a,b=indices[source],indices[destination]
        result.measurements[a],result.measurements[b]=result.measurements[b],result.measurements[a]
    return result


def remove_lines(budget, keys):
    result = loads(dumps(budget))
    native_ids = {identity for kind,identity in keys if kind == 'native'}
    affected = {m.relation_id for m in result.measurements if m.id in native_ids}
    result.measurements = [m for m in result.measurements if m.id not in native_ids]
    result._measurements_by_id = {m.id for m in result.measurements}
    for mid in native_ids:
        result.project_metadata.pop('measurement_kind:' + mid,None)
    for rid in affected:
        if not any(m.relation_id == rid for m in result.measurements):
            old = result._relation(rid)
            updated = replace(old,quantity='0')
            result.relations[result.relations.index(old)] = updated
            result._relations_by_id[rid] = updated
    grouped = {}
    for kind,identity in keys:
        if kind != 'native':
            grouped.setdefault(kind,set()).add(identity)
    from .bc3_measurements import rebuild_record,BC3MeasurementLine
    for rid,indices in grouped.items():
        record = result.bc3_measurements[rid]
        rows = [row for i,row in enumerate(record.lines) if i not in indices]
        if not rows:
            rows = [BC3MeasurementLine('','','0','','','',None)]
        result.bc3_measurements[rid] = rebuild_record(record,rows)
    return loads(dumps(result))
