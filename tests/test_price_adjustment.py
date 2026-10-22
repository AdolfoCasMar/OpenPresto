from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from openpresto.bc3_importer import import_bc3
from openpresto.bc3_exporter import save_bc3
from openpresto.budget import BudgetConcept, BudgetError, BudgetRelation
from openpresto.calculations import BudgetCalculator
from openpresto.price_adjustment import adjust_price
from openpresto.storage import dumps, loads, save_budget, load_budget


ROOT = Path(__file__).resolve().parents[1]


class PriceAdjustmentTests(unittest.TestCase):
    def project(self):
        budget = import_bc3(ROOT / 'tests/reference04/price_override/baseline.bc3',
                            observed_presto88=True).budget
        budget.concepts['OVR1'] = replace(budget.concepts['OVR1'], base_price=Decimal('5'))
        return budget

    def test_adjustment_preserves_graph_and_roundtrips_json_and_bc3(self):
        budget = self.project()
        original = dumps(budget)
        result = adjust_price(budget, 'OVITEM', Decimal('20'))
        self.assertEqual(dumps(budget), original)
        self.assertEqual(result.initial_price, Decimal('14'))
        self.assertEqual(result.achieved_price, Decimal('20.02'))
        self.assertEqual(result.changed_codes, ('OVR1', 'OVR2'))
        self.assertEqual(result.budget.relations, budget.relations)
        self.assertEqual(result.budget.concepts['OVITEM'], budget.concepts['OVITEM'])
        self.assertEqual(result.budget.locked_prices, {})
        self.assertEqual(BudgetCalculator(loads(dumps(result.budget))).total(), Decimal('140.14'))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'adjusted.json'
            save_budget(result.budget, path)
            self.assertEqual(BudgetCalculator(load_budget(path)).total(), Decimal('140.14'))
            bc3 = Path(folder) / 'adjusted.bc3'
            save_bc3(result.budget, bc3)
            imported = import_bc3(bc3, observed_presto88=True).budget
            self.assertEqual(BudgetCalculator(imported).total(), Decimal('140.14'))
            self.assertEqual(imported.concepts['OVR1'].base_price, Decimal('7.15'))

    def test_validation_failure_never_changes_input(self):
        budget = self.project()
        original = dumps(budget)
        for code, target in [('OVITEM', Decimal('100')), ('OVITEM', Decimal('NaN')),
                             ('OVITEM', Decimal('-1')), ('OVITEM', Decimal('0')),
                             ('OVITEM', Decimal('14')), ('OVR1', Decimal('10')),
                             ('OVROOT##', Decimal('20')), ('missing', Decimal('20'))]:
            with self.subTest(code=code, target=target), self.assertRaises(BudgetError):
                adjust_price(budget, code, target)
            self.assertEqual(dumps(budget), original)
        budget.locked_prices['OVITEM'] = Decimal('20')
        original = dumps(budget)
        with self.assertRaises(BudgetError):
            adjust_price(budget, 'OVITEM', Decimal('25'))
        self.assertEqual(dumps(budget), original)

    def test_arbitrary_codes_and_shared_resource_identity(self):
        budget = self.project()
        # A third direct resource also used by another partida is changed once.
        budget.add_concept(BudgetConcept('MATERIAL', nature='3', base_price=Decimal('2')))
        budget.add_concept(BudgetConcept('OTHER', base_price=Decimal('0')))
        budget.add_relation(BudgetRelation('OVITEM', 'MATERIAL', position=3))
        budget.add_relation(BudgetRelation('OTHER', 'MATERIAL'))
        budget.add_relation(BudgetRelation('OVA#', 'OTHER', position=2))
        result = adjust_price(budget, 'OVITEM', Decimal('32'))
        self.assertEqual(result.achieved_price, Decimal('32'))
        self.assertEqual(result.budget.concepts['MATERIAL'].base_price, Decimal('4'))
        self.assertEqual(BudgetCalculator(result.budget).price('OTHER'), Decimal('4'))
        self.assertEqual(result.changed_codes.count('MATERIAL'), 1)
        self.assertEqual(budget.concepts['MATERIAL'].base_price, Decimal('2'))

    def test_nested_decomposition_requires_its_own_contract(self):
        budget = self.project()
        budget.add_concept(BudgetConcept('NESTED', nature='3', base_price=Decimal('1')))
        budget.add_relation(BudgetRelation('OVR1', 'NESTED'))
        original = dumps(budget)
        with self.assertRaises(BudgetError):
            adjust_price(budget, 'OVITEM', Decimal('10'))
        self.assertEqual(dumps(budget), original)
