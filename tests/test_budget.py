"""Pruebas del modelo jerárquico de presupuestos."""

import unittest
from decimal import Decimal as D

from openpresto.budget import Budget, BudgetConcept, BudgetError, BudgetMeasurement, BudgetRelation


class BudgetTests(unittest.TestCase):
    def make_budget(self):
        b = Budget("OBRA")
        for code, price in (("OBRA", "0"), ("01", "0"), ("P1", "0"), ("P2", "0"), ("MO", "12.50")):
            b.add_concept(BudgetConcept(code, base_price=D(price)))
        b.add_relation(BudgetRelation("OBRA", "01", id="r0"))
        b.add_relation(BudgetRelation("01", "P1", quantity=D("2"), id="r1"))
        b.add_relation(BudgetRelation("01", "P2", quantity=D("3"), position=2, id="r2"))
        b.add_relation(BudgetRelation("P1", "MO", quantity=D("0.5"), id="r3"))
        b.add_relation(BudgetRelation("P2", "MO", quantity=D("1.5"), id="r4"))
        return b

    def test_nested_prices_and_total_without_double_count(self):
        b = self.make_budget()
        self.assertEqual(b.concept_price("P1"), D("6.250"))
        self.assertEqual(b.concept_price("P2"), D("18.750"))
        self.assertEqual(b.total(), D("68.750"))
        self.assertEqual(b.relation_amount("r1"), D("12.500"))

    def test_reuse_has_independent_quantities(self):
        b = self.make_budget()
        self.assertEqual(b.relation_quantity("r3"), D("0.5"))
        self.assertEqual(b.relation_quantity("r4"), D("1.5"))
        self.assertEqual(len(b.concepts), 5)

    def test_measurements_override_relation_quantity(self):
        b = self.make_budget()
        b.add_measurement(BudgetMeasurement("r1", n_lines=D("2"), length=D("3"), width=D("4")))
        b.add_measurement(BudgetMeasurement("r1", n_lines=D("-1"), length=D("2"), width=D("3")))
        self.assertEqual(b.relation_quantity("r1"), D("18"))
        self.assertEqual(b.total(), D("168.750"))

    def test_optional_zero_and_negative_dimensions(self):
        self.assertEqual(BudgetMeasurement("r", n_lines=D("2"), length=None).partial(), D("2"))
        self.assertEqual(BudgetMeasurement("r", n_lines=D("2"), length=D("0")).partial(), D("0"))
        self.assertEqual(BudgetMeasurement("r", n_lines=D("-2"), length=D("3")).partial(), D("-6"))
        self.assertEqual(BudgetMeasurement("r", n_lines=D("2"), length=D("-3")).partial(), D("-6"))

    def test_cycle_direct_and_indirect(self):
        b = self.make_budget()
        with self.assertRaises(BudgetError):
            b.add_relation(BudgetRelation("MO", "01", id="cycle"))
        with self.assertRaises(BudgetError):
            b.add_relation(BudgetRelation("P1", "P1", id="self"))
        self.assertEqual(len(b.relations), 5)

    def test_diamond_is_not_a_cycle(self):
        b = self.make_budget()
        b.add_concept(BudgetConcept("EXTRA"))
        b.add_relation(BudgetRelation("P1", "EXTRA", position=2, id="extra"))
        b.add_relation(BudgetRelation("P2", "EXTRA", position=2, id="extra2"))
        self.assertEqual(len(b.relations), 7)

    def test_duplicate_missing_and_invalid(self):
        b = self.make_budget()
        with self.assertRaises(BudgetError):
            b.add_concept(BudgetConcept("MO"))
        with self.assertRaises(BudgetError):
            b.add_relation(BudgetRelation("P1", "UNKNOWN", id="missing"))
        with self.assertRaises(BudgetError):
            b.add_relation(BudgetRelation("P1", "MO", position=1, id="duplicate_position"))
        with self.assertRaises(BudgetError):
            b.add_measurement(BudgetMeasurement("missing"))
        with self.assertRaises(BudgetError):
            BudgetConcept("X", base_price=0.3)
        with self.assertRaises(BudgetError):
            BudgetMeasurement("r", n_lines=D("NaN"))

    def test_decimal_no_implicit_rounding(self):
        b = Budget("ROOT")
        b.add_concept(BudgetConcept("ROOT"))
        b.add_concept(BudgetConcept("ITEM", base_price=D("1.23456")))
        b.add_relation(BudgetRelation("ROOT", "ITEM", quantity=D("0.333"), id="rel"))
        self.assertEqual(b.total(), D("0.41110848"))

    def test_root_is_explicit(self):
        b = Budget()
        b.add_concept(BudgetConcept("A", base_price=D("1")))
        with self.assertRaises(BudgetError):
            b.total()
        b.set_root("A")
        self.assertEqual(b.total(), D("1"))


if __name__ == "__main__":
    unittest.main()
