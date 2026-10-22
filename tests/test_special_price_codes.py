"""Do not present an unsupported percentage/subtotal as an ordinary resource."""
import hashlib
import json
from pathlib import Path
import unittest

from openpresto.budget import Budget, BudgetConcept, BudgetRelation, BudgetError
from openpresto.bc3_importer import import_bc3
from openpresto.calculations import BudgetCalculator
from openpresto.storage import dumps, loads


class SpecialPriceCodeTests(unittest.TestCase):
    def test_both_calculators_reject_special_codes(self):
        for code in ('M%10', '%GEN', 'ƩTOTAL', 'ΣTOTAL', '∑TOTAL', 'ƩƩ%TOTAL'):
            with self.subTest(code=code):
                b = Budget('ROOT')
                b.add_concept(BudgetConcept('ROOT'))
                b.add_concept(BudgetConcept(code, base_price=10))
                b.add_relation(BudgetRelation('ROOT',code,quantity=999))
                for calculate in (b.total, BudgetCalculator(b).total):
                    with self.assertRaises(BudgetError):
                        calculate()

    def test_import_preserves_unimplemented_conversion_without_claiming_a_total(self):
        directory = Path(__file__).parent / 'reference04/percentages'
        fixture = directory / 'prefix_pending.bc3'
        original = fixture.read_bytes()
        metadata = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(hashlib.sha256(original).hexdigest(), metadata['fixture_sha256'])
        self.assertEqual(metadata['status'], 'observed_import_conversion')
        root = Path(__file__).resolve().parents[1]
        observation_path = root / metadata['runtime_observation']
        observation = json.loads(observation_path.read_text(encoding='utf-8'))
        self.assertEqual(observation['input_fixture_sha256'], metadata['fixture_sha256'])
        self.assertEqual(observation['cases'][0]['item_price'], '50100.00')
        self.assertNotEqual(observation['cases'][0]['item_price'],
                            metadata['own_mathematical_expectation']['item_amount'])
        for filename, digest in observation['evidence_sha256'].items():
            self.assertEqual(hashlib.sha256((observation_path.parent / filename).read_bytes()).hexdigest(), digest)
        for profile in (False, True):
            result = import_bc3(fixture, observed_presto88=profile)
            self.assertTrue(any('Cálculo no disponible: M%10' in warning for warning in result.warnings))
            restored = loads(dumps(result.budget))
            relation = next(r for r in restored.relations if r.child_code == 'M%10')
            self.assertEqual(relation.quantity, 999)
            with self.assertRaises(BudgetError):
                BudgetCalculator(restored).total()
        self.assertEqual(fixture.read_bytes(), original)
