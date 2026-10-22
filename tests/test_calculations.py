"""Pruebas de la política económica de OpenPresto."""
import unittest
from decimal import Decimal

from openpresto.budget import (
    Budget, BudgetConcept, BudgetError, BudgetMeasurement, BudgetRelation,
)
from openpresto.calculations import BudgetCalculator, CalculationPolicy


class CalculationTests(unittest.TestCase):
    def setUp(self):
        self.budget = Budget("OBRA")
        for code, price in (("OBRA", "0"), ("CAP", "0"), ("P", "0"),
                            ("MAT", "12.345"), ("MANO", "4.25")):
            self.budget.add_concept(BudgetConcept(code, base_price=price))
        self.budget.add_relation(BudgetRelation("OBRA", "CAP", id="r_cap"))
        self.budget.add_relation(BudgetRelation("CAP", "P", quantity="2", id="r_p"))
        self.budget.add_relation(BudgetRelation("P", "MAT", quantity="3", id="r_mat"))
        self.budget.add_relation(BudgetRelation("P", "MANO", quantity="2", position=2, id="r_mano"))
        self.calc = BudgetCalculator(self.budget)

    def test_rounding_half_up_positive_and_negative(self):
        policy = CalculationPolicy()
        self.assertEqual(policy.price(Decimal("1.235")), Decimal("1.24"))
        self.assertEqual(policy.price(Decimal("-1.235")), Decimal("-1.24"))

    def test_different_precisions(self):
        policy = CalculationPolicy(4, 3, 2)
        self.assertEqual(policy.quantity(Decimal("1.23456")), Decimal("1.2346"))
        self.assertEqual(policy.price(Decimal("1.23456")), Decimal("1.235"))
        self.assertEqual(policy.amount(Decimal("1.23456")), Decimal("1.23"))

    def test_invalid_precisions_rejected(self):
        for bad in (-1, 13, 2.5, True):
            with self.subTest(bad=bad), self.assertRaises(BudgetError):
                CalculationPolicy(price_decimals=bad)

    def test_leaf_price(self):
        self.assertEqual(self.calc.price("MAT"), Decimal("12.35"))

    def test_root_precision_only_applies_to_direct_relations(self):
        self.budget.add_measurement(BudgetMeasurement('r_cap', n_lines='1.49'))
        self.budget.add_measurement(BudgetMeasurement('r_p', n_lines='2.019'))
        calculator = BudgetCalculator(self.budget, CalculationPolicy(root_quantity_decimals=0))
        self.assertEqual(calculator.quantity('r_cap'), Decimal('1'))
        self.assertEqual(calculator.quantity('r_p'), Decimal('2.019'))
        self.assertEqual(self.budget.relation_quantity('r_cap'), Decimal('1.49'))
        self.assertEqual(BudgetCalculator(self.budget).quantity('r_cap'), Decimal('1.490'))

    def test_invalid_root_precision_rejected(self):
        for bad in (-1, 13, True, '2', 2.5):
            with self.subTest(bad=bad), self.assertRaises(BudgetError):
                CalculationPolicy(root_quantity_decimals=bad)

    def test_recursive_decomposed_price(self):
        # P = 3*12.35 + 2*4.25 = 45.55; CAP = 2*45.55 = 91.10
        self.assertEqual(self.calc.price("P"), Decimal("45.55"))
        self.assertEqual(self.calc.price("CAP"), Decimal("91.10"))
        self.assertEqual(self.calc.total(), Decimal("91.10"))

    def test_relation_amount_and_identity(self):
        result = self.calc.relation("r_p")
        self.assertEqual(result.relation_id, "r_p")
        self.assertEqual(result.quantity, Decimal("2.000"))
        self.assertEqual(result.unit_price, Decimal("45.55"))
        self.assertEqual(result.amount, Decimal("91.10"))

    def test_measurements_replace_quantity(self):
        self.budget.add_measurement(
            BudgetMeasurement("r_p", n_lines="2", length="2.5", id="m1")
        )
        self.assertEqual(self.calc.quantity("r_p"), Decimal("5.000"))
        self.assertEqual(self.calc.total(), Decimal("227.75"))

    def test_zero_dimension_produces_zero_amount(self):
        self.budget.add_measurement(BudgetMeasurement("r_p", n_lines="2", length="0"))
        self.assertEqual(self.calc.relation("r_p").amount, Decimal("0.00"))
        self.assertEqual(self.calc.total(), Decimal("0.00"))

    def test_deductions_keep_negative_sign(self):
        self.budget.add_measurement(BudgetMeasurement("r_p", n_lines="-1"))
        self.assertEqual(self.calc.relation("r_p").amount, Decimal("-45.55"))
        self.assertEqual(self.calc.total(), Decimal("-45.55"))

    def test_no_double_count_and_no_mutation(self):
        previous = self.budget.total()
        self.assertEqual(self.calc.total(), Decimal("91.10"))
        self.assertEqual(self.budget.total(), previous)
        self.assertEqual(previous, Decimal("91.070"))

    def test_missing_references_raise(self):
        with self.assertRaises(BudgetError):
            self.calc.price("UNKNOWN")
        with self.assertRaises(BudgetError):
            self.calc.relation("UNKNOWN")

    def test_missing_root_raises(self):
        self.budget.root_code = None
        with self.assertRaises(BudgetError):
            self.calc.total()

    def test_precision_can_change_totals(self):
        exact = BudgetCalculator(self.budget, CalculationPolicy(3, 3, 3))
        self.assertEqual(exact.price("MAT"), Decimal("12.345"))
        self.assertEqual(exact.total(), Decimal("91.070"))


if __name__ == "__main__":
    unittest.main()
