"""Explicit partial calculation view for native-observed price locks.

The view copies its configuration and leaves the source graph untouched.
Projects persist explicit locks separately from declared base prices.
"""
from decimal import Decimal
from types import MappingProxyType

from .budget import BudgetError
from .calculations import BudgetCalculator


class LockedPriceCalculator(BudgetCalculator):
    def __init__(self, budget, locked_prices):
        super().__init__(budget)
        if budget.percentage_profile is not None or budget.indirect_config is not None:
            raise BudgetError('Bloqueos con porcentajes o indirectos pendientes de contraste')
        if budget.certified_quantities or budget.certification_schedule is not None or budget.phase_certified_quantities:
            raise BudgetError('Bloqueos con certificaciones pendientes de contraste')
        if not isinstance(locked_prices, dict):
            raise BudgetError('Los precios bloqueados deben ser un mapa')
        for code, price in locked_prices.items():
            if code not in budget.concepts or not any(r.parent_code == code for r in budget.relations):
                raise BudgetError('Solo se bloquean conceptos descompuestos existentes')
            if not isinstance(price, Decimal) or not price.is_finite() or price < 0:
                raise BudgetError('Precio bloqueado: Decimal finito no negativo')
        # Check the ordinary graph, including data hidden behind a lock.
        direct = BudgetCalculator(budget)
        for code in budget.concepts:
            direct.price(code)
        self.locked_prices = MappingProxyType(dict(locked_prices))

    def _price(self, code, visiting):
        if code in self.locked_prices:
            return self.policy.price(self.locked_prices[code])
        return super()._price(code, visiting)

    def without_lock(self, code):
        if code not in self.locked_prices:
            raise BudgetError('El concepto no tiene precio bloqueado')
        return LockedPriceCalculator(self.budget,
            {key: price for key, price in self.locked_prices.items() if key != code})
