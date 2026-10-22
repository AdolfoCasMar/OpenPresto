"""Document-based multiplication of basic prices by nature.

Manual reference: supplied complete manual, PDF page 38, Precios: Operar.
This is a core operation, not a claim about Presto 8.8 UI or rounding.
"""
from dataclasses import replace
from decimal import Decimal, localcontext

from .budget import BudgetError, require_plain_price_code
from .calculations import calculator_for
from .storage import dumps, loads


def multiply_basic_prices(budget, factors, *, codes=None):
    """Return a separate project; multiply each matching basic concept once.

    Factors are explicit positive Decimals keyed by BC3 nature 1/2/3.
    Exact products are retained; existing calculation policy values the result.
    Mixed profiles and rounding of modified prices need separate contracts.
    """
    if not isinstance(factors, dict) or not factors:
        raise BudgetError('Indica factores por naturaleza')
    factors = dict(factors)
    selected = None
    if codes is not None:
        if not isinstance(codes, (tuple, list, set, frozenset)) or not codes:
            raise BudgetError('Selecciona conceptos básicos')
        if any(not isinstance(code, str) for code in codes):
            raise BudgetError('Los códigos seleccionados deben ser cadenas')
        selected = set(codes)
        composed = {r.parent_code for r in budget.relations}
        if any(code not in budget.concepts or code in composed for code in selected):
            raise BudgetError('La selección contiene conceptos desconocidos o calculados')
        if any(budget.concepts[code].nature not in factors for code in selected):
            raise BudgetError('Falta factor para una naturaleza seleccionada')
    for nature, factor in factors.items():
        if nature not in ('1', '2', '3'):
            raise BudgetError('Solo naturalezas básicas BC3 1, 2 y 3')
        if not isinstance(factor, Decimal) or not factor.is_finite() or factor <= 0:
            raise BudgetError('El factor debe ser Decimal finito positivo')
    if (budget.locked_prices or budget.percentage_profile is not None
            or budget.indirect_config is not None or budget.certified_quantities
            or budget.certification_schedule is not None or budget.phase_certified_quantities):
        raise BudgetError('Operar con bloqueos u otros perfiles pendiente de contraste')
    for code in budget.concepts:
        require_plain_price_code(code)
    calculator_for(budget).total()
    composed = {r.parent_code for r in budget.relations}
    clone = loads(dumps(budget))
    for code, concept in budget.concepts.items():
        if selected is not None and code not in selected:
            continue
        if code in composed or concept.nature not in factors:
            continue
        factor = factors[concept.nature]
        # Avoid silent Decimal context rounding before the project's policy.
        with localcontext() as context:
            context.prec = max(28, len(concept.base_price.as_tuple().digits) + len(factor.as_tuple().digits))
            value = concept.base_price * factor
        clone.concepts[code] = replace(concept, base_price=value)
    calculator_for(clone).total()
    return clone


def scale_resource_prices(budget, factor, codes):
    """Native arithmetic operation preserving each project's calculation profile.

    Changes only selected leaf prices, once per shared code. Decomposition locks
    remain explicit; certification quantities and measurements remain unchanged.
    The complete result is valued using the active economic policy before return.
    """
    if not isinstance(factor,Decimal) or not factor.is_finite() or factor <= 0:
        raise BudgetError('El factor debe ser Decimal finito positivo')
    selected = set(codes)
    if not selected:
        raise BudgetError('Selecciona precios básicos')
    composed = {r.parent_code for r in budget.relations}
    for code in selected:
        if code not in budget.concepts or code in composed or code == budget.root_code:
            raise BudgetError('Solo se multiplican precios básicos existentes')
        require_plain_price_code(code)
    clone = loads(dumps(budget))
    for code in selected:
        concept = clone.concepts[code]
        with localcontext() as context:
            context.prec = max(28,len(concept.base_price.as_tuple().digits)+len(factor.as_tuple().digits))
            price = concept.base_price * factor
        clone.concepts[code] = replace(concept,base_price=price)
    calculator = calculator_for(clone)
    for code in clone.concepts:
        calculator.price(code)
    calculator.total()
    return clone
