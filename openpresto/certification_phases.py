"""Independent numbered certification periods, documented manual pp.116–120.

Period quantities are attached to ordinal numbers, not date identifiers.
Project JSON and Qt use this view; full agenda operations remain separate.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from collections.abc import Mapping
from types import MappingProxyType

from .budget import BudgetError
from .certifications import CertificationAtOrigin


def project_phases(budget):
    """Validate the project phase view and prevent two modes on one relation."""
    from .certification_measurements import validate
    validate(budget)
    if budget.certification_schedule is None:
        if budget.phase_certified_quantities:
            raise BudgetError('Hay cantidades por fase sin calendario')
        return None
    view = PhasedCertification(budget, budget.certification_schedule, budget.phase_certified_quantities)
    entered = {rid for rows in view.quantities.values() for rid in rows}
    if entered.intersection(budget.certified_quantities):
        raise BudgetError('Una relación no puede tener certificación a origen y por fases simultáneamente')
    return view


def _date(value):
    if not isinstance(value, str):
        raise BudgetError('La fecha debe ser texto ISO YYYY-MM-DD')
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise BudgetError('Fecha de certificación no válida') from exc
    if parsed.isoformat() != value:
        raise BudgetError('La fecha debe usar YYYY-MM-DD')
    return parsed


@dataclass(frozen=True)
class CertificationSchedule:
    start_date: str | None
    end_dates: tuple[str, ...]
    current_phase: int

    def __post_init__(self):
        start = _date(self.start_date) if self.start_date is not None else None
        if not isinstance(self.end_dates, tuple):
            raise BudgetError('Las fechas de fase deben ser una tupla ordenada')
        dates = tuple(_date(value) for value in self.end_dates)
        if dates and ((start is not None and dates[0] < start) or any(b <= a for a,b in zip(dates, dates[1:]))):
            raise BudgetError('Las fases deben terminar en fechas distintas y crecientes desde el inicio')
        if type(self.current_phase) is not int or not 0 <= self.current_phase <= len(dates):
            raise BudgetError('Fase aprobada fuera del calendario; cero significa ninguna aprobada')

    def validate_phase(self, number):
        if type(number) is not int or not 1 <= number <= len(self.end_dates):
            raise BudgetError('Número de fase fuera del calendario')

    def period(self, number):
        self.validate_phase(number)
        start = (None if number == 1 and self.start_date is None else _date(self.start_date) if number == 1 else
                 _date(self.end_dates[number-2]) + timedelta(days=1))
        return start.isoformat() if start is not None else None, self.end_dates[number-1]

    def state(self, number):
        self.validate_phase(number)
        return 3 if number == self.current_phase else 0 if number < self.current_phase else 2


@dataclass(frozen=True)
class PhasedCertifiedAmount:
    relation_id: str
    current_phase: int
    phase_quantity: Decimal
    previous_quantity: Decimal
    cumulative_quantity: Decimal
    unit_price: Decimal
    previous_amount: Decimal
    cumulative_amount: Decimal
    current_amount: Decimal


class PhasedCertification:
    """Period quantities, accumulated only through the last approved phase.

    Raw Decimal quantities are accumulated then rounded with the explicit
    OpenPresto policy. Current amount is cumulative minus previous amount,
    rather than a second independent valuation of the period quantity.
    """
    def __init__(self, budget, schedule: CertificationSchedule, quantities: Mapping, policy=None):
        if not isinstance(schedule, CertificationSchedule):
            raise TypeError('schedule debe ser CertificationSchedule')
        if not isinstance(quantities, Mapping):
            raise TypeError('Las cantidades deben estar agrupadas por número de fase')
        self.budget = budget
        self.schedule = schedule
        self.base = CertificationAtOrigin(budget, {}, policy)
        copied = {}
        for number, rows in quantities.items():
            schedule.validate_phase(number)
            view = CertificationAtOrigin(budget, rows, policy)
            view.rows()
            copied[number] = view.quantities
        self.quantities = MappingProxyType(copied)

    def _cumulative(self, through):
        result = {}
        for number, rows in self.quantities.items():
            # Validate even future references after an external structure change.
            # References must remain valid, but recalculating every budget
            # measurement for every requested row would make large phases quadratic.
            for relation_id in rows:
                self.base._eligible(relation_id)
            if number <= through:
                for rid, value in rows.items():
                    result[rid] = result.get(rid, Decimal(0)) + value
        return result

    def relation(self, relation_id):
        current = self.schedule.current_phase
        policy = self.base.calculator.policy
        cumulative = CertificationAtOrigin(self.budget, self._cumulative(current), policy).relation(relation_id)
        previous = CertificationAtOrigin(self.budget, self._cumulative(max(0,current-1)), policy).relation(relation_id)
        phase_quantity = policy.quantity(self.quantities.get(current, {}).get(relation_id, Decimal(0)))
        return PhasedCertifiedAmount(relation_id, current, phase_quantity,
            previous.quantity, cumulative.quantity, cumulative.unit_price,
            previous.amount, cumulative.amount, policy.amount(cumulative.amount - previous.amount))
