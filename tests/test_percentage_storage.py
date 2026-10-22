import copy
import unittest
from decimal import Decimal
from pathlib import Path

from openpresto.bc3_importer import import_bc3
from openpresto.calculations import calculator_for
from openpresto.percentage_calculations import set_percentage_rate
from openpresto.storage import dumps, loads, to_dict, from_dict, StorageError


class PercentageStorageTests(unittest.TestCase):
    def test_v11_preserves_source_profile_and_all_base_project_fields(self):
        source = Path(__file__).parent / 'reference04/percentages/order_scope.bc3'
        budget = import_bc3(source, observed_presto88=True).budget
        legacy = to_dict(budget)
        budget.percentage_profile = 'presto88_bc3'
        document = to_dict(budget)
        self.assertEqual(document['version'], 11)
        self.assertEqual(document['project'], legacy)
        restored = loads(dumps(budget))
        self.assertEqual(to_dict(restored), document)
        self.assertEqual(restored.total(), Decimal('840.73'))
        self.assertEqual(restored.source_records, budget.source_records)
        percentage = next(r for r in restored.relations if r.child_code == 'M%FIRST')
        self.assertEqual(restored.relation_quantity(percentage.id), Decimal('.701'))
        self.assertEqual(percentage.quantity, Decimal('.1'))
        set_percentage_rate(restored, 'M%FIRST', '20')
        self.assertEqual(calculator_for(restored).total(), Decimal('848.44'))
        self.assertEqual(loads(dumps(restored)).total(), Decimal('848.44'))
        for variant in ('profile', 'nested', 'extra'):
            broken = copy.deepcopy(document)
            if variant == 'profile':
                broken['percentage_profile'] = 'unknown'
            elif variant == 'nested':
                broken['project'] = document
            else:
                broken['extra'] = True
            with self.subTest(variant=variant), self.assertRaises(StorageError):
                from_dict(broken)

    def test_v11_wraps_existing_measurement_and_certification_formats_without_loss(self):
        from openpresto.storage import load_budget
        folder = Path(__file__).resolve().parents[1] / 'openpresto/data'
        for filename in ('medicion-formula-demo.openpresto.json',
                         'medicion-anulada-demo.openpresto.json',
                         'medicion-precision-demo.openpresto.json',
                         'certificacion-demo.openpresto.json',
                         'certificacion-fases-demo.openpresto.json'):
            with self.subTest(filename=filename):
                budget = load_budget(folder / filename)
                before = to_dict(budget)
                budget.percentage_profile = 'presto88_bc3'
                restored = loads(dumps(budget))
                self.assertEqual(to_dict(restored)['project'], before)
