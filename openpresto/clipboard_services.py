"""Portapapeles de conceptos nativos y texto tabular."""
import json
from dataclasses import replace
from uuid import uuid4
from PySide6.QtCore import QMimeData
from PySide6.QtWidgets import QApplication, QLineEdit, QPlainTextEdit
from .budget import BudgetRelation, BudgetError
from .storage import dumps, loads

MIME = 'application/x-openpresto-concepts+json'


def copy(host, cut=False):
    focus = QApplication.focusWidget()
    if isinstance(focus, (QLineEdit, QPlainTextEdit)):
        focus.cut() if cut else focus.copy()
        return
    table = host._selected_table()
    if table is None:
        return
    rows = sorted({index.row() for index in table.selectedIndexes() if not table.isRowHidden(index.row())})
    if not rows:
        return
    host.flush_text()
    mime = QMimeData()
    mime.setText('\n'.join('\t'.join(table.item(row,col).text() if table.item(row,col) else ''
                  for col in range(table.columnCount())) for row in rows))
    if table is host.prices:
        relations = [host._visible_relations[row] for row in rows]
        payload = {'project': dumps(host.budget), 'relations': [r.id for r in relations],
                   'document_base': str(host.path.parent.resolve()) if host.path else None}
        mime.setData(MIME, json.dumps(payload).encode('utf-8'))
        if cut:
            if any(host.budget.has_certification(r.id) for r in relations):
                host._error('No se cortan relaciones con certificaciones asociadas')
                return
            def remove_relations():
                result = loads(dumps(host.budget))
                ids = {r.id for r in relations}
                result.relations = [r for r in result.relations if r.id not in ids]
                result._relations_by_id = {r.id:r for r in result.relations}
                result.measurements = [m for m in result.measurements if m.relation_id not in ids]
                result._measurements_by_id = {m.id for m in result.measurements}
                result.bc3_measurements = {rid:record for rid,record in result.bc3_measurements.items() if rid not in ids}
                host.budget = loads(dumps(result))
            host._transaction(remove_relations)
    elif table is host.measurements_table:
        keys = [host._measurement_keys[row] for row in rows]
        mime.setData(MIME,json.dumps({'type':'measurements','project':dumps(host.budget),'keys':keys}).encode('utf-8'))
        if cut:
            from .measurement_operations import remove_lines
            host._transaction(lambda: setattr(host,'budget',remove_lines(host.budget,keys)))
    elif cut:
        host._error('Cortar filas requiere seleccionar texto editable; las filas pueden copiarse.')
        return
    QApplication.clipboard().setMimeData(mime)


