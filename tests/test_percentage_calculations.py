"""Compare the explicit percentage view with independent 8.8 observations."""
from decimal import Decimal
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import unittest

from openpresto.bc3_importer import import_bc3
from openpresto.budget import BudgetConcept, BudgetError, BudgetRelation
from openpresto.calculations import BudgetCalculator
from openpresto.percentage_calculations import Presto88PercentageCalculator
from openpresto.storage import dumps


ROOT = Path(__file__).resolve().parents[1]
OBSERVATION = ROOT / 'docs/evidencias-04/ensayos/porcentajes-observados.json'


class PercentageCalculationTests(unittest.TestCase):
    @staticmethod
    def replace_relation(budget, relation, **changes):
        updated = replace(relation, **changes)
        budget.relations[budget.relations.index(relation)] = updated
        budget._relations_by_id[updated.id] = updated

    def setUp(self):
        self.observation = json.loads(OBSERVATION.read_text(encoding='utf-8'))

    def load_export(self):
        path = ROOT / self.observation['bc3_roundtrip']['export']
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                         self.observation['bc3_roundtrip']['export_sha256'])
        return import_bc3(path, observed_presto88=True).budget

    def assert_case(self, budget, expected):
        before = dumps(budget)
        calculator = Presto88PercentageCalculator(budget)
        percentage = next(r for r in budget.relations if '%' in r.child_code)
        row = calculator.relation(percentage.id)
        self.assertEqual(row.quantity, Decimal(expected['displayed_percentage_quantity']))
        self.assertEqual(row.unit_price, Decimal(expected['displayed_percentage_price']))
        self.assertEqual(row.amount, Decimal(expected['percentage_amount']))
        self.assertEqual(calculator.quantity(percentage.id), row.quantity)
        self.assertEqual(calculator.total(), Decimal(expected['item_price']))
        self.assertEqual(dumps(budget), before)
        with self.assertRaises(BudgetError):
            BudgetCalculator(budget).total()

    def test_original_import_yield_is_a_rate_not_the_displayed_base(self):
        path = ROOT / self.observation['input_fixture']
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                         self.observation['input_fixture_sha256'])
        self.assert_case(import_bc3(path, observed_presto88=True).budget,
                         self.observation['cases'][0])

    def test_native_export_and_reimport(self):
        self.assert_case(self.load_export(), self.observation['bc3_roundtrip'])

    def test_native_rate_10_with_original_resource_quantity(self):
        budget = self.load_export()
        self.replace_relation(budget, next(r for r in budget.relations if r.child_code == 'M01'),
                              quantity=Decimal('2'))
        self.assert_case(budget, self.observation['cases'][1])

    def test_unsupported_variants_fail_instead_of_guessing(self):
        for variant in ('multiple_signs', 'factor', 'ambiguous_order', 'decomposed',
                        'mixed_prefix', 'case_ambiguity'):
            with self.subTest(variant=variant):
                budget = self.load_export()
                percentage = next(r for r in budget.relations if '%' in r.child_code)
                if variant == 'multiple_signs':
                    budget.add_concept(BudgetConcept('M%%OTHER', base_price=10))
                    self.replace_relation(budget, percentage, child_code='M%%OTHER')
                elif variant == 'factor':
                    self.replace_relation(budget, percentage, factor=Decimal('2'))
                elif variant == 'ambiguous_order':
                    self.replace_relation(budget, percentage, position=1)
                elif variant == 'mixed_prefix':
                    budget.add_concept(BudgetConcept('P%OTHER', base_price=10))
                    budget.add_relation(BudgetRelation('ITEM', 'P%OTHER', quantity='.1', position=5))
                elif variant == 'case_ambiguity':
                    budget.add_concept(BudgetConcept('m%OTHER', base_price=10))
                    self.replace_relation(budget, percentage, child_code='m%OTHER')
                else:
                    budget.add_relation(BudgetRelation(percentage.child_code, 'M01', quantity=1, position=1))
                with self.assertRaises(BudgetError):
                    Presto88PercentageCalculator(budget).total()

    def test_order_empty_prefix_and_sequential_percentages_match_observed_lines(self):
        path = OBSERVATION.parent / 'porcentajes-orden-observados.json'
        observation = json.loads(path.read_text(encoding='utf-8'))
        fixture = ROOT / observation['fixture']
        self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(), observation['fixture_sha256'])
        for filename, digest in observation['evidence_sha256'].items():
            self.assertEqual(hashlib.sha256((path.parent / filename).read_bytes()).hexdigest(), digest)
        budget = import_bc3(fixture, observed_presto88=True).budget
        before = dumps(budget)
        calculator = Presto88PercentageCalculator(budget)
        for case in observation['cases']:
            with self.subTest(concept=case['concept']):
                self.assertEqual(calculator.price(case['concept']), Decimal(case['price']))
                for expected in case['percentage_rows']:
                    relation = next(r for r in budget.relations
                                    if r.parent_code == case['concept'] and r.child_code == expected['code'])
                    row = calculator.relation(relation.id)
                    self.assertEqual(row.quantity, Decimal(expected['quantity']))
                    self.assertEqual(row.unit_price, Decimal(expected['price']))
                    self.assertEqual(row.amount, Decimal(expected['amount']))
        self.assertEqual(calculator.total(), Decimal(observation['root_price']))
        self.assertEqual(dumps(budget), before)

    def test_native_percentage_base_rounding_before_multiplication(self):
        observation = json.loads((OBSERVATION.parent / 'porcentajes-orden-observados.json').read_text(encoding='utf-8'))
        for case in observation['native_rounding_cases']:
            with self.subTest(base=case['eligible_sum']):
                budget = self.load_export()
                for code in ('M01', 'M02'):
                    budget.concepts[code] = replace(budget.concepts[code],
                                                   base_price=Decimal(case['edits'][code + '_price']))
                relation = next(r for r in budget.relations if '%' in r.child_code)
                self.replace_relation(budget, relation,
                                      quantity=Decimal(case['edits']['percentage_rate']) / 100)
                self.assert_case(budget, case)
