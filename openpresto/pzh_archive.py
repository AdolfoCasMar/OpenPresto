"""Lossless, read-only preservation of an imported PZH source snapshot.

The snapshot is *not* a semantic conversion. Unknown records remain opaque and
must never be used as budget/certification inputs without a separate contract.
"""
from __future__ import annotations

import base64
import hashlib
import json
import zlib
from decimal import Decimal

from .budget import BudgetError


ARCHIVE_KEY = 'pzh_source_archive_v1'
MAX_SOURCE_BYTES = 64 * 1024 * 1024


def preserve_pzh_source(budget, reader) -> None:
    """Embed the exact source bytes and a bounded table inventory in metadata."""
    data = reader.data
    if len(data) > MAX_SOURCE_BYTES:
        raise BudgetError('PZH demasiado grande para conservación íntegra.')
    inventory = [{'table': i, 'records': count, 'data_start': start,
                  'data_end': end} for i, (count, start, end) in enumerate(reader.tables)]
    payload = {'format': 'pzh-source-snapshot-v1',
               'sha256': hashlib.sha256(data).hexdigest(),
               'bytes': len(data),
               'inventory': inventory,
               'encoding': 'zlib-base64',
               'data': base64.b64encode(zlib.compress(data, level=9)).decode('ascii')}
    budget.project_metadata[ARCHIVE_KEY] = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))


def pzh_archive_inventory(budget) -> dict | None:
    """Return source identity and table counts, never inferred table semantics."""
    payload = _payload(budget)
    if payload is None:
        return None
    return {key: payload[key] for key in ('format', 'sha256', 'bytes', 'inventory')}


def pzh_source_bytes(budget) -> bytes | None:
    """Recover the exact frozen source after size and digest validation."""
    payload = _payload(budget)
    if payload is None:
        return None
    try:
        packed = base64.b64decode(payload['data'], validate=True)
        decoder = zlib.decompressobj()
        data = decoder.decompress(packed, MAX_SOURCE_BYTES + 1)
        if (len(data) > MAX_SOURCE_BYTES or not decoder.eof or decoder.unused_data
                or decoder.unconsumed_tail):
            raise ValueError('contenido o límite incorrecto')
        data += decoder.flush()
    except (ValueError, zlib.error) as exc:
        raise BudgetError('Archivo PZH conservado dañado.') from exc
    if len(data) != payload['bytes'] or hashlib.sha256(data).hexdigest() != payload['sha256']:
        raise BudgetError('La huella del PZH conservado no coincide.')
    return data


def pzh_phase_line_inventory(budget) -> tuple[dict, ...]:
    """Consult known measurement fields in every source phase, read-only.

    These are budget measurement phases. They are not certification quantities.
    An undecoded record is reported by identity instead of guessed.
    """
    data = pzh_source_bytes(budget)
    if data is None:
        return ()
    from .pzh_importer import _Reader, _fields, _code, MEASUREMENT_FIELDS
    reader = _Reader(data)
    rows = []
    for offset, identifier, record in reader.records(4, 12):
        if len(record) < 30:
            rows.append({'id': identifier, 'offset': offset, 'status': 'undecoded'})
            continue
        row = {'id': identifier, 'offset': offset, 'phase': record[29],
               'status': 'decoded-fields'}
        try:
            row['parent'] = _code(record[1:14])
            row['child'] = _code(record[14:27])
            fields = _fields(record[30:], MEASUREMENT_FIELDS, 'medición archivada')
            row['fields'] = {str(tag): str(value) for tag, value in fields.items()}
        except BudgetError:
            row['status'] = 'undecoded'
        rows.append(row)
    return tuple(rows)


def _payload(budget):
    raw = budget.project_metadata.get(ARCHIVE_KEY)
    if raw is None:
        return None
    try:
        payload = json.loads(raw)
        if (payload['format'] != 'pzh-source-snapshot-v1'
                or payload['encoding'] != 'zlib-base64'
                or type(payload['bytes']) is not int
                or not 0 <= payload['bytes'] <= MAX_SOURCE_BYTES
                or len(payload['inventory']) != 24
                or len(payload['sha256']) != 64):
            raise ValueError('cabecera incorrecta')
        return payload
    except (KeyError, TypeError, ValueError) as exc:
        raise BudgetError('Metadatos del PZH conservado dañados.') from exc


