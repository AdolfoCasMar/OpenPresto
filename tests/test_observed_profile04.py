"""Limited optional profile compared to independent Presto observations."""
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import unittest

from openpresto.bc3_importer import import_bc3
from openpresto.bc3_measurements import rebuild_record, parse_measurement
from openpresto.calculations import BudgetCalculator
from openpresto.storage import dumps, loads, StorageError

ROOT = Path(__file__).resolve().parents[1]


class ObservedProfileTests(unittest.TestCase):
    def test_zero_dimension_profile_does_not_change_zero_n_or_formulas(self):
        ordinary = parse_measurement('R\\P|1|0|\\N cero\\0\\4\\\\\\|', zero_dimensions_as_blank=True)
        self.assertEqual(ordinary.calculated_quantity, Decimal('0'))
        formula = parse_measurement('R\\P|1|0|3\\a*b\\2\\0\\\\\\|', zero_dimensions_as_blank=True)
        self.assertEqual(formula.calculated_quantity, Decimal('0'))

    def test_five_cases_match_observed_economic_fields_and_persist(self):
        directory = ROOT / 'docs/evidencias-04/ensayos'
        for name in ('simple', 'reuse', 'dimensions', 'rounding', 'factor_text'):
            with self.subTest(case=name):
                observation = json.loads((directory / f'{name}-observado.json').read_text(encoding='utf-8'))
                fixture = ROOT / observation['fixture']
                original = fixture.read_bytes()
                self.assertEqual(hashlib.sha256(original).hexdigest(), observation['fixture_sha256'])
                budget = import_bc3(fixture, observed_presto88=True).budget
                restored = loads(dumps(budget))
                self.assertEqual(json.loads(dumps(restored))['version'], 5)
                self.assertEqual(fixture.read_bytes(), original)
                calculator = BudgetCalculator(restored)
                for code, price in observation['observed_prices'].items():
                    self.assertEqual(calculator.price(code), Decimal(price))
                for observed in observation.get('observed_relations', []):
                    relations = [r for r in restored.relations if r.parent_code == observed['parent']
                                 and r.child_code == observed['child']]
                    self.assertEqual(len(relations), 1)
                    relation = relations[0]
                    amount = calculator.relation(relation.id)
                    self.assertEqual(amount.quantity, Decimal(observed['quantity']))
                    self.assertEqual(amount.unit_price, Decimal(observed['unit_price']))
                    self.assertEqual(amount.amount, Decimal(observed['amount']))
                    if 'factor' in observed:
                        self.assertEqual(relation.factor, Decimal(observed['factor']))

    def test_rebuilding_measurements_retains_profile_and_negative_deduction(self):
        budget = import_bc3(ROOT / 'tests/reference04/presto88/dimensions.bc3', observed_presto88=True).budget
        record = next(iter(budget.bc3_measurements.values()))
        rebuilt = rebuild_record(record, record.lines)
        self.assertTrue(rebuilt.zero_dimensions_as_blank)
        self.assertEqual([r.partial for r in rebuilt.lines], list(map(Decimal, ['6', '4', '-2', '0'])))
        self.assertEqual(rebuilt.calculated_quantity, Decimal('8'))

    def test_invalid_factor_and_profile_metadata_rejected(self):
        budget = import_bc3(ROOT / 'tests/reference04/presto88/factor_text.bc3', observed_presto88=True).budget
        document = json.loads(dumps(budget))
        document['relations'][0]['factor'] = 'NaN'
        with self.assertRaises(StorageError):
            loads(json.dumps(document))
        document = json.loads(dumps(budget))
        document['calculation']['bc3_zero_dimensions_as_blank'] = 1
        with self.assertRaises(StorageError):
            loads(json.dumps(document))
