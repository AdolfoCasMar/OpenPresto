"""Batching shares work only within an explicit read-only evaluation."""
import unittest
from unittest.mock import patch
from decimal import Decimal
from openpresto.pzh_importer import _import
from openpresto.calculations import calculator_for, calculation_batch
from openpresto.budget import BudgetError
from test_pzh_percentages import fixture


class CalculationBatchTests(unittest.TestCase):
    def setUp(self):
        self.budget=_import(fixture(),'synthetic.pzh').budget
        self.calc=calculator_for(self.budget)

    def test_batch_matches_independent_evaluations(self):
        prices={code:self.calc.price(code) for code in self.budget.concepts}
        relations={r.id:self.calc.relation(r.id) for r in self.budget.relations}
        with self.calc.batch():
            self.assertEqual({code:self.calc.price(code) for code in prices},prices)
            self.assertEqual({rid:self.calc.relation(rid) for rid in relations},relations)
        self.assertEqual(self.calc.total(),Decimal('77.06'))

    def test_component_work_is_shared_and_nested_scopes_are_safe(self):
        with patch.object(self.budget,'relation_quantity',wraps=self.budget.relation_quantity) as quantity:
            with self.calc.batch():
                self.calc.total()
                calls=quantity.call_count
                with self.calc.batch():
                    for r in self.budget.relations:self.calc.relation(r.id)
                    for code in self.budget.concepts:self.calc.price(code)
                self.assertEqual(quantity.call_count,calls)

    def test_next_call_sees_edit_after_batch(self):
        from openpresto.percentage_calculations import set_percentage_rate
        with calculation_batch(self.calc):self.assertEqual(self.calc.total(),Decimal('77.06'))
        set_percentage_rate(self.budget,'M%10','20')
        self.assertEqual(self.calc.total(),Decimal('84.07'))

    def test_exception_releases_cache_and_later_edit_is_visible(self):
        with self.assertRaises(BudgetError),self.calc.batch():
            self.calc.total()
            self.calc.price('MISSING')
        self.assertEqual(self.calc._batch_depth,0)
        from openpresto.percentage_calculations import set_percentage_rate
        set_percentage_rate(self.budget,'M%10','20')
        self.assertEqual(self.calc.total(),Decimal('84.07'))


if __name__=='__main__':unittest.main()
