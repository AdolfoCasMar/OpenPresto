"""Operaciones de edición sobre copias validadas, sin dependencias gráficas."""
from dataclasses import replace
from uuid import uuid4
from .budget import BudgetError
from .history_snapshots import capture_snapshot as dumps, restore_snapshot as loads
from .calculations import calculator_for


def replace_text(budget, search, replacement, codes=None):
    if not search:
        raise BudgetError('El texto buscado no puede estar vacío')
    result = loads(dumps(budget))
    selected = set(result.concepts if codes is None else codes)
    for code in selected:
        if code not in result.concepts:
            raise BudgetError('Concepto desconocido: ' + code)
        concept = result.concepts[code]
        result.concepts[code] = replace(concept,
            summary=concept.summary.replace(search, replacement),
            text=concept.text.replace(search, replacement))
    return result


def reorder_children(budget, parent, key='code', reverse=False):
    result = loads(dumps(budget))
    calculator = calculator_for(result)
    fields = {
        'code': lambda r: r.child_code.casefold(),
        'summary': lambda r: result.concepts[r.child_code].summary.casefold(),
        'price': lambda r: calculator.price(r.child_code),
        'quantity': lambda r: calculator.quantity(r.id),
    }
    if key not in fields or parent not in result.concepts:
        raise BudgetError('Ordenación no válida')
    rows = sorted((r for r in result.relations if r.parent_code == parent),
                  key=fields[key], reverse=reverse)
    positions = {r.id: i for i, r in enumerate(rows, 1)}
    result.relations = [replace(r, position=positions[r.id]) if r.id in positions else r
                        for r in result.relations]
    result._relations_by_id = {r.id: r for r in result.relations}
    return loads(dumps(result))


def copy_measurements(budget, source, destination):
    result = loads(dumps(budget))
    result._relation(source)
    result._relation(destination)
    if source == destination:
        raise BudgetError('Selecciona dos relaciones diferentes')
    rows = [row for row in result.measurements if row.relation_id == source]
    removed_ids={row.id for row in result.measurements if row.relation_id == destination}
    result.measurements = [row for row in result.measurements if row.relation_id != destination]
    for mid in removed_ids:
        result.project_metadata.pop('measurement_kind:' + mid,None)
    result._measurements_by_id = {row.id for row in result.measurements}
    result.bc3_measurements.pop(destination, None)
    if source in result.bc3_measurements:
        from dataclasses import replace as record_replace
        record = result.bc3_measurements[source]
        target = result._relation(destination)
        # Rebuild with destination identifiers using the native record contract.
        from .bc3_measurements import rebuild_record
        copied = rebuild_record(record_replace(record, reference=target.parent_code + "\\" + target.child_code), list(record.lines))
        result.bc3_measurements[destination] = copied
    else:
        for row in rows:
            copied = replace(row, id=uuid4().hex, relation_id=destination)
            result.add_measurement(copied)
            kind = result.project_metadata.get('measurement_kind:' + row.id)
            if kind:
                result.project_metadata['measurement_kind:' + copied.id] = kind
        if not rows:
            relation = result._relation(destination)
            updated = replace(relation, quantity=result.relation_quantity(source))
            result.relations[result.relations.index(relation)] = updated
            result._relations_by_id[destination] = updated
    return loads(dumps(result))
