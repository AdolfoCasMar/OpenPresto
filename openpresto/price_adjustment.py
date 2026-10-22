"""Independent price-only adjustment, bounded by the verified 8.8 contract.

See docs/CALCULATIONS.md for the supported calculation scope.
The source project is never modified, including on an unsupported branch.
"""
from dataclasses import dataclass, replace
from decimal import Decimal, localcontext

from .budget import Budget, BudgetError, require_plain_price_code
from .calculations import BudgetCalculator, CalculationPolicy, calculator_for
from .storage import dumps, loads


@dataclass(frozen=True)
class AdjustmentStep:
    factor: Decimal
    price: Decimal


@dataclass(frozen=True)
class PriceAdjustment:
    budget: Budget
    concept_code: str
    target: Decimal
    initial_price: Decimal
    achieved_price: Decimal
    factor: Decimal
    steps: tuple[AdjustmentStep, ...]
    changed_codes: tuple[str, ...]


def adjust_price(budget, concept_code, target, *, policy=None):
    """Preview adjustment of all basic prices in one direct decomposition.

    Global concept identity is retained: other uses of a changed resource are
    affected too. Only the verified price-only mode is supported. Nested
    decomposition, mixed profiles, measurements, unequal factors, and native
    rollback/outer-pass branches fail explicitly, without modifying input.
    A caller supplying a custom policy must also use it to value the result.
    The desktop editor uses the active project policy within the supported adjustment range.
    """
    if not isinstance(target, Decimal) or not target.is_finite() or target <= 0:
        raise BudgetError('El precio solicitado debe ser un decimal finito positivo.')
    if (concept_code not in budget.concepts or concept_code == budget.root_code
            or concept_code.endswith('#')):
        raise BudgetError('Selecciona una partida descompuesta para ajustar sus recursos.')
    if (budget.locked_prices or budget.percentage_profile is not None
            or budget.indirect_config is not None or budget.certified_quantities
            or budget.certification_schedule is not None or budget.phase_certified_quantities
            or budget.root_quantity_decimals not in (None, 0)):
        raise BudgetError('Ajustar con bloqueos, certificaciones u otros perfiles está pendiente de contraste.')
    for code in budget.concepts:
        require_plain_price_code(code)
    policy = policy if policy is not None else calculator_for(budget).policy
    if not isinstance(policy, CalculationPolicy):
        raise BudgetError('La política de cálculo no es válida.')
    if (policy.price_decimals not in (2, 3) or policy.amount_decimals != 2
            or policy.quantity_decimals not in (3, 4) or policy.root_quantity_decimals not in (None, 0)):
        raise BudgetError('Esta combinación de precisiones aún no está contrastada para Ajustar.')
    children = [r for r in budget.relations if r.parent_code == concept_code]
    if not children:
        raise BudgetError('La partida debe tener una descomposición de recursos básicos.')
    composed = {r.parent_code for r in budget.relations}
    measured = {m.relation_id for m in budget.measurements}
    measured.update(rid for rid, record in budget.bc3_measurements.items() if record.lines)
    codes = tuple(dict.fromkeys(r.child_code for r in children))
    if any(code in composed or budget.concepts[code].nature not in ('1', '2', '3') for code in codes):
        raise BudgetError('Solo se admite una descomposición directa de recursos básicos; los niveles anidados están pendientes.')
    if any(r.factor != 1 or r.quantity <= 0 or r.id in measured for r in children):
        raise BudgetError('Los rendimientos deben ser positivos, sin mediciones ni factores separados para este ajuste.')
    if any(budget.concepts[code].base_price <= 0
           or policy.price(budget.concepts[code].base_price) != budget.concepts[code].base_price for code in codes):
        raise BudgetError('Los recursos deben tener precios positivos con la precisión seleccionada.')
    calc = BudgetCalculator(budget, policy)
    calc.total()  # Validate the whole graph before preparing any result.
    baseline = calc.price(concept_code)
    if baseline <= 0:
        raise BudgetError('El precio de partida debe ser positivo.')
    if target == baseline:
        raise BudgetError('El precio solicitado ya coincide con el precio actual.')
    snapshot = dumps(budget)
    previous = Decimal(0)
    previous_error = target
    steps = []
    with localcontext() as context:
        context.prec = 50
        factor = target / baseline
        for _ in range(5):
            if not Decimal('.5') <= factor <= Decimal(2) or factor == 1:
                raise BudgetError('El ajuste requiere una pasada fuera del intervalo contrastado; no se ha aplicado ningún cambio.')
            proposed = loads(snapshot)
            for code in codes:
                original = budget.concepts[code]
                proposed.concepts[code] = replace(
                    original, base_price=policy.price(original.base_price * factor))
            result_calc = BudgetCalculator(proposed, policy)
            achieved = result_calc.price(concept_code)
            steps.append(AdjustmentStep(factor, achieved))
            if (achieved == baseline
                    or policy._round(achieved, 0) == policy._round(previous, 0)
                    or policy._round(achieved, 2) == policy._round(target, 2)):
                result_calc.total()
                changed = tuple(code for code in codes
                                if proposed.concepts[code].base_price != budget.concepts[code].base_price)
                if not changed:
                    raise BudgetError('La precisión actual no permite modificar los precios con este ajuste.')
                return PriceAdjustment(proposed, concept_code, target, baseline,
                                       achieved, factor, tuple(steps), changed)
            error = abs(target - achieved)
            if error >= previous_error:
                raise BudgetError('El ajuste necesita un retroceso todavía pendiente de contraste; la obra se conserva.')
            previous_error = error
            previous = achieved
            factor -= ((1 - factor) * (achieved - target)) / (baseline - achieved)
    raise BudgetError('El ajuste requiere más pasadas pendientes de contraste; la obra se conserva.')
