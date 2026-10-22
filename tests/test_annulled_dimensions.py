"""Manual p.58 geometric annulment; no recent-runtime equivalence claim."""
from dataclasses import replace
from decimal import Decimal
import json
import unittest

from openpresto.budget import Budget, BudgetConcept, BudgetMeasurement, BudgetRelation, BudgetError
from openpresto.storage import dumps, loads, StorageError
from openpresto.bc3_exporter import render_bc3, BC3ExportError


class AnnulledDimensionsTests(unittest.TestCase):
    def test_surface_volume_and_retained_precision(self):
        m = BudgetMeasurement('r', n_lines='2', length='3', width='4', height='0.23456',
                              annulled_dimensions=('height',))
        self.assertEqual(m.partial(), Decimal('24'))
        self.assertEqual(m.height, Decimal('0.23456'))
        self.assertEqual(replace(m, annulled_dimensions=()).partial(), Decimal('5.62944'))
        self.assertEqual(replace(m, annulled_dimensions=('n_lines', 'height')).partial(), Decimal('12'))

    def test_zero_annulled_is_excluded(self):
        m = BudgetMeasurement('r', n_lines=2, length=3, height=0)
        self.assertEqual(m.partial(), 0)
        self.assertEqual(replace(m, annulled_dimensions=('height',)).partial(), 6)

    def test_invalid_flags_and_native_formula_annulment(self):
        for flags in (('bad',), ('height', 'height'), ['height']):
            with self.assertRaises(BudgetError):
                BudgetMeasurement('r', annulled_dimensions=flags)
        for formula in ('B', 'D'):
            line = BudgetMeasurement('r', n_lines=2, length=3, width=4, height='0.23456',
                                     formula=formula, annulled_dimensions=('height',))
            self.assertEqual(line.partial(), Decimal('24'))
            self.assertEqual(line.height, Decimal('0.23456'))

    def test_v7_roundtrip_and_export_guard(self):
        b = Budget('ROOT')
        b.add_concept(BudgetConcept('ROOT'))
        b.add_concept(BudgetConcept('ITEM', base_price=2))
        b.add_relation(BudgetRelation('ROOT', 'ITEM', id='r'))
        b.add_measurement(BudgetMeasurement('r', n_lines=2, length=3, width=4,
                         height='0.2', annulled_dimensions=('height',)))
        encoded = dumps(b)
        self.assertEqual(json.loads(encoded)['version'], 7)
        restored = loads(encoded)
        self.assertEqual(restored.concept_price('ROOT'), 48)
        self.assertEqual(restored.measurements[0].height, Decimal('0.2'))
        with self.assertRaises(BC3ExportError):
            render_bc3(restored)
        invalid = json.loads(encoded)
        invalid['measurements'][0]['annulled_dimensions'] = 'height'
        with self.assertRaises(StorageError):
            loads(json.dumps(invalid))


if __name__ == '__main__':
    unittest.main()
