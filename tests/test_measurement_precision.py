"""Documented per-concept precision and independently observed length tie."""
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import unittest

from openpresto.budget import Budget, BudgetConcept, BudgetRelation, BudgetMeasurement, BudgetError
from openpresto.storage import dumps, loads
from openpresto.bc3_exporter import render_bc3, BC3ExportError


class MeasurementPrecisionTests(unittest.TestCase):
    def budget(self, decimals=2):
        b = Budget('ROOT')
        b.add_concept(BudgetConcept('ROOT'))
        b.add_concept(BudgetConcept('ITEM', base_price=2, measurement_decimals=decimals))
        b.add_relation(BudgetRelation('ROOT', 'ITEM', id='r'))
        return b

    def test_documented_geometry_cases(self):
        cases = json.loads((Path(__file__).parent / 'reference04/modern_geometry_contracts.json').read_text(encoding='utf-8'))
        names = {'n':'n_lines','length':'length','width':'width','height':'height'}
        for case in cases['cases']:
            with self.subTest(case=case['id']):
                m = BudgetMeasurement('r', n_lines=case['n'], length=case['length'],
                     width=case['width'], height=case['height'],
                     annulled_dimensions=tuple(names[n] for n in case['annulled']))
                b = self.budget(case['redparc'])
                b.add_measurement(m)
                self.assertEqual(b.measurement_partial(m), Decimal(case['expected_partial']))

    def test_observed_length_and_precision_recovery(self):
        path = Path(__file__).resolve().parents[1] / 'docs/evidencias-04/ensayos/longitud-redondeada-observada.json'
        case = json.loads(path.read_text(encoding='utf-8'))
        b = self.budget()
        m = BudgetMeasurement('r', n_lines=case['input']['n'], length=case['input']['length'])
        b.add_measurement(m)
        self.assertEqual(b.relation_quantity('r'), Decimal(case['displayed']['partial']))
        restored = loads(dumps(b))
        self.assertEqual(json.loads(dumps(b))['version'], 8)
        self.assertEqual(restored.measurements[0].length, Decimal('1.005'))
        restored.concepts['ITEM'] = replace(restored.concepts['ITEM'], measurement_decimals=3)
        self.assertEqual(restored.relation_quantity('r'), Decimal('2.010'))
        restored.concepts['ITEM'] = replace(restored.concepts['ITEM'], measurement_decimals=None)
        self.assertEqual(restored.relation_quantity('r'), Decimal('2.010'))
        with self.assertRaises(BC3ExportError):
            render_bc3(b)

    def test_precision_applies_to_each_partial_before_sum(self):
        b = self.budget()
        for _ in range(2):
            b.add_measurement(BudgetMeasurement('r', n_lines='0.005'))
        self.assertEqual(b.relation_quantity('r'), Decimal('.02'))

    def test_validation_and_native_formula_precision(self):
        for value in (True, -1, 13, '2', 2.0):
            with self.assertRaises(BudgetError):
                self.budget(value)
        b = self.budget()
        line = BudgetMeasurement('r', n_lines='2', length='1.005', formula='B')
        b.add_measurement(line)
        self.assertEqual(b.measurement_partial(line), Decimal('2.02'))
        restored = loads(dumps(b))
        self.assertEqual(restored.relation_quantity('r'), Decimal('2.02'))
        with self.assertRaises(BudgetError):
            b.add_measurement(BudgetMeasurement('r', formula='UNKNOWN'))


if __name__ == '__main__':
    unittest.main()
