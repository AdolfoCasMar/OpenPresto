"""Certification projection validated against saved PZH quantities and amounts.

Profiles are validated against examined saved quantities and amounts. Other
structures remain archived, never interpreted as certification by resemblance.
"""
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from .certifications import CertificationAtOrigin
from .certification_phases import CertificationSchedule, project_phases


def import_certifications(budget, reader, concepts, relation_fields, pairs):
    from .pzh_importer import _fields, _code, _unpack, PZHImportError, _relation_key
    eligible = {}
    for pair, relation in pairs.items():
        parent, child = pair[:2]
        if concepts[parent].get(2) == 4 and concepts[child].get(2) in (5, 10):
            eligible[pair] = relation
    if not eligible:
        return []
    phase_rows = {}
    phase_cumulative = {}
    schema = {1: 'H', **{i: 'd' for i in range(2, 12)}}
    for _, _, record in reader.records(18, 12):
        if len(record) < 29:
            raise PZHImportError('Clave de cantidades por fase PZH no admitida.')
        pair = _relation_key(_code(record[:13]), _code(record[13:26]),record[26:28])
        if pair not in eligible:
            continue
        number = record[28]
        fields = _fields(record[29:], schema, 'Cantidades PZH por fase')
        if 3 not in fields and 8 not in fields:
            continue  # This row carries other schemes, not certified quantities.
        if number == 0:
            raise PZHImportError('Fase PZH de certificación nula.')
        rid = eligible[pair].id
        rows = phase_rows.setdefault(number, {})
        if rid in rows:
            raise PZHImportError('Cantidad certificada PZH repetida en una fase.')
        rows[rid] = fields.get(3, Decimal('0')).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
        if 8 in fields:
            phase_cumulative[number, rid] = fields[8].quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
    origin = {relation.id: relation_fields[pair].get(15, Decimal('0')).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
              for pair, relation in eligible.items() if 15 in relation_fields[pair]}
    if not origin and not phase_rows:
        return []
    from .calculations import calculator_for, calculation_batch
    calculator=calculator_for(budget)
    with calculation_batch(calculator):
        for pair, relation in eligible.items():
            source = concepts[pair[1]]
            if source.get(15,3)==3:
                price=calculator.price(pair[1])
            else:
                price = source.get(10, source.get(9, Decimal('0')))
            budget.project_metadata['certification_price:' + relation.id] = str(price)
            budget.project_metadata['certification_role:' + relation.id] = 'partida'
    budget.project_metadata['pzh_certification_profile'] = '8x-observed-v1'
    # The explicit source price can differ from the current budget unit price.
    policy = CertificationAtOrigin(budget, {}).calculator.policy
    dates = {}
    declared_amounts = {}
    if phase_rows:
        for _, _, record in reader.records(17, 8):
            if len(record) < 4 or record[1] != 1 or record[0] == 0:
                raise PZHImportError('Fecha de certificación PZH no admitida.')
            number = record[0]
            if number in dates:
                raise PZHImportError('Fecha de fase PZH repetida.')
            serial, = _unpack(record, 2, 'H')
            dates[number] = (date(1979, 12, 31) + timedelta(days=serial)).isoformat()
            # Only the independently identified prefix is used for period checks.
            at = 4
            amount = Decimal('0')
            while at < len(record) and record[at] <= 5:
                tag = record[at]
                if tag not in (4, 5):
                    raise PZHImportError('Prefijo de importes de fase PZH desconocido.')
                value, = _unpack(record, at + 1, 'd')
                if tag == 5:
                    amount = Decimal(str(value))
                at += 9
            declared_amounts[number] = amount
        if not dates or sorted(dates) != list(range(1, len(dates) + 1)):
            raise PZHImportError('Calendario de fases PZH incompleto.')
        approved = reader.certification_phase
        if approved == 99:
            approved = len(dates)
        if not 0 <= approved <= len(dates):
            raise PZHImportError('Aprobación de certificación PZH fuera de calendario.')
        budget.certification_schedule = CertificationSchedule(None,
            tuple(dates[n] for n in range(1, len(dates) + 1)), approved)
        budget.phase_certified_quantities = phase_rows
        view = project_phases(budget)
        for number, rows in view.quantities.items():
            for rid in rows:
                cumulative = sum((v.get(rid, Decimal('0')) for n, v in view.quantities.items() if n <= number), Decimal('0'))
                saved = phase_cumulative.get((number, rid), Decimal('0'))
                if policy.quantity(cumulative) != policy.quantity(saved):
                    raise PZHImportError(f'Certificación PZH: acumulado distinto en fase {number}, relación {rid}.')
        for pair, relation in eligible.items():
            expected = relation_fields[pair].get(15, Decimal('0')).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
            if view.relation(relation.id).cumulative_quantity != policy.quantity(expected):
                raise PZHImportError(f'Certificación PZH: acumulado aprobado distinto en {pair[0]}/{pair[1]}.')
        for number, declared in declared_amounts.items():
            rows = CertificationAtOrigin(budget, phase_rows.get(number, {})).rows()
            calculated = sum((r.amount for r in rows), Decimal('0'))
            if policy.amount(calculated) != policy.amount(declared):
                raise PZHImportError(f'Certificación PZH: importe del periodo {number} difiere del guardado.')
        total = sum((view.relation(r.id).cumulative_amount for r in eligible.values()), Decimal('0'))
        note = f'Certificaciones importadas: {len(dates)} fases, aprobada {approved}; acumulado {total}. Inicio de primera fase desconocido, no inventado.'
    else:
        budget.certified_quantities = origin
        total = sum((r.amount for r in CertificationAtOrigin(budget, origin).rows()), Decimal('0'))
        note = f'Certificación a origen importada: {len(origin)} relaciones; acumulado {total}.'
    declared_total = concepts[reader.root].get(10, Decimal('0'))
    if policy.amount(total) != policy.amount(declared_total):
        raise PZHImportError(f'La certificación total convertida ({total}) difiere de la guardada en PZH ({declared_total}).')
    from .certification_measurements import encode_line, replace
    from .budget import BudgetMeasurement
    from .pzh_importer import MEASUREMENT_FIELDS
    detailed = {}
    for offset, identifier, record in sorted(reader.records(5, 12), key=lambda entry: (_unpack(reader.data, entry[0] + 8, 'I')[0], entry[1])):
        if len(record) < 30 or record[0] not in (0, 1, 2) or record[27:29] != b'  ':
            raise PZHImportError('Línea de certificación PZH no admitida.')
        pair = _relation_key(_code(record[1:14]), _code(record[14:27]),record[27:29])
        if pair not in eligible:
            raise PZHImportError('Línea certificada sin relación admitida.')
        phase, rid = record[29], eligible[pair].id
        fields = _fields(record[30:], MEASUREMENT_FIELDS, 'Línea certificada')
        dims = [fields.get(n) for n in range(12, 16)]
        formula = fields.get(5, '')
        n = dims[0] if dims[0] is not None else Decimal(1) if formula or any(x is not None for x in dims) else Decimal(0)
        line = BudgetMeasurement(rid, fields.get(4, ''), n,
            *(x if x else None for x in dims[1:]), id=f'pzh-cm{identifier}', formula=formula)
        source = {str(k): str(v) for k, v in fields.items()}
        source['offset'] = offset
        source['prefix'] = record[0]
        source['sequence'] = _unpack(reader.data, offset + 8, 'I')[0]
        detailed.setdefault((phase, rid), []).append(encode_line(line, fields.get(1, 0), source))
    from .certification_measurements import totals
    for (phase, rid), rows in detailed.items():
        if totals(rows, rid)[0] != policy.quantity(phase_rows.get(phase, {}).get(rid, Decimal(0))):
            raise PZHImportError(f'Las líneas certificadas no coinciden: {phase} {rid} {totals(rows, rid)[0]} != {phase_rows.get(phase, {}).get(rid)}')
        replace(budget, phase, rid, rows)
    if detailed:
        note += f' {sum(len(rows) for rows in detailed.values())} líneas detalladas en {len(detailed)} grupos.'
    return [note, 'Se conservan precios de certificación explícitos separados de los precios del presupuesto.']



