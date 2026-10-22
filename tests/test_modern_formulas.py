"""Documented grammar, mathematical checks, persistence and separation of profiles.

These are not runtime observations of a recent Presto installation.
"""
from dataclasses import replace
from decimal import Decimal
import json
import unittest

from openpresto.modern_formulas import evaluate_modern_formula as evaluate, ModernFormulaError, PI
from openpresto.budget import Budget, BudgetConcept, BudgetMeasurement, BudgetRelation
from openpresto.storage import dumps, loads, StorageError
from openpresto.bc3_measurements import evaluate_formula
from openpresto.bc3_exporter import render_bc3, BC3ExportError


class ModernFormulaTests(unittest.TestCase):
    def test_unused_dimensions_multiply_result(self):
        self.assertEqual(evaluate('(B+C)/2', 2, 3, 5, 4), Decimal('32'))
        self.assertEqual(evaluate('B', 0, 3, 4, 5), Decimal('0'))
        self.assertEqual(evaluate('(b+c)/2', 2, 3, 5, 4), Decimal('32'))

    def test_power_pi_abs_and_root(self):
        self.assertEqual(evaluate('B^2', 2, 3), Decimal('18'))
        self.assertEqual(evaluate('P'), PI)
        self.assertEqual(evaluate('ABS(-B)', -2, -3), Decimal('-6'))
        self.assertEqual(evaluate('SQRT(B)', 2, 9, 4), Decimal('24'))
        self.assertEqual(evaluate('1e-2+0.1'), Decimal('0.11'))

    def test_trigonometry_uses_degrees(self):
        self.assertEqual(evaluate('SIN(A)', 90), Decimal('1'))
        self.assertEqual(evaluate('COS(A)', 180), Decimal('-1'))
        self.assertLess(abs(evaluate('COS(A)', 60) - Decimal('0.5')), Decimal('1e-35'))
        self.assertLess(abs(evaluate('TAN(A)', 45) - Decimal('1')), Decimal('1e-35'))
        with self.assertRaises(ModernFormulaError): evaluate('TAN(A)', 90)

    def test_unsafe_unimplemented_or_invalid_expressions_rejected(self):
        for expression in ('__import__("os")', 'a.__class__', '[x for x in ()]',
                           'open("x")', 'True', '1/0', 'SQRT(-1)', '2^1000',
                           'IPE(C)', '$[Mediciones.BIMVol]$', '=A/B.CanPres', 'a//2', 'foo', '2^^3'):
            with self.subTest(expression=expression), self.assertRaises(ModernFormulaError):
                evaluate(expression)

    def test_bc3_formula_profile_does_not_gain_modern_semantics(self):
        self.assertEqual(evaluate_formula('(b+c)/2', '2', '3', '5', '4'), Decimal('4'))
        self.assertEqual(evaluate('(b+c)/2', 2, 3, 5, 4), Decimal('32'))

    def budget(self):
        budget = Budget('ROOT')
        budget.add_concept(BudgetConcept('ROOT'))
        budget.add_concept(BudgetConcept('ITEM', base_price='2'))
        budget.add_relation(BudgetRelation('ROOT', 'ITEM', id='r'))
        budget.add_measurement(BudgetMeasurement('r', n_lines='2', length='3', width='5', height='4', formula='(B+C)/2'))
        return budget

    def test_native_formula_roundtrip_v6_and_legacy_geometry_unchanged(self):
        budget = self.budget()
        self.assertEqual(budget.relation_quantity('r'), Decimal('32'))
        restored = loads(dumps(budget))
        self.assertEqual(json.loads(dumps(restored))['version'], 6)
        self.assertEqual(restored.relation_quantity('r'), Decimal('32'))
        self.assertEqual(restored.measurements[0].formula, '(B+C)/2')
        legacy = replace(restored.measurements[0], formula='')
        self.assertEqual(legacy.partial(), Decimal('120'))
        with self.assertRaises(BC3ExportError): render_bc3(restored)

    def test_invalid_persisted_formula_rejected_before_opening(self):
        document = json.loads(dumps(self.budget()))
        document['measurements'][0]['formula'] = '1/0'
        with self.assertRaises(StorageError): loads(json.dumps(document))
