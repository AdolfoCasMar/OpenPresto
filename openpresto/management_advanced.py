"""Actual payments and dated settlement, independent of Qt and bank interfaces.

Allocations settle only explicitly selected documents. A proforma is not an
invoice: converting it requires an explicit future accounting contract; no
automatic offsets or guessed tax/stock adjustments are performed here.
"""
import json
from decimal import Decimal
from uuid import uuid4

from .budget import BudgetError
from .calculations import calculator_for
from .planning import iso
from . import management

KEY = 'management_advanced_v1'


def state(budget):
    try:
        data = json.loads(budget.project_metadata.get(KEY, '{"payments":[]}'))
    except (ValueError, TypeError) as exc:
        raise BudgetError('Registro de pagos inválido') from exc
    if (not isinstance(data, dict) or set(data) != {'payments'}
            or not isinstance(data['payments'], list) or len(data['payments']) > 10000):
        raise BudgetError('Registro de pagos inválido')
    return data


def validate(budget):
    """Validate links, money precision and chronological outstanding balances."""
    base = management.validate(budget)
    documents = management.indexed(base['documents'])
    suppliers = management.indexed(base['suppliers'])
    data = state(budget)
    payments = management.indexed(data['payments'])
    policy = calculator_for(budget).policy
    from .management_schedule import validate as validate_schedules
    schedules=validate_schedules(budget)
    references, events = set(), []
    for document_id,record in schedules.items():
        if record['opening']:
            opening=record['opening']
            events.append((opening['date'],0,'opening',document_id,management.number(opening['paid'],'Apertura')))
    for row in payments.values():
        if set(row) != {'id', 'supplier_id', 'reference', 'date', 'method',
                        'allocations', 'status', 'cancellation_date', 'cancellation_reason'}:
            raise BudgetError('Pago inválido')
        if (row['supplier_id'] not in suppliers or row['status'] not in ('posted', 'cancelled')
                or not isinstance(row['reference'], str) or not row['reference'].strip()
                or not isinstance(row['method'], str) or not row['method'].strip()
                or not isinstance(row['allocations'], list) or not row['allocations']):
            raise BudgetError('Proveedor, referencia, medio o aplicaciones de pago inválidos')
        iso(row['date'])
        reference = (row['supplier_id'], row['date'][:4], row['reference'].strip().casefold())
        if reference in references:
            raise BudgetError('Referencia de pago repetida para ese proveedor y año')
        references.add(reference)
        if row['status'] == 'cancelled':
            if (iso(row['cancellation_date']) < iso(row['date'])
                    or not isinstance(row['cancellation_reason'], str)
                    or not row['cancellation_reason'].strip()):
                raise BudgetError('Anulación de pago sin fecha o motivo válidos')
        elif row['cancellation_date'] is not None or row['cancellation_reason'] is not None:
            raise BudgetError('Un pago vigente no tiene anulación')
        seen = set()
        for allocation in row['allocations']:
            if not isinstance(allocation, dict) or set(allocation) != {'document_id', 'amount'}:
                raise BudgetError('Aplicación de pago inválida')
            document_id = allocation['document_id']
            document = documents.get(document_id)
            schedule=schedules.get(document_id)
            if schedule and schedule['opening'] is None and Decimal(schedule['source_paid'])>0:
                raise BudgetError('Revisa el saldo de apertura importado antes de registrar pagos')
            if schedule and schedule['opening'] and iso(row['date'])<iso(schedule['opening']['date']):
                raise BudgetError('Pago anterior al inicio del seguimiento del saldo')
            if (document_id in seen or document is None
                    or document['kind'] not in ('invoice', 'proforma')
                    or document['supplier_id'] != row['supplier_id']
                    or iso(document['date']) > iso(row['date'])
                    or document['status'] == 'draft'
                    or (row['status'] == 'posted' and document['status'] != 'posted')):
                raise BudgetError('Documento de pago inexistente, repetido o incompatible')
            seen.add(document_id)
            amount = management.number(allocation['amount'], 'Importe pagado')
            if amount <= 0 or policy.amount(amount) != amount:
                raise BudgetError('El pago debe ser positivo y respetar la precisión monetaria')
            events.append((row['date'], 1, row['id'], document_id, amount))
            if row['status'] == 'cancelled':
                # Same-day payment precedes its reversal. Other payments that day
                # are conservatively checked before cancellations release balance.
                events.append((row['cancellation_date'], 2, row['id'], document_id, -amount))
    settled = {}
    for _, _, _, document_id, amount in sorted(events):
        settled[document_id] = settled.get(document_id, Decimal(0)) + amount
        total = management.document_amounts(budget, documents[document_id])[3]
        if settled[document_id] < 0 or settled[document_id] > total:
            raise BudgetError('Las aplicaciones de pago superan el importe pendiente del documento')
    return data


def _write(budget, data):
    previous = budget.project_metadata.get(KEY)
    budget.project_metadata[KEY] = json.dumps(data, ensure_ascii=False)
    try:
        validate(budget)
    except Exception:
        if previous is None:
            budget.project_metadata.pop(KEY, None)
        else:
            budget.project_metadata[KEY] = previous
        raise


