from decimal import Decimal
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from openpresto.bc3_importer import import_bc3
from openpresto.bc3_exporter import save_bc3
from openpresto.budget import BudgetError
from openpresto.price_operations import multiply_basic_prices
from openpresto.storage import dumps, loads

ROOT = Path(__file__).resolve().parents[1]


class PriceOperationsTests(unittest.TestCase):
    def test_exact_multiplication_matches_selected_native_resource_rows(self):
        from openpresto.calculations import BudgetCalculator, CalculationPolicy
        observed = json.loads((ROOT / 'docs/evidencias-04/ensayos/operar-multiplicar-observado.json').read_text(encoding='utf-8'))
        fixture = ROOT / observed['fixture']
        self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(), observed['fixture_sha256'])
        for shot in observed['screenshots']:
            self.assertEqual(hashlib.sha256((ROOT / shot['path']).read_bytes()).hexdigest(), shot['sha256'])
        budget = import_bc3(fixture, observed_presto88=True).budget
        for code, price in observed['before']['resources'].items():
            budget.concepts[code] = replace(budget.concepts[code], base_price=Decimal(price))
        before = dumps(budget)
        policy = CalculationPolicy(quantity_decimals=4, price_decimals=3, amount_decimals=2)
        self.assertEqual(BudgetCalculator(budget, policy).total(), Decimal(observed['before']['root']))
        factor = Decimal(observed['factor'])
        changed = multiply_basic_prices(budget, {'1': factor, '3': factor})
        self.assertEqual(dumps(budget), before)
        calc = BudgetCalculator(changed, policy)
        self.assertEqual(calc.total(), Decimal(observed['after']['root']))
        for code, key in (('OVA#', 'OVA'), ('OVB#', 'OVB'), ('OVITEM', 'OVITEM')):
            self.assertEqual(calc.price(code), Decimal(observed['after'][key]))
        for row in observed['after']['resources']:
            self.assertEqual(changed.concepts[row['code']].base_price, Decimal(row['price']))
            relation = next(r for r in changed.relations if r.parent_code == 'OVITEM' and r.child_code == row['code'])
            values = calc.relation(relation.id)
            self.assertEqual(values.quantity, Decimal(row['quantity']))
            self.assertEqual(values.amount, Decimal(row['amount']))

    def project(self):
        return import_bc3(ROOT / 'tests/reference04/price_override/baseline.bc3', observed_presto88=True).budget

    def test_explicit_selection_deduplicates_and_leaves_other_resources(self):
        budget = self.project()
        before = dumps(budget)
        changed = multiply_basic_prices(budget, {'1': Decimal('2')}, codes=['OVR1','OVR1'])
        self.assertEqual(changed.concepts['OVR1'].base_price, Decimal('6'))
        self.assertEqual(changed.concepts['OVR2'], budget.concepts['OVR2'])
        self.assertEqual(changed.total(), Decimal('112'))
        for codes in ([], ['OVITEM'], ['unknown'], ['OVR2']):
            with self.subTest(codes=codes), self.assertRaises(BudgetError):
                multiply_basic_prices(budget, {'1': Decimal('2')}, codes=codes)
        self.assertEqual(dumps(budget), before)

    def test_distinct_factors_preserve_shared_identity_and_roundtrip(self):
        original = self.project()
        before = dumps(original)
        changed = multiply_basic_prices(original, {'1': Decimal('1.1'), '3': Decimal('.5')})
        self.assertEqual(dumps(original), before)
        self.assertEqual(changed.concepts['OVR1'].base_price, Decimal('3.3'))
        self.assertEqual(changed.concepts['OVR2'].base_price, Decimal('2'))
        self.assertEqual(changed.concepts['OVITEM'], original.concepts['OVITEM'])
        self.assertEqual(changed.relations, original.relations)
        self.assertEqual(changed.total(), Decimal('60.20'))
        self.assertEqual(loads(dumps(changed)).total(), Decimal('60.20'))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'operated.bc3'
            save_bc3(changed, path)
            self.assertEqual(import_bc3(path, observed_presto88=True).budget.total(), Decimal('60.20'))

    def test_invalid_or_uncontrasted_operation_does_not_modify_project(self):
        budget = self.project()
        before = dumps(budget)
        for factors in ({}, {'1': 1.1}, {'1': Decimal('NaN')}, {'1': Decimal('0')},
                        {'1': Decimal('-1')}, {'0': Decimal('2')}):
            with self.subTest(factors=factors), self.assertRaises(BudgetError):
                multiply_basic_prices(budget, factors)
            self.assertEqual(dumps(budget), before)
        budget.locked_prices = {'OVITEM': Decimal('20')}
        locked = dumps(budget)
        with self.assertRaises(BudgetError):
            multiply_basic_prices(budget, {'1': Decimal('2')})
        self.assertEqual(dumps(budget), locked)

    def test_extra_figures_survive_json_and_are_reported_when_exported(self):
        from openpresto.bc3_exporter import render_bc3
        original = self.project()
        changed = multiply_basic_prices(original, {'1': Decimal('.333333333')})
        self.assertEqual(changed.concepts['OVR1'].base_price, Decimal('.999999999'))
        self.assertEqual(loads(dumps(changed)).concepts['OVR1'].base_price, Decimal('.999999999'))
        before = dumps(changed)
        exported = render_bc3(changed)
        self.assertTrue(any('OVR1' in w and 'redondeados' in w and 'JSON' in w for w in exported.warnings))
        self.assertEqual(dumps(changed), before)
        self.assertEqual(original.concepts['OVR1'].base_price, Decimal('3'))
        changed.locked_prices = {'OVITEM': Decimal('20')}
        self.assertTrue(any('OVR1' in w and 'redondeados' in w for w in render_bc3(changed).warnings))


if __name__ == '__main__':
    unittest.main()
