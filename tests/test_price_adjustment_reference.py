"""Compare native observations and the bounded independent research replay."""
from dataclasses import replace
from decimal import Decimal, ROUND_HALF_UP, ROUND_CEILING
import hashlib
import json
from pathlib import Path
import unittest

from openpresto.bc3_importer import import_bc3
from openpresto.calculations import calculator_for

ROOT = Path(__file__).resolve().parents[1]


class PriceAdjustmentReferenceTests(unittest.TestCase):
    def test_iterative_replay_predicts_all_seven_native_results(self):
        from tools.replay_iterative_adjustment04 import compare
        result = compare()
        self.assertEqual(result['case_count'], 7)
        self.assertTrue(result['all_match'])
        for case in result['cases']:
            with self.subTest(observation=case['observation'], target=case['target']):
                self.assertEqual(case['mismatches'], [])
        twenty = result['cases'][0]
        self.assertEqual([t['achieved'] for t in twenty['trace']], ['19.99', '20.02'])
        self.assertEqual(twenty['resources'], {'OVR1': '7.15', 'OVR2': '5.72'})
        thirteen = next(c for c in result['cases'] if c['observation'] == 'ajuste-trece-observado.json')
        self.assertEqual([t['achieved'] for t in thirteen['trace']], ['12.99', '13.02'])

    def test_research_replay_preserves_input_and_rejects_unverified_factor(self):
        from tools.replay_iterative_adjustment04 import replay
        from openpresto.calculations import CalculationPolicy
        from openpresto.storage import dumps
        observed = json.loads((ROOT / 'docs/evidencias-04/ensayos/ajuste-precio-observado.json').read_text(encoding='utf-8'))
        budget = import_bc3(ROOT / observed['fixture'], observed_presto88=True).budget
        original = dumps(budget)
        clone, trace = replay(budget, Decimal('20'), CalculationPolicy())
        self.assertEqual(dumps(budget), original)
        self.assertIsNot(clone, budget)
        self.assertEqual(len(trace), 2)
        with self.assertRaises(ValueError):
            replay(budget, Decimal('100'), CalculationPolicy())
        self.assertEqual(dumps(budget), original)

    def test_factor_precision_hypothesis_is_distinguished_by_native_cases(self):
        from tools.compare_adjustment_hypotheses04 import compare
        result = compare()
        self.assertEqual(result['case_count'], 7)
        self.assertEqual(result['matching_factor_decimals'], [])
        candidate = next(c for c in result['candidates'] if c['factor_decimals'] == 'price_decimals_plus_one')
        self.assertIn({'target': '13.00', 'resource': 'OVR1', 'candidate_price': '5.055', 'observed_price': '5.056'}, candidate['mismatches'])
        precision = json.loads((ROOT / 'docs/evidencias-04/ensayos/ajuste-rend4-observado.json').read_text(encoding='utf-8'))
        factor = (Decimal(precision['target']) / Decimal(precision['before']['OVITEM'])).quantize(Decimal('.0001'), rounding=ROUND_HALF_UP)
        using_quantity_precision = [(Decimal(precision['before']['resources'][row['code']]) * factor).quantize(Decimal('.01'), rounding=ROUND_HALF_UP) for row in precision['after']['resources']]
        self.assertNotEqual(using_quantity_precision, [Decimal(row['price']) for row in precision['after']['resources']])
        observed = json.loads((ROOT / 'docs/evidencias-04/ensayos/ajuste-trece-observado.json').read_text(encoding='utf-8'))
        budget = import_bc3(ROOT / observed['fixture'], observed_presto88=True).budget
        for row in observed['after']['resources']:
            budget.concepts[row['code']] = replace(budget.concepts[row['code']], base_price=Decimal(row['price']))
        calc = calculator_for(budget)
        self.assertEqual(calc.total(), Decimal(observed['after']['root']))
        for code, key in (('OVA#', 'OVA'), ('OVB#', 'OVB'), ('OVITEM', 'OVITEM')):
            self.assertEqual(calc.price(code), Decimal(observed['after'][key]))

    def test_exact_and_decreasing_targets_rule_out_universal_upward_rounding(self):
        observed = json.loads((ROOT / 'docs/evidencias-04/ensayos/ajuste-objetivos-observados.json').read_text(encoding='utf-8'))
        fixture = ROOT / observed['fixture']
        self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(), observed['fixture_sha256'])
        for shot in observed['screenshots']:
            self.assertEqual(hashlib.sha256((ROOT / shot['path']).read_bytes()).hexdigest(), shot['sha256'])
        for case in observed['cases']:
            with self.subTest(target=case['target']):
                budget = import_bc3(fixture, observed_presto88=True).budget
                factor = Decimal(case['target']) / Decimal(observed['before']['OVITEM'])
                after = case['after']
                upward = []
                for row in after['resources']:
                    price = Decimal(observed['before']['resources'][row['code']]) * factor
                    self.assertEqual(price.quantize(Decimal('.01'), rounding=ROUND_HALF_UP), Decimal(row['price']))
                    upward.append(price.quantize(Decimal('.01'), rounding=ROUND_CEILING))
                    budget.concepts[row['code']] = replace(budget.concepts[row['code']], base_price=Decimal(row['price']))
                if case['target'] == '10.00':
                    self.assertNotEqual(upward, [Decimal(row['price']) for row in after['resources']])
                calc = calculator_for(budget)
                self.assertEqual(calc.total(), Decimal(after['root']))
                for code, key in (('OVA#', 'OVA'), ('OVB#', 'OVB'), ('OVITEM', 'OVITEM')):
                    self.assertEqual(calc.price(code), Decimal(after[key]))
                for row in after['resources']:
                    relation = next(r for r in budget.relations if r.parent_code == 'OVITEM' and r.child_code == row['code'])
                    result = calc.relation(relation.id)
                    self.assertEqual(result.quantity, Decimal(row['quantity']))
                    self.assertEqual(result.amount, Decimal(row['amount']))

    def test_observed_resource_changes_explain_both_occurrences(self):
        observed = json.loads((ROOT / 'docs/evidencias-04/ensayos/ajuste-precio-observado.json').read_text(encoding='utf-8'))
        fixture = ROOT / observed['fixture']
        self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(), observed['fixture_sha256'])
        for shot in observed['screenshots']:
            self.assertEqual(hashlib.sha256((ROOT / shot['path']).read_bytes()).hexdigest(), shot['sha256'])
        budget = import_bc3(fixture, observed_presto88=True).budget
        self.assertEqual(calculator_for(budget).total(), Decimal(observed['before']['root']))
        after = observed['after']
        factor = Decimal(observed['target']) / Decimal(observed['before']['OVITEM'])
        ordinary_rounding = []
        for resource in after['resources']:
            code = resource['code']
            ordinary_rounding.append((Decimal(observed['before']['resources'][code]) * factor).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
            budget.concepts[code] = replace(budget.concepts[code], base_price=Decimal(resource['price']))
        self.assertNotEqual(ordinary_rounding, [Decimal(r['price']) for r in after['resources']])
        calc = calculator_for(budget)
        self.assertEqual(calc.total(), Decimal(after['root']))
        self.assertNotEqual(calc.price('OVITEM'), Decimal(observed['target']))
        self.assertEqual(calc.price('OVITEM'), Decimal(after['OVITEM']))
        for row in after['resources'] + after['occurrences']:
            parent = row['parent'] + '#' if 'parent' in row else 'OVITEM'
            child = 'OVITEM' if 'parent' in row else row['code']
            relation = next(r for r in budget.relations if r.parent_code == parent and r.child_code == child)
            values = calc.relation(relation.id)
            self.assertEqual(values.quantity, Decimal(row['quantity']))
            self.assertEqual(values.amount, Decimal(row['amount']))


if __name__ == '__main__':
    unittest.main()
