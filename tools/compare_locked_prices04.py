"""Read-only numeric comparison with captured Presto 8.8 price-lock evidence.

Exit 0: observed numeric fields match; 1: differences; 2: invalid evidence.
Does not execute Presto or certify native persistence, undo, colour or BC3.
"""
from dataclasses import replace
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openpresto.bc3_importer import import_bc3
from openpresto.calculations import calculator_for
from tools.compare_reference04 import confined, number


def report(root=ROOT):
    checks = []
    result = {'schema_version': 1, 'reference': 'Presto 8.8', 'checks': checks, 'errors': [],
              'scope': 'captured numeric observations only',
              'uncompared_fields': ['native_persistence', 'native_undo', 'BC3',
                                    'colour', 'adjust', 'remove_decomposition']}
    try:
        folder = root / 'tests/reference04/price_override'
        manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        fixture = confined(folder, manifest['fixture'])
        digest = hashlib.sha256(fixture.read_bytes()).hexdigest()
        if digest != manifest['sha256']:
            raise ValueError('Fixture hash mismatch')
        observations = []
        for path in manifest['native_results']:
            observation = json.loads(confined(root, path).read_text(encoding='utf-8'))
            if observation.get('version') != 'Presto 8.8':
                raise ValueError('Unexpected native version')
            if observation.get('source') not in ('native_ui', 'native_ui_observation'):
                raise ValueError('Unexpected observation source')
            shots = observation['screenshots']
            if not shots:
                raise ValueError('Missing screenshots')
            for shot in shots:
                data = confined(root, shot['path']).read_bytes()
                if hashlib.sha256(data).hexdigest() != shot['sha256']:
                    raise ValueError('Screenshot hash mismatch')
            observations.append(observation)
        baseline, lock, unlock = observations
        if baseline['sha256'] != digest:
            raise ValueError('Observed fixture hash mismatch')
        budget = import_bc3(fixture, observed_presto88=True).budget

        def check(stage, identity, field, actual, expected):
            expected = number(expected)
            checks.append({'stage': stage, 'identity': identity, 'field': field,
                           'openpresto': str(actual), 'presto': str(expected),
                           'matches': actual == expected})

        def prices(stage, data, fields):
            calc = calculator_for(budget)
            for code, key in fields.items():
                check(stage, code, 'price', calc.price(code), data[key])

        def relation(stage, parent, child, data, fields):
            candidates = [r for r in budget.relations
                          if r.parent_code == parent and r.child_code == child]
            if len(candidates) != 1:
                raise ValueError('Ambiguous observed relation')
            value = calculator_for(budget).relation(candidates[0].id)
            for field, key in fields.items():
                check(stage, [parent, child], field, getattr(value, field), data[key])

        prices('baseline', baseline['baseline'],
               {'OVROOT##': 'root', 'OVA#': 'OVA', 'OVB#': 'OVB', 'OVITEM': 'OVITEM'})
        budget.locked_prices = {'OVITEM': Decimal(baseline['attempted_price'])}
        prices('locked', lock['observed'],
               {'OVROOT##': 'root', 'OVA#': 'OVA', 'OVB#': 'OVB', 'OVITEM': 'OVITEM_A'})
        for parent, key in [('OVA#', 'OVITEM_A'), ('OVB#', 'OVITEM_B')]:
            relation('locked', parent, 'OVITEM', lock['observed'], {'unit_price': key})
        for resource in lock['observed']['resources_before_edit']:
            relation('locked', 'OVITEM', resource['code'], resource,
                     {'quantity': 'quantity', 'unit_price': 'price', 'amount': 'amount'})
        edit = lock['resource_edit']
        budget.concepts[edit['code']] = replace(budget.concepts[edit['code']], base_price=edit['price'])
        relation('resource_edit', 'OVITEM', edit['code'], edit, {'unit_price': 'price', 'amount': 'amount'})
        relation('resource_edit', 'OVA#', 'OVITEM', edit,
                 {'quantity': 'OVITEM_quantity', 'unit_price': 'OVITEM_price', 'amount': 'OVITEM_amount'})
        prices('before_unlock', unlock['before_unlock'],
               {'OVROOT##': 'root_after_resource_edit', 'OVITEM': 'OVITEM'})
        budget.locked_prices.clear()
        prices('unlocked', unlock['after_unlock'],
               {'OVROOT##': 'OVROOT', 'OVA#': 'OVA', 'OVB#': 'OVB', 'OVITEM': 'OVITEM_price'})
        relation('unlocked', 'OVA#', 'OVITEM', unlock['after_unlock'],
                 {'quantity': 'OVA_quantity', 'amount': 'OVA_amount'})
    except (OSError, ValueError, KeyError, TypeError, ArithmeticError) as exc:
        result['errors'].append(str(exc))
    result['differences'] = sum(not check['matches'] for check in checks)
    return result, 2 if result['errors'] else 1 if result['differences'] else 0


if __name__ == '__main__':
    result, status = report()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(status)
