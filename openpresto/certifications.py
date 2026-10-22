"""Independent certification-at-origin calculation, manual pp.116–119.

No dates, phases, official-contract adjustments or guessed chapter rollups.
This view does not mutate the source budget or reuse budget quantities as
certified quantities. The project stores inputs separately; Qt uses this view.
"""
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from collections.abc import Mapping

from .budget import Budget, BudgetError, _decimal
from .calculations import calculator_for as BudgetCalculator, CalculationPolicy


@dataclass(frozen=True)
class CertifiedAmount:
    relation_id: str
    budget_quantity: Decimal
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal

    @property
    def exceeds_budget(self) -> bool:
        return self.quantity > self.budget_quantity


class CertificationAtOrigin:
    """Explicit cumulative quantities keyed by relation, never by concept code.

    Concept roles must be explicitly identified as chapter/partida; ambiguous
    numeric BC3 natures are not inferred. Non-unit relation factors require a
    separate reference contract and are rejected, rather than double-counted.
    The current calculation policy governs rounding; its full equivalence with
    certification rounding in Presto has not yet been independently observed.
    """
    def __init__(self, budget: Budget, quantities: Mapping,
                 policy: CalculationPolicy | None = None):
        if not isinstance(budget, Budget):
            raise TypeError('budget debe ser Budget')
        if not isinstance(quantities, Mapping):
            raise TypeError('Las cantidades certificadas deben ser un mapa por relación')
        self.budget = budget
        self.calculator = BudgetCalculator(budget, policy)
        self.quantities = MappingProxyType({key: _decimal(value, 'CanCert')
                                            for key, value in quantities.items()})
        for relation_id in self.quantities:
            self._eligible(relation_id)

    def _eligible(self, relation_id):
        relation = self.budget._relation(relation_id)
        parent = self.budget.concepts[relation.parent_code]
        child = self.budget.concepts[relation.child_code]
        explicit_role = self.budget.project_metadata.get('certification_role:' + relation_id)
        if parent.nature.strip().casefold() not in ('capitulo', 'capítulo') or (child.nature.strip().casefold() != 'partida' and explicit_role != 'partida'):
            raise BudgetError('Solo se admite certificación explícita de partidas directamente bajo capítulos')
        if relation.factor != 1:
            raise BudgetError('El factor de relación en certificaciones necesita contraste adicional')
        return relation

    def relation(self, relation_id: str) -> CertifiedAmount:
        relation = self._eligible(relation_id)
        policy = self.calculator.policy
        quantity = policy.quantity(self.quantities.get(relation_id, Decimal('0')))
        override = self.budget.project_metadata.get('certification_price:' + relation_id)
        if override is not None:
            price = policy.price(_decimal(override, 'Precio de certificación'))
        else:
            price = (self.calculator.valuation_price(relation_id)
                     if self.budget.project_metadata.get('engine') == 'native-v1'
                     else self.calculator.price(relation.child_code))
        return CertifiedAmount(relation_id, self.calculator.quantity(relation_id),
                               quantity, price, policy.amount(quantity * price))

    def rows(self) -> tuple[CertifiedAmount, ...]:
        # Revalidate references on each use: the source budget may have changed.
        return tuple(self.relation(key) for key in self.quantities)
