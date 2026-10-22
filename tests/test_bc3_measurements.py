"""Pruebas de interpretación conservadora de mediciones BC3."""
import unittest
from decimal import Decimal
from pathlib import Path

from openpresto.bc3_measurements import (
    MeasurementParseError, evaluate_formula, parse_measurement, inspect_import,
)
from openpresto.bc3_importer import import_bc3


class BC3MeasurementTests(unittest.TestCase):
    def test_plain_lines_and_optional_dimensions(self):
        value = parse_measurement("|".join(("C\\P", "1\\1\\", "9.50", "\\".join(("", "Zona", "1", "3", "2", "", "", "Otra", "1", "3.5", "", "", "")))))
        self.assertEqual(len(value.lines), 2)
        self.assertEqual(value.calculated_quantity, Decimal("9.5"))
        self.assertEqual(value.declared_quantity, Decimal("9.50"))

    def test_zero_dimension(self):
        line = parse_measurement("|".join(("C\\P", "1\\1\\", "0", "\\".join(("", "Cero", "2", "0", "", "", "")))))
        self.assertEqual(line.calculated_quantity, Decimal("0"))

    def test_arithmetic_and_variables(self):
        self.assertEqual(evaluate_formula("(b+c)/2*d", "1", "17", "9", "0.5"), Decimal("6.5"))
        self.assertEqual(evaluate_formula("2*(3+5+2)*0.5-2.98"), Decimal("7.02"))

    def test_reject_unsafe_formula(self):
        for expression in ('__import__("os")', 'b**99999', '[1,2,3]', '1/0'):
            with self.subTest(expression=expression), self.assertRaises(MeasurementParseError):
                evaluate_formula(expression)

    def test_special_rows_preserved_not_summed(self):
        value = parse_measurement("|".join(("C\\P", "1\\1\\", "2", "\\".join(("1", "Subtotal", "", "", "", "", "")))))
        self.assertEqual(len(value.lines), 1)
        self.assertEqual(value.calculated_quantity, Decimal("0"))
        self.assertEqual(value.lines[0].partial, Decimal("0"))
        self.assertFalse(value.warnings)

    def test_malformed_record_rejected(self):
        for value in ('x', "C\\P|1\\1\\|2|\\missing\\1\\"):
            with self.subTest(value=value), self.assertRaises(MeasurementParseError):
                parse_measurement(value)



if __name__ == "__main__":
    unittest.main()
