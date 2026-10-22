"""Operaciones jerárquicas independientes con preservación de identificadores."""
from dataclasses import replace
from uuid import uuid4
from .budget import BudgetError
from .history_snapshots import capture_snapshot as dumps, restore_snapshot as loads


def move_relation(budget, relation_id, parent_code, position):
    result = loads(dumps(budget))
    relation = result._relation(relation_id)
    if parent_code not in result.concepts or type(position) is not int or position < 1:
        raise BudgetError('Destino o posición no válidos')
    result.relations = [r for r in result.relations if r.id != relation_id]
    result._relations_by_id.pop(relation_id)
    destination = sorted((r for r in result.relations if r.parent_code == parent_code), key=lambda r:r.position)
    destination.insert(min(position - 1, len(destination)), replace(relation, parent_code=parent_code))
    updated = {r.id: replace(r, position=index) for index, r in enumerate(destination, 1)}
    result.relations = [updated.get(r.id, r) for r in result.relations]
    result._relations_by_id = {r.id:r for r in result.relations}
    result.add_relation(updated[relation_id])
    if relation_id in result.bc3_measurements:
        record=result.bc3_measurements[relation_id]
        reference=parent_code + chr(92) + relation.child_code
        result.bc3_measurements[relation_id]=replace(record,reference=reference,
            raw_body=reference + '|' + record.raw_body.split('|',1)[1])
    return loads(dumps(result))


def duplicate_concept(budget, code, new_code):
    result = loads(dumps(budget))
    if code not in result.concepts or new_code in result.concepts:
        raise BudgetError('Código original inexistente o código nuevo duplicado')
    result.add_concept(replace(result.concepts[code], code=new_code))
    from .concept_keywords import validate as keyword_state,set_terms
    words=keyword_state(result)
    if code in words:set_terms(result,new_code,list(words[code]['terms']))
    for relation in list(result.relations):
        if relation.parent_code != code:
            continue
        new = replace(relation, id=uuid4().hex, parent_code=new_code)
        result.add_relation(new)
        for row in list(result.measurements):
            if row.relation_id == relation.id:
                copied = replace(row, id=uuid4().hex, relation_id=new.id)
                result.add_measurement(copied)
                kind = result.project_metadata.get('measurement_kind:' + row.id)
                if kind:
                    result.project_metadata['measurement_kind:' + copied.id] = kind
        if relation.id in result.bc3_measurements:
            from .bc3_measurements import rebuild_record
            record = result.bc3_measurements[relation.id]
            result.bc3_measurements[new.id] = rebuild_record(
                replace(record, reference=new_code + '\\' + new.child_code), record.lines)
    for row in list(result.documents):
        if row['concept'] == code:
            result.documents.append(dict(row, concept=new_code))
    if code in result.locked_prices:
        result.locked_prices[new_code] = result.locked_prices[code]
    return loads(dumps(result))


def remove_relations(budget, relation_ids):
    result = loads(dumps(budget))
    selected = set(relation_ids)
    for rid in selected:
        result._relation(rid)
        if result.has_certification(rid):
            raise BudgetError('Vacía la certificación antes de eliminar relaciones')
    removed_measurements = {m.id for m in result.measurements if m.relation_id in selected}
    result.relations = [r for r in result.relations if r.id not in selected]
    result._relations_by_id = {r.id:r for r in result.relations}
    result.measurements = [m for m in result.measurements if m.relation_id not in selected]
    result._measurements_by_id = {m.id for m in result.measurements}
    for rid in selected:
        result.bc3_measurements.pop(rid,None)
    for mid in removed_measurements:
        result.project_metadata.pop('measurement_kind:' + mid,None)
    return loads(dumps(result))


def insert_relation(budget, relation):
    result = loads(dumps(budget))
    rows = sorted((r for r in result.relations if r.parent_code == relation.parent_code),key=lambda r:r.position)
    index = min(relation.position-1,len(rows))
    rows.insert(index,relation)
    updates = {r.id:replace(r,position=i) for i,r in enumerate(rows,1)}
    result.relations = [updates.get(r.id,r) for r in result.relations]
    result._relations_by_id = {r.id:r for r in result.relations}
    result.add_relation(updates[relation.id])
    return loads(dumps(result))


def remove_unused_concepts(budget, codes):
    result = loads(dumps(budget))
    selected = set(codes)
    for code in selected:
        if code not in result.concepts or code == result.root_code:
            raise BudgetError('No se elimina un concepto inexistente o la raíz')
        if any(code in (r.parent_code,r.child_code) for r in result.relations):
            raise BudgetError('El concepto está en uso: ' + code)
        if any(row['concept'] == code for row in result.documents):
            raise BudgetError('Retira los vínculos documentales del concepto: ' + code)
    for code in selected:
        del result.concepts[code]
    from .concept_keywords import KEY as keyword_key,validate as keyword_state
    if keyword_key in result.project_metadata:
        import json
        words=keyword_state(budget)
        result.project_metadata[keyword_key]=json.dumps({code:row for code,row in words.items() if code not in selected},ensure_ascii=False)
    return loads(dumps(result))
