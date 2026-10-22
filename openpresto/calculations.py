"""Cálculos económicos configurables para OpenPresto.

Esta política de redondeo es inicial y explícita: no presupone aún que
reproduzca todos los parámetros y fases de cálculo de Presto 8.8.
El modelo fuente (`Budget`) nunca se modifica.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_EVEN, ROUND_DOWN

from .budget import Budget, BudgetError, require_plain_price_code


@dataclass(frozen=True)
class CalculationPolicy:
    """Decimales de cantidad, precio unitario e importe; redondeo comercial."""
    quantity_decimals: int = 3
    price_decimals: int = 2
    amount_decimals: int = 2
    root_quantity_decimals: int | None = None

    def __post_init__(self) -> None:
        for name in ("quantity_decimals", "price_decimals", "amount_decimals"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 12:
                raise BudgetError(f"{name} debe ser un entero entre 0 y 12")
        value = self.root_quantity_decimals
        if value is not None and (isinstance(value, bool) or not isinstance(value, int)
                                  or not 0 <= value <= 12):
            raise BudgetError("root_quantity_decimals debe ser None o un entero entre 0 y 12")

    @staticmethod
    def _round(value: Decimal, places: int) -> Decimal:
        step = Decimal("1").scaleb(-places)
        return value.quantize(step, rounding=ROUND_HALF_UP)

    def quantity(self, value: Decimal) -> Decimal:
        return self._round(value, self.quantity_decimals)

    def price(self, value: Decimal) -> Decimal:
        return self._round(value, self.price_decimals)

    def amount(self, value: Decimal) -> Decimal:
        return self._round(value, self.amount_decimals)


@dataclass(frozen=True)
class NativeCalculationPolicy(CalculationPolicy):
    rounding: str = ROUND_HALF_UP

    def __post_init__(self):
        super().__post_init__()
        if self.rounding not in (ROUND_HALF_UP, ROUND_HALF_EVEN, ROUND_DOWN):
            raise BudgetError('Modo de redondeo no admitido')

    def _round(self, value, places):
        return value.quantize(Decimal(1).scaleb(-places), rounding=self.rounding)


@dataclass(frozen=True)
class RelationAmount:
    relation_id: str
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal


class BudgetCalculator:
    """Vista económica calculada de un Budget, sin mutarlo.

    Para una descomposición se redondea cada cantidad y precio hijo,
    se redondea cada importe de componente, se suman esos importes
    y se redondea el precio resultante. El importe de relación usa
    cantidad redondeada × precio redondeado y su propio redondeo.
    """

    def __init__(self, budget: Budget, policy: CalculationPolicy | None = None) -> None:
        if not isinstance(budget, Budget):
            raise TypeError("budget debe ser un Budget")
        self.budget = budget
        metadata = getattr(budget, 'project_metadata', {})
        configured = {name: int(metadata[name]) for name in
                      ('quantity_decimals', 'price_decimals', 'amount_decimals') if name in metadata}
        if (configured or 'economic_rounding' in metadata) and (budget.percentage_profile or budget.indirect_config or budget.locked_prices):
            raise BudgetError('Precisión personalizada incompatible con el perfil económico seleccionado')
        if policy is not None:
            self.policy = policy
        elif configured or 'economic_rounding' in metadata:
            self.policy = NativeCalculationPolicy(root_quantity_decimals=budget.root_quantity_decimals,
                rounding=metadata.get('economic_rounding', ROUND_HALF_UP), **configured)
        else:
            self.policy = CalculationPolicy(root_quantity_decimals=budget.root_quantity_decimals)
        if not isinstance(self.policy, CalculationPolicy):
            raise TypeError("policy debe ser CalculationPolicy")

    def quantity(self, relation_id: str) -> Decimal:
        relation = self.budget._relation(relation_id)
        value = self._raw_quantity(relation_id)
        places = self.policy.root_quantity_decimals
        if places is not None and relation.parent_code == self.budget.root_code:
            return self.policy._round(value, places)
        return self.policy.quantity(value)

    def _raw_quantity(self, relation_id: str) -> Decimal:
        return self.budget.relation_quantity(relation_id)

    def price(self, concept_code: str) -> Decimal:
        if concept_code not in self.budget.concepts:
            raise BudgetError(f"Concepto desconocido: {concept_code}")
        return self._price(concept_code, set())

    def _price(self, code: str, visiting: set[str]) -> Decimal:
        require_plain_price_code(code)
        if code in visiting:
            raise BudgetError("Ciclo detectado durante el cálculo")
        children = [r for r in self.budget.relations if r.parent_code == code]
        if not children:
            return self.policy.price(self.budget.concepts[code].base_price)
        visiting.add(code)
        try:
            parts = [
                self.policy.amount(r.factor * self.quantity(r.id) * self._price(r.child_code, visiting))
                for r in children
            ]
            return self.policy.price(sum(parts, Decimal("0")))
        finally:
            visiting.remove(code)

    def relation(self, relation_id: str) -> RelationAmount:
        relation = self.budget._relation(relation_id)
        quantity = self.quantity(relation_id)
        price = self.price(relation.child_code)
        return RelationAmount(
            relation_id=relation_id,
            quantity=quantity,
            unit_price=price,
            amount=self.policy.amount(relation.factor * quantity * price),
        )

    def total(self) -> Decimal:
        if self.budget.root_code is None:
            raise BudgetError("Es necesario establecer el concepto raíz")
        return self.price(self.budget.root_code)


def calculator_for(budget: Budget, policy: CalculationPolicy | None = None) -> BudgetCalculator:
    """Choose the explicitly persisted project profile; legacy projects stay unchanged."""
    if budget.project_metadata.get('engine') == 'native-v1':
        from .native_calculations import NativeBudgetCalculator
        return NativeBudgetCalculator(budget,policy)
    if budget.locked_prices:
        if policy is not None:
            raise BudgetError('Política personalizada con bloqueo pendiente de contraste')
        from .locked_prices import LockedPriceCalculator
        return LockedPriceCalculator(budget, budget.locked_prices)
    if budget.indirect_config is not None:
        if policy is not None:
            raise BudgetError('Política personalizada con indirectos pendiente de contraste')
        from .indirect_costs import calculator_from_config
        return calculator_from_config(budget)
    if budget.percentage_profile is None:
        return BudgetCalculator(budget, policy)
    if budget.percentage_profile == 'presto88_bc3':
        from .percentage_calculations import Presto88PercentageCalculator
        return Presto88PercentageCalculator(budget, policy)
    raise BudgetError('Perfil de porcentajes desconocido')


def calculation_batch(calculator):
    """Read-only evaluation scope; never cache across user edits."""
    from contextlib import nullcontext
    return calculator.batch() if hasattr(calculator, 'batch') else nullcontext(calculator)
