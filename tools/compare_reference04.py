"""Read-only comparison against the partial independent Presto 8.8 corpus.

Exit 0: observed fields match; 1: differences; 2: invalid/missing evidence.
This research tool does not certify unobserved behaviour.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openpresto.bc3_importer import import_bc3
from openpresto.calculations import BudgetCalculator

CASES = ('simple', 'reuse', 'dimensions', 'rounding', 'factor_text')


def confined(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f'Path outside evidence root: {relative}')
    return path


def number(value):
    result = Decimal(value)
    if not result.is_finite():
        raise ValueError('Non-finite observed value')
    return result


def compare_case(root, name, *, observed_presto88=False):
    directory = root / 'docs/evidencias-04/ensayos'
    observation = json.loads((directory / f'{name}-observado.json').read_text(encoding='utf-8'))
    if observation.get('schema_version') != 1 or observation.get('source') != 'presto_observation':
        raise ValueError('Invalid observation provenance')
    if observation.get('presto_version') != '8.8' or not observation.get('coverage'):
        raise ValueError('Missing version or coverage')
    fixture = confined(root, observation['fixture'])
    digest = hashlib.sha256(fixture.read_bytes()).hexdigest()
    if digest != observation['fixture_sha256']:
        raise ValueError('Fixture hash mismatch')
    evidence = observation.get('evidence', [])
    if not evidence or any(not confined(directory, item).is_file() for item in evidence):
        raise ValueError('Missing evidence file')
    result = import_bc3(fixture, observed_presto88=observed_presto88)
    calculator = BudgetCalculator(result.budget)
    checks = []

    def check(identity, field, actual, expected):
        expected = number(expected)
        checks.append({'identity': identity, 'field': field,
                       'openpresto': str(actual), 'presto': str(expected),
                       'matches': actual == expected})

    prices = observation.get('observed_prices')
    if not isinstance(prices, dict) or not prices:
        raise ValueError('No observed prices')
    for code, price in prices.items():
        check(code, 'price', calculator.price(code), price)
    for relation in observation.get('observed_relations', []):
        candidates = [r for r in result.budget.relations
                      if r.parent_code == relation['parent'] and r.child_code == relation['child']]
        if len(candidates) != 1:
            raise ValueError('Observed relation is ambiguous or missing')
        target = candidates[0]
        calculated = calculator.relation(target.id)
        identity = [target.parent_code, target.position, target.child_code]
        check(identity, 'quantity', calculated.quantity, relation['quantity'])
        check(identity, 'unit_price', calculated.unit_price, relation['unit_price'])
        check(identity, 'amount', calculated.amount, relation['amount'])
        if observed_presto88 and 'factor' in relation:
            check(identity, 'factor', target.factor, relation['factor'])
    return {'case': name, 'fixture_sha256': digest, 'coverage': observation['coverage'],
            'checks': checks, 'differences': sum(not c['matches'] for c in checks),
            'uncompared_fields': ([] if observed_presto88 and any('factor' in r for r in observation.get('observed_relations', [])) else ['factor'])
                                 + ['measurement_lines', 'long_text', 'rounding_configuration']}


def report(root=ROOT, *, observed_presto88=False):
    cases = []
    errors = []
    for name in CASES:
        try:
            cases.append(compare_case(root, name, observed_presto88=observed_presto88))
        except (OSError, ValueError, KeyError, TypeError, ArithmeticError) as exc:
            errors.append({'case': name, 'error': str(exc)})
    differences = sum(case['differences'] for case in cases)
    return {'schema_version': 1, 'reference': 'Presto 8.8',
            'profile': 'observed-presto88' if observed_presto88 else 'standard',
            'scope': 'partial observed fields; not a certification of compatibility',
            'cases': cases, 'errors': errors, 'differences': differences}, (2 if errors else 1 if differences else 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=('standard', 'observed-presto88'), default='standard')
    args = parser.parse_args()
    result, status = report(observed_presto88=args.profile == 'observed-presto88')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return status


if __name__ == '__main__':
    raise SystemExit(main())