def main(argv=None):
    """Inspect or recover an imported PZH snapshot without running Presto."""
    import argparse
    from .storage import load_budget
    parser = argparse.ArgumentParser(description='Consulta la instantánea PZH de un proyecto OpenPresto')
    parser.add_argument('project', help='Proyecto .openpresto.json importado')
    parser.add_argument('--phase-lines', action='store_true', help='Incluye los campos conocidos de líneas en todas las fases presupuestarias')
    parser.add_argument('--recover', metavar='NEW_FILE', help='Recupera los bytes originales en un archivo nuevo; nunca sobrescribe')
    args = parser.parse_args(argv)
    budget = load_budget(args.project)
    info = pzh_archive_inventory(budget)
    if info is None:
        parser.error('El proyecto no contiene instantánea PZH')
    if args.phase_lines:
        info['phase_lines'] = pzh_phase_line_inventory(budget)
    if args.recover:
        with open(args.recover, 'xb') as target:
            target.write(pzh_source_bytes(budget))
    print(json.dumps(info, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()


def import_summary(budget):
    """Describe this file's actual content, separately from general limitations."""
    inventory=pzh_archive_inventory(budget)
    counts={r['table']:r['records'] for r in inventory['inventory']} if inventory else {}
    notes=tuple(budget.import_warnings) or tuple(budget.project_metadata.get('pzh_import_notes','').splitlines())
    chosen=json.loads(budget.project_metadata.get('pzh_import_modules','null'))
    selected=set(chosen) if chosen is not None else {'certifications','planning','management'}
    from .pzh_operations import state, rejected_records
    data=state(budget)
    failed=[w for w in notes if 'IMPORTACIÓN PARCIAL' in w or 'REFERENCIAS SIN RESOLVER' in w or 'Tablas adicionales PZH con campos aún no convertidos:' in w]
    lines=[f"Presupuesto: {len(budget.concepts)} conceptos y {len(budget.relations)} relaciones.",
           f"Textos recuperados: {sum(bool(c.text) for c in budget.concepts.values())}.",
           f"Mediciones: {sum(len(r.lines) for r in budget.bc3_measurements.values()) + len(budget.measurements)} líneas."]
    for module,label in (('certifications','Certificaciones'),('planning','Planificación'),('management','Gestión')):
        if module not in selected:
            status='no seleccionado; original conservado'
        elif any(label+' no convertido:' in w for w in failed):
            status='no convertido; requiere revisión'
        elif module=='certifications':
            quantity=len(budget.certified_quantities)
            phases=len(budget.phase_certified_quantities)
            status=f'importadas ({quantity} partidas, {phases} fases)' if quantity or phases else 'sin cantidades certificadas recuperadas'
        elif module=='planning':
            phases=len(data.get('phases',[]));edges=len(data.get('precedences',[]))
            dated=sum(bool(r['planned_start'] or r['planned_finish'] or r['actual_start'] or r['actual_finish']) or any(Decimal(r[k])!=0 for k in ('objective_quantity','planned_quantity','objective_price')) for r in data.get('activities',[]))
            status=f'datos de origen consultables ({dated} actividades con datos, {phases} repartos, {edges} precedencias); copia nativa por separado' if phases or edges or dated else 'sin planificación guardada recuperada'
        elif not any(counts.get(t,0) for t in (10,11,13,14,15)):
            status='sin datos en este archivo'
        else:
            status=f"datos de origen consultables ({len(data.get('entities',[]))} entidades, {len(data.get('documents',[]))} documentos, {len(data.get('dues',[]))} vencimientos); conversión editable por separado"
        lines.append(label+': '+status+'.')
    from .pzh_native_modules import results,control_records
    conversions=results(budget)
    if conversions:
        from .management import state as purchases
        from .issued_management import state as issued
        from .planning_phases import state as phase_plan
        from .entities import validate as native_entities
        purchase=purchases(budget);sales=issued(budget);plan=phase_plan(budget)
        lines.append(f"Copias nativas editables: {len(native_entities(budget))} entidades, {len(purchase['contracts'])} contratos, {len(purchase['documents'])} documentos recibidos, {len(sales['documents'])} emitidos y {len(plan['tasks'])} actividades de planificación y {len(control_records(budget))} registros de control.")
        pending=sum(r['status']=='pending' for r in conversions)
        if pending:
            lines.append(f'{pending} conversiones pendientes. Consulta Informes → PZH · Conversiones nativas.')
            failed.append('Conversión nativa parcial')
    rejected=len(rejected_records(budget))
    if rejected:lines.append(f'Requieren revisión: {rejected} registros sin convertir. Consulta Gestión → Origen PZH → Sin convertir.')
    if failed:lines.append('Importación parcial: consulta los detalles antes de usar los resultados.')
    lines.append('Original completo conservado. Guarda una copia como proyecto OpenPresto.')
    return '\n'.join(lines), bool(failed or rejected)
