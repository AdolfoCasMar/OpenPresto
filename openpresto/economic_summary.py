"""Resumen financiero independiente con porcentajes explícitos de proyecto."""
from decimal import Decimal, ROUND_HALF_UP
from .budget import _decimal, BudgetError
from .calculations import calculator_for

KEYS = ('overhead_percent', 'profit_percent', 'tax_percent')


def economic_summary(budget):
    calculator = calculator_for(budget)
    direct = calculator.total()
    rates = {}
    for key in KEYS:
        value = _decimal(budget.project_metadata.get(key,'0'), key)
        if not 0 <= value <= 100:
            raise BudgetError('Los porcentajes del resumen deben estar entre 0 y 100')
        rates[key] = value
    amount = calculator.policy.amount
    overhead = amount(direct * rates['overhead_percent'] / 100)
    profit = amount(direct * rates['profit_percent'] / 100)
    subtotal = amount(direct + overhead + profit)
    tax = amount(subtotal * rates['tax_percent'] / 100)
    return [('Presupuesto',direct),('Gastos generales',overhead),('Beneficio industrial',profit),
            ('Base imponible',subtotal),('Impuestos',tax),('Total',amount(subtotal+tax))]