def paste(host):
    focus = QApplication.focusWidget()
    if isinstance(focus, (QLineEdit, QPlainTextEdit)):
        focus.paste()
        return
    mime = QApplication.clipboard().mimeData()
    if not mime.hasFormat(MIME):
        host._error('Selecciona un editor de texto o copia filas de Precios para pegar conceptos.')
        return
    def operation():
        if not host.current_code:
            raise BudgetError('Selecciona el nivel de destino')
        raw = bytes(mime.data(MIME))
        if len(raw) > 25 * 1024 * 1024:
            raise BudgetError('Portapapeles demasiado grande')
        payload = json.loads(raw)
        source = loads(payload['project'])
        if payload.get('type') == 'measurements':
            _paste_measurements(host,payload,source)
            return
        result = loads(dumps(host.budget))
        precision_keys = ('quantity_decimals', 'price_decimals', 'amount_decimals', 'economic_rounding', 'engine')
        if any(source.project_metadata.get(key) != result.project_metadata.get(key) for key in precision_keys):
            raise BudgetError('Las precisiones económicas de origen y destino son diferentes')
        selected = [source._relation(rid) for rid in payload['relations']]
        if any(source.has_certification(r.id) for r in selected):
            raise BudgetError('La copia de certificaciones requiere una operación específica de fases')
        needed = set()
        pending = [r.child_code for r in selected]
        while pending:
            code = pending.pop()
            if code in needed:
                continue
            needed.add(code)
            pending.extend(r.child_code for r in source.relations if r.parent_code == code)
        if any(source.has_certification(r.id) for r in source.relations if r.parent_code in needed):
            raise BudgetError('La descomposición contiene certificaciones que requieren tratamiento específico')
        for code in needed:
            concept = source.concepts[code]
            if code in result.concepts and result.concepts[code] != concept:
                raise BudgetError('Conflicto de concepto compartido: ' + code)
            if code not in result.concepts:
                result.add_concept(concept)
        existing_parents = {r.parent_code for r in result.relations}
        mapping = {}
        for code in needed & existing_parents:
            old = [(r.child_code, r.position, r.quantity, r.factor) for r in source.relations if r.parent_code == code]
            current = [(r.child_code, r.position, r.quantity, r.factor) for r in result.relations if r.parent_code == code]
            if sorted(old) != sorted(current):
                raise BudgetError('Descomposición diferente para el concepto compartido: ' + code)
        for relation in source.relations:
            if relation.parent_code in needed and relation.parent_code not in existing_parents:
                new = replace(relation, id=uuid4().hex)
                result.add_relation(new)
                mapping[relation.id] = new.id
        position = max((r.position for r in result.relations if r.parent_code == host.current_code), default=0)
        for relation in selected:
            position += 1
            new = replace(relation, parent_code=host.current_code, position=position, id=uuid4().hex)
            result.add_relation(new)
            mapping[relation.id] = new.id
        for row in source.measurements:
            if row.relation_id in mapping:
                copied = replace(row, relation_id=mapping[row.relation_id], id=uuid4().hex)
                result.add_measurement(copied)
                kind = source.project_metadata.get('measurement_kind:' + row.id)
                if kind:
                    result.project_metadata['measurement_kind:' + copied.id] = kind
        for rid, record in source.bc3_measurements.items():
            if rid in mapping:
                result.bc3_measurements[mapping[rid]] = record
        if source.percentage_profile != result.percentage_profile and any('%' in c for c in needed):
            raise BudgetError('Los perfiles porcentuales del origen y destino difieren')
        if source.indirect_config != result.indirect_config or source.locked_prices != result.locked_prices:
            raise BudgetError('La copia entre configuraciones económicas diferentes requiere normalizar sus perfiles')
        from pathlib import Path
        for row in source.documents:
            if row['concept'] not in needed:
                continue
            document = dict(row)
            path = Path(document['path'])
            if not path.is_absolute():
                base = payload.get('document_base')
                if not isinstance(base,str):
                    raise BudgetError('No se puede resolver un documento relativo del portapapeles')
                document['path'] = str(Path(base) / path)
            if document not in result.documents:
                result.documents.append(document)
        host.budget = loads(dumps(result))
    try:
        host._transaction(operation)
    except (KeyError, TypeError, UnicodeError) as exc:
        host._error('Portapapeles inválido: ' + str(exc))


def _paste_measurements(host,payload,source):
    from .bc3_measurements import parse_measurement,rebuild_record
    target = host.selected_relation
    if target is None:
        raise BudgetError('Selecciona una partida de destino')
    result = loads(dumps(host.budget))
    relation = result._relation(target)
    keys = payload['keys']
    if not isinstance(keys,list) or not keys:
        raise BudgetError('El portapapeles no contiene líneas de medición')
    native = [identity for kind,identity in keys if kind == 'native']
    imported = [(kind,identity) for kind,identity in keys if kind != 'native']
    if native and imported:
        raise BudgetError('No se mezclan motores de medición en una misma relación')
    if native:
        if target in result.bc3_measurements:
            raise BudgetError('El destino utiliza mediciones BC3; usa Copiar mediciones para sustituirlas')
        for identity in native:
            row = next((m for m in source.measurements if m.id == identity),None)
            if row is None:
                raise BudgetError('Línea de medición del portapapeles inexistente')
            copied = replace(row,id=uuid4().hex,relation_id=target)
            result.add_measurement(copied)
            kind = source.project_metadata.get('measurement_kind:' + row.id)
            if kind:
                result.project_metadata['measurement_kind:' + copied.id] = kind
    else:
        if any(m.relation_id == target for m in result.measurements):
            raise BudgetError('El destino utiliza mediciones nativas; usa Copiar mediciones para sustituirlas')
        record = result.bc3_measurements.get(target)
        if record is None:
            record = parse_measurement(relation.parent_code + '\\' + relation.child_code + '|||',
                                       zero_dimensions_as_blank=result.bc3_zero_dimensions_as_blank,
                                       native_formulas=result.project_metadata.get('engine') == 'native-v1')
        lines = list(record.lines)
        for rid,index in imported:
            origin = source.bc3_measurements[rid]
            if type(index) is not int or not 0 <= index < len(origin.lines):
                raise BudgetError('Índice de medición del portapapeles inválido')
            if (origin.zero_dimensions_as_blank != record.zero_dimensions_as_blank
                    or origin.native_formulas != record.native_formulas):
                raise BudgetError('Los perfiles dimensionales BC3 del origen y destino son diferentes')
            lines.append(origin.lines[index])
        result.bc3_measurements[target] = rebuild_record(record,lines)
    host.budget = loads(dumps(result))
