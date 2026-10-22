"""Certification application rules shared by graphical and headless clients."""
from .budget import BudgetError, _decimal
from .certifications import CertificationAtOrigin
from .certification_phases import CertificationSchedule, project_phases
from .certification_measurements import find, replace


def set_schedule(budget, start_date, end_dates, current_phase):
    old = budget.certification_schedule
    schedule = CertificationSchedule(start_date, tuple(end_dates), current_phase)
    entered = any(budget.phase_certified_quantities.values())
    if old and entered and ((old.start_date is not None and schedule.start_date != old.start_date)
            or schedule.end_dates[:len(old.end_dates)] != old.end_dates):
        raise BudgetError('Con cantidades registradas solo se pueden añadir fases al final; no se desplazan datos automáticamente.')
    budget.certification_schedule = schedule
    project_phases(budget)


def set_price(budget, relation_id, value=None):
    CertificationAtOrigin(budget, {})._eligible(relation_id)
    key = 'certification_price:' + relation_id
    if value is None:
        budget.project_metadata.pop(key, None)
    else:
        budget.project_metadata[key] = str(_decimal(value, 'Precio de certificación'))
    CertificationAtOrigin(budget, {}).relation(relation_id)
    project_phases(budget)


def set_phase_quantity(budget, phase, relation_id, value=None):
    if budget.certification_schedule is None:
        raise BudgetError('Configura el calendario antes de introducir cantidades')
    budget.certification_schedule.validate_phase(phase)
    CertificationAtOrigin(budget, {})._eligible(relation_id)
    if find(budget, phase, relation_id) is not None:
        raise BudgetError('Edita las líneas del periodo para cambiar esta cantidad.')
    rows = budget.phase_certified_quantities.setdefault(phase, {})
    if value is None:
        rows.pop(relation_id, None)
        if not rows:
            budget.phase_certified_quantities.pop(phase, None)
    else:
        rows[relation_id] = _decimal(value, 'Cantidad certificada del periodo')
        budget.certified_quantities.pop(relation_id, None)
    project_phases(budget)


def set_origin_quantity(budget, relation_id, value=None):
    quantities = dict(budget.certified_quantities)
    if value is None:
        quantities.pop(relation_id, None)
    else:
        quantities[relation_id] = _decimal(value, 'Cantidad certificada a origen')
    cert = CertificationAtOrigin(budget, quantities)
    cert.rows()
    budget.certified_quantities = dict(cert.quantities)
    project_phases(budget)


def replace_lines(budget, phase, relation_id, rows):
    replace(budget, phase, relation_id, rows)
    project_phases(budget)

def editable_lines(budget, phase, relation_id):
    from .budget import BudgetMeasurement
    from .certification_measurements import encode_line
    group = find(budget, phase, relation_id)
    if group is not None:
        return group['rows']
    quantity = budget.phase_certified_quantities.get(phase, {}).get(relation_id)
    return [encode_line(BudgetMeasurement(relation_id,
        'Cantidad del periodo anterior al desglose', quantity))] if quantity is not None else []

def period_rows(budget, phase):
    view=project_phases(budget)
    if view is None:return []
    view.schedule.validate_phase(phase)
    eligible=CertificationAtOrigin(budget,{})
    result=[]
    for relation in budget.relations:
        try:eligible._eligible(relation.id)
        except BudgetError:continue
        approved=view.relation(relation.id)
        entered=budget.phase_certified_quantities.get(phase,{}).get(relation.id,'')
        period=CertificationAtOrigin(budget,{relation.id:entered if entered!='' else '0'}).relation(relation.id)
        result.append((relation.id,(relation.parent_code,relation.child_code,budget.relation_quantity(relation.id),entered,
            approved.cumulative_quantity,approved.unit_price,approved.previous_amount,approved.cumulative_amount,approved.current_amount,period.amount)))
    return result
