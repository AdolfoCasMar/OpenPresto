from dataclasses import replace
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from openpresto.bc3_importer import import_bc3, BC3ImportError
from openpresto.bc3_exporter import render_bc3, BC3ExportError
from openpresto.storage import dumps, loads, StorageError, to_dict


FIXTURE = Path(__file__).parent / 'reference04/aliases/baseline.bc3'
SAMPLE = FIXTURE.read_bytes().decode('cp1252')


class BC3AliasTests(unittest.TestCase):
    def test_native_synonym_difference_is_explicit_and_evidence_is_bound(self):
        root = Path(__file__).resolve().parents[1]
        observation = json.loads((root / 'docs/evidencias-04/ensayos/sinonimos-observados.json').read_text(encoding='utf-8'))
        self.assertEqual(observation['source'], 'native_ui_and_native_export')
        self.assertEqual(observation['presto_version'], '8.8')
        self.assertEqual(hashlib.sha256(FIXTURE.read_bytes()).hexdigest(), observation['fixture_sha256'])
        for shot in observation['screenshots']:
            self.assertEqual(hashlib.sha256((root / shot['path']).read_bytes()).hexdigest(), shot['sha256'])
        exported = observation['native_export']
        path = root / exported['path']
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), exported['sha256'])
        native = import_bc3(path)
        self.assertEqual(list(native.budget.concepts), exported['concept_codes'])
        self.assertEqual(native.record_counts.get('D', 0), exported['decomposition_records'])
        self.assertEqual(native.record_counts.get('M', 0), exported['measurement_records'])
        self.assertEqual(native.declared_prices, {code: Decimal(price) for code, price in exported['declared_prices'].items()})
        self.assertEqual(native.budget.concepts[exported['text_code']].text, exported['text'])
        documented = import_bc3(FIXTURE)
        self.assertNotEqual(set(documented.budget.concepts), set(native.budget.concepts))
        self.assertNotEqual(documented.budget.total(), native.budget.total())
        self.assertTrue(any('Sinónimos BC3' in warning for warning in documented.warnings))
        self.assertTrue(any('Sinónimos BC3' in warning for warning in render_bc3(documented.budget).warnings))
        with self.assertRaisesRegex(BC3ImportError, 'Sinónimos BC3'):
            import_bc3(FIXTURE, observed_presto88=True)

    def test_project_synonym_collision_rejected_without_restricting_plain_json_codes(self):
        from openpresto.budget import Budget, BudgetConcept
        budget = self.import_text(SAMPLE).budget
        document = to_dict(budget)
        document['concepts'].append({'code': 'ALT', 'unit': '', 'summary': '',
                                     'nature': '', 'base_price': '1', 'text': ''})
        with self.assertRaises(StorageError):
            loads(json.dumps(document))
        budget.add_concept(BudgetConcept('ALT'))
        with self.assertRaises(StorageError):
            dumps(budget)
        plain = Budget('R')
        plain.add_concept(BudgetConcept('R'))
        plain.add_concept(BudgetConcept('R#'))
        self.assertEqual(list(loads(dumps(plain)).concepts), ['R', 'R#'])

    def import_text(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'aliases.bc3'
            original = text.encode('cp1252')
            path.write_bytes(original)
            result = import_bc3(path)
            self.assertEqual(path.read_bytes(), original)
            return result

    def test_synonyms_resolve_structure_measurements_and_text_without_duplicates(self):
        manifest = json.loads(FIXTURE.with_name('manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(hashlib.sha256(FIXTURE.read_bytes()).hexdigest(), manifest['sha256'])
        self.assertTrue((FIXTURE.parents[3] / manifest['native_results']).is_file())
        result = self.import_text(SAMPLE)
        budget = result.budget
        self.assertEqual(list(budget.concepts), ['ROOT##', 'ITEM'])
        self.assertEqual(len(budget.relations), 1)
        relation = budget.relations[0]
        self.assertEqual((relation.parent_code, relation.child_code), ('ROOT##', 'ITEM'))
        self.assertEqual(budget.relation_quantity(relation.id), Decimal('2.00'))
        self.assertIn(relation.id, budget.bc3_measurements)
        self.assertEqual(budget.concepts['ITEM'].text, 'Texto propio con ñ')
        self.assertEqual(budget.total(), Decimal('7.5000'))
        restored = loads(dumps(budget))
        restored.concepts['ITEM'] = replace(restored.concepts['ITEM'], base_price=Decimal('5'))
        exported = render_bc3(restored).data.decode('cp1252')
        self.assertIn('~C|ITEM\\ALT|', exported)
        self.assertIn('~C|ROOT##\\OBRA##|', exported)
        again = self.import_text(exported).budget
        self.assertEqual(list(again.concepts), ['ROOT##', 'ITEM'])
        self.assertEqual(again.total(), Decimal('10.0000'))
        self.assertEqual(again.concepts['ITEM'].text, 'Texto propio con ñ')
        self.assertEqual(again.source_records[1][1].split('|')[0], 'ROOT##\\OBRA##')

    def test_collisions_empty_and_special_synonyms_are_rejected(self):
        for field in ('ITEM\\OBRA', 'ITEM\\ROOT##', 'ITEM\\\\ALT',
                      'ITEM\\ITEM', 'ITEM\\M%10'):
            with self.subTest(field=field), self.assertRaises(BC3ImportError):
                self.import_text(SAMPLE.replace('ITEM\\ALT\\', field))
        budget = self.import_text(SAMPLE).budget
        budget.source_records += (('C', 'OTHER\\ALT|m|Conflict|1||0|'),)
        from openpresto.budget import BudgetConcept
        budget.add_concept(BudgetConcept('OTHER', base_price='1'))
        with self.assertRaises(BC3ExportError):
            render_bc3(budget)
