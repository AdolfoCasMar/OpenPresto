"""Replay the bounded own-data price-only adjustment reference.

Comparison harness for the bounded core adjustment operation.
No recovered proprietary implementation is included. Decimal rounding is the
existing OpenPresto policy, not an emulation of the native x87 environment.
"""
from dataclasses import replace
from decimal import Decimal
import hashlib
import json

from openpresto.bc3_importer import import_bc3
from openpresto.calculations import BudgetCalculator, CalculationPolicy
from openpresto.storage import dumps
from openpresto.price_adjustment import adjust_price
from tools.compare_adjustment_hypotheses04 import ROOT, OBSERVATIONS


def replay(budget, target, policy):
    """Return a separate fixture project and its trace, or reject unknown cases.

    Restricted to OVITEM with two basic resources; other native modes, outer
    passes, shared-resource exclusions and prompts remain outside this model.
    """
    codes = ('OVR1', 'OVR2')
    children = [r for r in budget.relations if r.parent_code == 'OVITEM']
    if (len(children) != 2 or {r.child_code for r in children} != set(codes)
            or any(r.parent_code in codes for r in budget.relations)
            or budget.locked_prices or budget.percentage_profile is not None
            or budget.indirect_config is not None):
        raise ValueError('Solo el perfil de ensayo propio está contrastado')
    if not isinstance(target, Decimal) or not target.is_finite() or target <= 0:
        raise ValueError('Objetivo positivo finito requerido')
    result = adjust_price(budget, 'OVITEM', target, policy=policy)
    trace = [{'attempt': i, 'factor': str(step.factor), 'achieved': str(step.price)}
             for i, step in enumerate(result.steps, 1)]
    return result.budget, trace


def compare():
    results = []
    for filename in OBSERVATIONS:
        observed = json.loads((ROOT / 'docs/evidencias-04/ensayos' / filename).read_text(encoding='utf-8'))
        paths = [(observed['fixture'], observed['fixture_sha256'])]
        paths += [(shot['path'], shot['sha256']) for shot in observed['screenshots']]
        for path, digest in paths:
            if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != digest:
                raise ValueError(f'Evidencia alterada: {path}')
        policy = CalculationPolicy(
            quantity_decimals=observed.get('precision_change', {}).get('DecCantRend', 3),
            price_decimals=observed.get('price_decimals', 2), amount_decimals=2)
        for case in observed.get('cases', [observed]):
            budget = import_bc3(ROOT / observed['fixture'], observed_presto88=True).budget
            for code, price in observed['before']['resources'].items():
                budget.concepts[code] = replace(budget.concepts[code], base_price=Decimal(price))
            original = dumps(budget)
            clone, trace = replay(budget, Decimal(case['target']), policy)
            if dumps(budget) != original:
                raise AssertionError('El ensayo modificó la obra de entrada')
            calc = BudgetCalculator(clone, policy)
            actual = {'root': calc.total(), 'OVA': calc.price('OVA#'),
                      'OVB': calc.price('OVB#'), 'OVITEM': calc.price('OVITEM')}
            mismatches = []
            for field, value in actual.items():
                if value != Decimal(case['after'][field]):
                    mismatches.append(field)
            for row in case['after']['resources']:
                relation = next(r for r in clone.relations
                                if r.parent_code == 'OVITEM' and r.child_code == row['code'])
                values = calc.relation(relation.id)
                for field, value in (('price', values.unit_price),
                                     ('quantity', values.quantity), ('amount', values.amount)):
                    if value != Decimal(row[field]):
                        mismatches.append(row['code'] + '.' + field)
            results.append({'observation': filename, 'target': case['target'],
                            'price_decimals': policy.price_decimals, 'trace': trace,
                            'actual': {k: str(v) for k, v in actual.items()},
                            'resources': {code: str(clone.concepts[code].base_price)
                                          for code in ('OVR1', 'OVR2')},
                            'mismatches': mismatches})
    return {'case_count': len(results), 'cases': results,
            'all_match': all(not case['mismatches'] for case in results),
            'scope': 'Own fixture, price-only, two basic resources, seven observations; not universal parity'}


if __name__ == '__main__':
    print(json.dumps(compare(), ensure_ascii=False, indent=2))
