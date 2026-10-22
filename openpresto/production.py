"""Daily production records; quantities never post certificates or invoices."""
import json
from uuid import uuid4
from decimal import Decimal, localcontext
from .budget import BudgetError, _decimal, special_price_kind
from .planning import iso

KEY = 'production_v1'
HEADERS = ('Parte', 'Fecha', 'Equipo', 'Estado', 'Relación', 'Código', 'Resumen', 'Unidad', 'Cantidad', 'Nota', 'Fecha de anulación', 'Motivo de anulación')


def eligible(budget):
    return [r for r in budget.relations
            if budget.concepts[r.parent_code].nature.strip().casefold() in ('capitulo','capítulo')
            and (budget.concepts[r.child_code].nature.strip().casefold() == 'partida'
                 or budget.project_metadata.get('certification_role:'+r.id) == 'partida')
            and not special_price_kind(r.child_code)]


def validate(budget, data=None):
    try:
        data = json.loads(budget.project_metadata.get(KEY, '[]')) if data is None else data
        if not isinstance(data, list) or len(data) > 10000: raise BudgetError('Demasiados partes')
        ids, references, total = set(), set(), 0
        allowed = {r.id for r in eligible(budget)}
        for row in data:
            if not isinstance(row, dict) or set(row) != {'id','reference','date','team','note','status','lines','cancellation_date','cancellation_reason'}:
                raise BudgetError('Columnas de parte inválidas')
            for key in ('id','reference','team','note','cancellation_reason'):
                if not isinstance(row[key], str) or len(row[key]) > 10000: raise BudgetError('Texto de parte inválido')
            if not row['id'] or row['id'] in ids or not row['reference'].strip(): raise BudgetError('Identidad de parte inválida')
            ids.add(row['id']); iso(row['date'])
            ref = row['date'][:4], row['reference'].strip().casefold()
            if ref in references: raise BudgetError('Referencia de parte repetida en el año')
            references.add(ref)
            if row['status'] not in ('draft','posted','cancelled'): raise BudgetError('Estado de parte inválido')
            if row['status'] == 'cancelled':
                iso(row['cancellation_date'])
                if row['cancellation_date'] < row['date'] or not row['cancellation_reason'].strip(): raise BudgetError('Anulación sin fecha o motivo válido')
            elif row['cancellation_date'] is not None or row['cancellation_reason']:
                raise BudgetError('Anulación incompatible con el estado')
            lines = row['lines']
            if not isinstance(lines,list) or not lines: raise BudgetError('El parte necesita partidas')
            total += len(lines)
            if total > 100000: raise BudgetError('Demasiadas líneas de producción')
            seen = set()
            for line in lines:
                if not isinstance(line,dict) or set(line) != {'relation_id','quantity'}: raise BudgetError('Línea de producción inválida')
                rid = line['relation_id']
                if not isinstance(rid,str) or rid not in allowed or rid in seen: raise BudgetError('Partida inexistente, no elegible o repetida')
                seen.add(rid)
                if not isinstance(line['quantity'],str) or len(line['quantity']) > 100: raise BudgetError('Cantidad debe ser texto decimal')
                q = _decimal(line['quantity'], 'Cantidad producida')
                if not 0 < q <= Decimal('1e15') or q.as_tuple().exponent < -12: raise BudgetError('Cantidad fuera de rango')
        return data
    except (ValueError, TypeError) as exc:
        raise BudgetError('Partes de obra inválidos: '+str(exc)) from exc


def _save(budget, data):
    validate(budget, data)
    budget.project_metadata[KEY] = json.dumps(data, ensure_ascii=False)


def set_report(budget, reference, date, team, note, lines, report_id=None):
    data = validate(budget)
    old = next((r for r in data if r['id'] == report_id), None)
    if report_id is not None and old is None: raise BudgetError('Parte inexistente')
    if old and old['status'] != 'draft': raise BudgetError('Solo se editan borradores; anula el parte para corregirlo')
    row = dict(id=old['id'] if old else uuid4().hex, reference=reference, date=date, team=team, note=note,
               lines=lines, status='draft', cancellation_date=None, cancellation_reason='')
    _save(budget, [row if r['id']==row['id'] else r for r in data] if old else data+[row])


def set_status(budget, report_id, status, cancellation_date=None, reason=''):
    data = validate(budget)
    old = next((r for r in data if r['id']==report_id), None)
    if old is None: raise BudgetError('Parte inexistente')
    if not ((old['status']=='draft' and status=='posted') or (old['status'] in ('draft','posted') and status=='cancelled')):
        raise BudgetError('Transición de parte no permitida')
    row = dict(old, status=status, cancellation_date=cancellation_date, cancellation_reason=reason)
    _save(budget, [row if r['id']==report_id else r for r in data])


def report_rows(budget):
    rows=[]
    for r in sorted(validate(budget),key=lambda r:(r['date'],r['reference'])):
        for line in r['lines']:
            relation=budget._relation(line['relation_id']);concept=budget.concepts[relation.child_code]
            rows.append((r['reference'],r['date'],r['team'],{'draft':'Borrador','posted':'Confirmado','cancelled':'Anulado'}[r['status']],relation.id,concept.code,concept.summary,concept.unit,Decimal(line['quantity']),r['note'],r['cancellation_date'] or '',r['cancellation_reason']))
    return rows


def quantities(budget, as_of):
    """Current confirmed records up to a date, not historical state replay."""
    iso(as_of); values={}
    with localcontext() as context:
        context.prec=160
        for report in validate(budget):
            if report['status']!='posted' or report['date']>as_of: continue
            for line in report['lines']:
                rid=line['relation_id']; values[rid]=values.get(rid,Decimal(0))+Decimal(line['quantity'])
    return values
