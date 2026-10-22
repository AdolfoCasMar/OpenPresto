"""Pruebas de desglose y subtotales de mediciones."""
import unittest
from decimal import Decimal

from openpresto.budget import (
    Budget, BudgetConcept, BudgetError, BudgetMeasurement, BudgetRelation,
)
from openpresto.measurements import (
    line_partial, summarize_budget, summarize_relation,
)


class MeasurementTests(unittest.TestCase):
    def setUp(self):
        self.budget = Budget("OBRA")
        self.budget.add_concept(BudgetConcept("OBRA"))
        self.budget.add_concept(BudgetConcept("P1", unit="m2"))
        self.budget.add_concept(BudgetConcept("P2", unit="m"))
        self.r1 = BudgetRelation("OBRA", "P1", "9", 1, id="r1")
        self.r2 = BudgetRelation("OBRA", "P2", "4", 2, id="r2")
        self.budget.add_relation(self.r1)
        self.budget.add_relation(self.r2)

    def test_manual_quantity_when_no_measurements(self):
        summary = summarize_relation(self.budget, "r1")
        self.assertEqual(summary.quantity, Decimal("9"))
        self.assertFalse(summary.uses_measurements)
        self.assertEqual(summary.entries, ())
        self.assertEqual(summary.positives, 0)
        self.assertEqual(summary.deductions, 0)

    def test_measurements_override_manual_quantity(self):
        self.budget.add_measurement(
            BudgetMeasurement("r1", n_lines="2", length="3", width="4", id="m1")
        )
        summary = summarize_relation(self.budget, "r1")
        self.assertEqual(summary.quantity, Decimal("24"))
        self.assertEqual(summary.positives, Decimal("24"))
        self.assertTrue(summary.uses_measurements)
        self.assertEqual(summary.entries[0].id, "m1")
        self.assertEqual(self.budget.relation_quantity("r1"), summary.quantity)

    def test_negative_deduction_and_positive(self):
        self.budget.add_measurement(
            BudgetMeasurement("r1", comment="Superficie", n_lines="2",
                              length="5", id="m1")
        )
        self.budget.add_measurement(
            BudgetMeasurement("r1", comment="A deducir", n_lines="-1",
                              length="3", id="m2")
        )
        summary = summarize_relation(self.budget, "r1")
        self.assertEqual(summary.positives, Decimal("10"))
        self.assertEqual(summary.deductions, Decimal("-3"))
        self.assertEqual(summary.quantity, Decimal("7"))
        self.assertEqual([e.comment for e in summary.entries],
                         ["Superficie", "A deducir"])

    def test_missing_dimensions_and_explicit_zero(self):
        a = BudgetMeasurement("r1", n_lines="2", length=None, width="3")
        b = BudgetMeasurement("r1", n_lines="5", length=Decimal("0"))
        self.assertEqual(line_partial(a), Decimal("6"))
        self.assertEqual(line_partial(b), Decimal("0"))

    def test_zero_measurements_still_override_manual_quantity(self):
        self.budget.add_measurement(
            BudgetMeasurement("r1", n_lines="2", length="0")
        )
        summary = summarize_relation(self.budget, "r1")
        self.assertEqual(summary.quantity, Decimal("0"))
        self.assertEqual(summary.zero_lines, 1)
        self.assertTrue(summary.uses_measurements)

    def test_decimal_precision_preserved(self):
        self.budget.add_measurement(
            BudgetMeasurement("r1", n_lines="0.125", length="0.333")
        )
        summary = summarize_relation(self.budget, "r1")
        self.assertEqual(summary.quantity, Decimal("0.041625"))

    def test_relations_are_independent(self):
        self.budget.add_measurement(
            BudgetMeasurement("r1", n_lines="10", id="m1")
        )
        self.assertEqual(summarize_relation(self.budget, "r1").quantity, 10)
        self.assertEqual(summarize_relation(self.budget, "r2").quantity, 4)

    def test_budget_summary_does_not_sum_incompatible_units(self):
        summaries = summarize_budget(self.budget)
        self.assertEqual(tuple(s.relation_id for s in summaries), ("r1", "r2"))
        self.assertEqual(tuple(s.quantity for s in summaries),
                         (Decimal("9"), Decimal("4")))

    def test_unknown_relation_is_rejected(self):
        with self.assertRaises(BudgetError):
            summarize_relation(self.budget, "no-existe")

    def test_no_mutation_of_budget(self):
        line = BudgetMeasurement("r1", n_lines="2", length="3", id="m1")
        self.budget.add_measurement(line)
        before = tuple(self.budget.measurements)
        summarize_relation(self.budget, "r1")
        summarize_budget(self.budget)
        self.assertEqual(tuple(self.budget.measurements), before)
        self.assertIsNone(line.width)


if __name__ == "__main__":
    unittest.main()
