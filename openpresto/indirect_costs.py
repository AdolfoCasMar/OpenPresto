"""Partial, explicit budget valuation from the independent Presto 8.8 trials.

Direct partida prices remain direct; chapter relations use a rounded price
including indirect costs. This view does not change the project or its profile.
Chapter roles are supplied explicitly, never guessed from codes or nature.
"""
from decimal import Decimal

from .budget import Budget, BudgetError
from .calculations import BudgetCalculator, RelationAmount


def calculator_from_config(budget):
    config = budget.indirect_config
    if (not isinstance(config, dict) or set(config) !=
            {'profile', 'chapter_codes', 'rate', 'exclude_undecomposed'}
            or config['profile'] != 'presto88_default'
            or not isinstance(config['chapter_codes'], list)
            or not all(isinstance(c, str) for c in config['chapter_codes'])
            or len(set(config['chapter_codes'])) != len(config['chapter_codes'])
            or not isinstance(config['rate'], str)):
        raise BudgetError('Configuración de indirectos no compatible')
    if budget.certified_quantities or budget.certification_schedule is not None or budget.phase_certified_quantities:
        raise BudgetError('Certificaciones con indirectos pendientes de contraste')
    calculator = Presto88IndirectCalculator(
        budget, chapter_codes=set(config['chapter_codes']), rate=Decimal(config['rate']),
        exclude_undecomposed=config['exclude_undecomposed'])
    calculator.total()
    return calculator


class Presto88IndirectCalculator:
    """Root -> chapters -> partidas -> simple resources, observed default rounding.

Explicitly selected by the persisted configuration. No auxiliary prices, special
percentages, measurements, factors, other price structures or rounding options.
"""

    def __init__(self, budget: Budget, *, chapter_codes: set[str],
                 rate: Decimal, exclude_undecomposed: bool = False):
        if not isinstance(budget, Budget):
            raise TypeError('budget debe ser un Budget')
        if (not isinstance(rate, Decimal) or not rate.is_finite() or rate < 0):
            raise BudgetError('Tipo de indirectos: Decimal no negativo con hasta dos decimales')
        excess = max(0, -rate.as_tuple().exponent - 2)
        if excess and any(rate.as_tuple().digits[-excess:]):
            raise BudgetError('Precisión adicional del tipo pendiente de contraste')
        if not isinstance(exclude_undecomposed, bool):
            raise BudgetError('La exclusión de partidas simples debe ser booleana')
        if not isinstance(chapter_codes, set) or not chapter_codes:
            raise BudgetError('Es necesario declarar explícitamente los capítulos')
        self.budget = budget
        self.rate = rate
        self.exclude_undecomposed = exclude_undecomposed
        self.chapters = frozenset(chapter_codes)
        self.direct = BudgetCalculator(budget)
        self.policy = self.direct.policy
        self._validate()

    def _validate(self):
        budget = self.budget
        root = budget.root_code
        if root is None or root in self.chapters:
            raise BudgetError('Raíz o capítulos no válidos para el perfil de indirectos')
        if budget.percentage_profile is not None:
            raise BudgetError('Combinación de porcentajes e indirectos pendiente de contraste')
        if budget.measurements or budget.bc3_measurements:
            raise BudgetError('Mediciones con indirectos pendientes de contraste')
        if any(r.factor != 1 for r in budget.relations):
            raise BudgetError('Factores con indirectos pendientes de contraste')
        self.children = {}
        for relation in budget.relations:
            self.children.setdefault(relation.parent_code, []).append(relation)
        root_children = self.children.get(root, [])
        if {r.child_code for r in root_children} != self.chapters:
            raise BudgetError('La raíz debe contener exactamente los capítulos declarados')
        self.partidas = frozenset(r.child_code for code in self.chapters
                                 for r in self.children.get(code, []))
        if not self.partidas or self.partidas & (self.chapters | {root}):
            raise BudgetError('Jerarquía de partidas no contrastada')
        resources = {r.child_code for code in self.partidas
                     for r in self.children.get(code, [])}
        if resources & (self.partidas | self.chapters | {root}):
            raise BudgetError('Partidas auxiliares o roles compartidos pendientes de contraste')
        if any(self.children.get(code) for code in resources):
            raise BudgetError('Recursos descompuestos pendientes de contraste')
        if set(budget.concepts) != {root} | self.chapters | self.partidas | resources:
            raise BudgetError('Conceptos desconectados o estructura no contrastada')
        # Validate special-code guards, cycles and direct prices before exposing
        # a partial result. The existing direct calculator owns their semantics.
        for code in budget.concepts:
            self.direct.price(code)

    def quantity(self, relation_id: str) -> Decimal:
        return self.direct.quantity(relation_id)

    def price(self, code: str) -> Decimal:
        if code not in self.budget.concepts:
            raise BudgetError(f'Concepto desconocido: {code}')
        if code == self.budget.root_code or code in self.chapters:
            return self.policy.price(sum((self.relation(r.id).amount
                                          for r in self.children.get(code, [])), Decimal(0)))
        return self.direct.price(code)

    def relation(self, relation_id: str) -> RelationAmount:
        relation = self.budget._relation(relation_id)
        quantity = self.quantity(relation_id)
        direct_price = self.price(relation.child_code)
        valuation_price = direct_price
        if relation.parent_code in self.chapters:
            decomposed = bool(self.children.get(relation.child_code))
            if decomposed or not self.exclude_undecomposed:
                valuation_price = self.policy.price(direct_price * (1 + self.rate / 100))
        return RelationAmount(relation_id, quantity, direct_price,
                              self.policy.amount(quantity * valuation_price))

    def total(self) -> Decimal:
        return self.price(self.budget.root_code)

    def direct_total(self) -> Decimal:
        return self.direct.total()