def record_payment(budget, supplier_id, reference, date, allocations, method='Transferencia', payment_id=None):
    """Record an actual payment atomically; allocations are document_id/amount."""
    data = state(budget)
    identity = payment_id or uuid4().hex
    if any(row['id'] == identity for row in data['payments']):
        raise BudgetError('Un pago registrado no se edita; anúlalo explícitamente')
    # Store Decimal input canonically; never store binary floating-point money.
    normalized = []
    if not isinstance(allocations, list):
        raise BudgetError('Las aplicaciones deben ser una lista')
    for row in allocations:
        if not isinstance(row, dict) or set(row) != {'document_id', 'amount'}:
            raise BudgetError('Aplicación de pago inválida')
        normalized.append({'document_id': row['document_id'],
                           'amount': str(management.number(row['amount'], 'Importe pagado'))})
    data['payments'].append(dict(id=identity, supplier_id=supplier_id, reference=reference,
        date=date, method=method, allocations=normalized, status='posted',
        cancellation_date=None, cancellation_reason=None))
    _write(budget, data)
    return identity


def cancel_payment(budget, payment_id, date, reason):
    data = state(budget)
    row = next((row for row in data['payments'] if row['id'] == payment_id), None)
    if row is None or row['status'] != 'posted':
        raise BudgetError('Selecciona un pago vigente para anularlo')
    row.update(status='cancelled', cancellation_date=date, cancellation_reason=reason)
    _write(budget, data)


def record_payment_command(budget, supplier_id, reference, date, allocations, method='Transferencia', payment_id=None):
    record_payment(budget, supplier_id, reference, date, allocations, method, payment_id)


def settlement_rows(budget, as_of=None):
    """Rows: id, kind, reference, supplier, due, payable, paid, outstanding, overdue.

    Retentions remain excluded from the payable amount, as in management_v1.
    They are not implicitly released or recorded as payments.
    """
    data = validate(budget)
    if as_of is not None:
        iso(as_of)
    paid = {}
    from .management_schedule import state as schedule_state
    schedules=schedule_state(budget)
    documents=management.indexed(management.state(budget)['documents'])
    for identifier,record in schedules.items():
        opening=record['opening']
        if opening:
            if as_of is not None and opening['date']>as_of:
                document=documents[identifier]
                if document['status']=='posted' and document['date']<=as_of:
                    raise BudgetError('No hay un saldo histórico reconstruido anterior a la apertura')
                continue
            paid[identifier]=management.number(opening['paid'],'Apertura')
    for row in data['payments']:
        if as_of is not None and row['date'] > as_of:
            continue
        if row['status'] == 'cancelled' and (as_of is None or row['cancellation_date'] <= as_of):
            continue
        for allocation in row['allocations']:
            key = allocation['document_id']
            paid[key] = paid.get(key, Decimal(0)) + management.number(allocation['amount'], 'Pago')
    result = []
    for row in management.state(budget)['documents']:
        if (row['status'] != 'posted' or row['kind'] not in ('invoice', 'proforma')
                or (as_of is not None and row['date'] > as_of)):
            continue
        payable = management.document_amounts(budget, row)[3]
        schedule=schedules.get(row['id'])
        if schedule and schedule['opening'] is None and Decimal(schedule['source_paid'])>0:
            result.append((row['id'],row['kind'],row['reference'],row['supplier_id'],None,payable,None,None,False))
            continue
        amount_paid = paid.get(row['id'], Decimal(0))
        outstanding = payable - amount_paid
        due=row['due_date']
        if schedule:
            remaining_paid=amount_paid;due=None
            for item in sorted((d for d in schedule['dues'] if d['kind']=='normal'),key=lambda d:(d['date'],d['id'])):
                amount=Decimal(item['amount']);covered=min(amount,remaining_paid);remaining_paid-=covered
                if amount>covered and due is None:due=item['date']
        overdue = bool(as_of and due and due < as_of and outstanding > 0)
        result.append((row['id'], row['kind'], row['reference'], row['supplier_id'],
                       due, payable, amount_paid, outstanding, overdue))
    return result


def payment_rows(budget):
    """Rows: id, date, reference, supplier, method, amount, status, cancellation."""
    result = []
    for row in validate(budget)['payments']:
        amount = sum((management.number(a['amount'], 'Pago') for a in row['allocations']), Decimal(0))
        result.append((row['id'], row['date'], row['reference'], row['supplier_id'], row['method'],
                       amount, row['status'], row['cancellation_date']))
    return result


def cash_movements(budget):
    """Actual cash outflows positive, dated reversals negative; no forecasts."""
    result = []
    for row in validate(budget)['payments']:
        amount = sum((management.number(a['amount'], 'Pago') for a in row['allocations']), Decimal(0))
        result.append((row['date'], row['id'], row['reference'], row['supplier_id'], amount))
        if row['status'] == 'cancelled':
            result.append((row['cancellation_date'], row['id'], 'Anulación: ' + row['reference'], row['supplier_id'], -amount))
    return sorted(result)
