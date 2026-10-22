"""Semantic identity of the separately encoded interoperability corpus."""
from pathlib import Path
from decimal import Decimal
import hashlib
import json
import unittest
from test_reference04 import CASES, snapshot
from openpresto.bc3_importer import import_bc3


class Presto88CorpusTests(unittest.TestCase):
    def test_observed_dimension_precision_differs_from_legacy_native(self):
        from openpresto.budget import BudgetMeasurement
        repo = Path(__file__).resolve().parents[1]
        directory = repo / 'docs/evidencias-04/ensayos'
        observed = json.loads((directory / 'longitud-redondeada-observada.json').read_text(encoding='utf-8'))
        self.assertEqual(observed['source'], 'presto_observation')
        for name, digest in observed['evidence'].items():
            self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(), digest)
        data = observed['input']
        legacy = BudgetMeasurement('r', n_lines=data['n'], length=data['length'],
                                   width=data['width'], height=data['height'])
        self.assertEqual(legacy.partial(), Decimal('2.010'))
        self.assertEqual(Decimal(observed['displayed']['partial']), Decimal('2.02'))
        self.assertNotEqual(legacy.partial(), Decimal(observed['displayed']['partial']))

    def test_observed_n_retains_digits_when_partial_rounds(self):
        repo = Path(__file__).resolve().parents[1]
        directory = repo / 'docs/evidencias-04/ensayos'
        observed = json.loads((directory / 'empates-parciales-observados.json').read_text(encoding='utf-8'))
        fixture = repo / 'tests/reference04/presto88/rounding.bc3'
        self.assertEqual(observed['source'], 'presto_observation')
        self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(), observed['fixture_sha256'])
        self.assertEqual(hashlib.sha256((directory / observed['evidence']).read_bytes()).hexdigest(), observed['evidence_sha256'])
        record = next(iter(import_bc3(fixture).budget.bc3_measurements.values()))
        for row in observed['rows']:
            line = record.lines[row['index']]
            self.assertEqual(line.description, row['comment'])
            self.assertEqual(Decimal(line.a), Decimal(row['displayed_n']))
            self.assertEqual(line.partial, Decimal(row['displayed_partial']))
        self.assertEqual(record.calculated_quantity, Decimal(observed['displayed_partial_total']))

    def test_independent_exports_keep_hashes_and_factor_fields(self):
        repo = Path(__file__).resolve().parents[1]
        directory = repo / 'docs/evidencias-04/ensayos'
        hashes = {
            'rounding-exportado-20261014.bc3': '56bca583ee8118c12c147161e1d0f5bae2d090862419585d5195705247552d48',
            'factor-exportado-20261014.bc3': 'e350f33da379c4d4e544443663faa6a05c7fc81c6e68c9474d4393eed4af8e67',
        }
        for name, digest in hashes.items():
            data = (directory / name).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), digest)
            self.assertEqual(data.count(b'\n'), data.count(b'\r\n'))
        factor = import_bc3(directory / 'factor-exportado-20261014.bc3')
        self.assertIn(('D', 'ROOT##|ITEM\\2\\2\\|'), factor.raw_records)
        self.assertEqual(factor.budget.concepts['ITEM'].text,
                         'Texto sintético: áéíóú, ñ y €; revisión 0.4.')
        rounding = import_bc3(directory / 'rounding-exportado-20261014.bc3')
        record = next(iter(rounding.budget.bc3_measurements.values()))
        self.assertEqual(record.declared_quantity, Decimal('2'))
        self.assertEqual(record.calculated_quantity, Decimal('2.01'))

    def test_observed_root_precision_explains_rounding_case(self):
        from openpresto.calculations import BudgetCalculator, CalculationPolicy
        repo = Path(__file__).resolve().parents[1]
        budget = import_bc3(repo / 'tests/reference04/presto88/rounding.bc3').budget
        directory = repo / 'docs/evidencias-04/ensayos'
        observation = json.loads((directory / 'precisiones-observadas-20261014.json').read_text(encoding='utf-8'))
        self.assertEqual(observation['source'], 'presto_observation')
        fixture = repo / 'tests/reference04/presto88/rounding.bc3'
        self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(), observation['fixture_sha256'])
        for evidence in observation['evidence']:
            self.assertTrue((directory / evidence).is_file())
        for case in observation['root_precision_experiment']:
            calculator = BudgetCalculator(budget, CalculationPolicy(root_quantity_decimals=case['decimals']))
            self.assertEqual(calculator.total(), Decimal(case['total']))
            self.assertEqual(calculator.quantity(budget.relations[0].id), Decimal(case['quantity']))
        self.assertEqual(next(iter(budget.bc3_measurements.values())).calculated_quantity, Decimal('2.01'))

    def test_independent_rounding_measurement_partials_match(self):
        repo = Path(__file__).resolve().parents[1]
        directory = repo / 'docs/evidencias-04/ensayos'
        observations = json.loads((directory / 'lineas-observadas-20261014.json').read_text(encoding='utf-8'))
        self.assertEqual(observations['source'], 'presto_observation')
        for name, case in observations['cases'].items():
            fixture = repo / 'tests/reference04/presto88' / (name + '.bc3')
            self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(), case['fixture_sha256'])
            self.assertTrue((directory / case['evidence']).is_file())
        case = observations['cases']['rounding']
        budget = import_bc3(repo / 'tests/reference04/presto88/rounding.bc3').budget
        self.assertEqual(len(budget.bc3_measurements), 1)
        record = next(iter(budget.bc3_measurements.values()))
        # Presto displays accumulated subtotal in its own column; compare
        # operative lines rather than equating presentation with domain data.
        indexes = [i for i, line in enumerate(record.lines) if line.kind in ('', '3')]
        self.assertEqual([record.lines[i].partial for i in indexes],
                         [Decimal(case['partials'][i]) for i in indexes])
        self.assertEqual(record.lines[4].partial, Decimal(case['accumulated_subtotal']))
        self.assertEqual(record.calculated_quantity, Decimal(case['partial_total']))

    def observation(self, name):
        repo = Path(__file__).resolve().parents[1]
        directory = repo / 'docs/evidencias-04/ensayos'
        observed = json.loads((directory / (name + '-observado.json')).read_text(encoding='utf-8'))
        fixture = repo / observed['fixture']
        self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(), observed['fixture_sha256'])
        self.assertEqual(observed['source'], 'presto_observation')
        for evidence in observed['evidence']:
            self.assertTrue((directory / evidence).is_file())
        return observed, snapshot(import_bc3(fixture).budget)

    def compare_observed(self, name):
        observed, actual = self.observation(name)
        for code, price in observed['observed_prices'].items():
            self.assertEqual(Decimal(actual['concepts'][code]['price']), Decimal(price))
        for relation in observed.get('observed_relations', []):
            candidates = [value for key, value in actual['relations'].items()
                          if json.loads(key)[0] == relation['parent']
                          and json.loads(key)[2] == relation['child']]
            self.assertEqual(len(candidates), 1)
            for field in ('quantity', 'unit_price', 'amount'):
                self.assertEqual(Decimal(candidates[0][field]), Decimal(relation[field]))

    def test_all_observations_have_valid_fixture_and_evidence(self):
        for name in CASES:
            with self.subTest(case=name):
                self.observation(name)

    def test_independent_reuse_prices_and_quantities(self):
        self.compare_observed('reuse')

    @unittest.expectedFailure
    def test_known_gap_dimensions(self):
        self.compare_observed('dimensions')

    @unittest.expectedFailure
    def test_known_gap_rounding(self):
        self.compare_observed('rounding')

    @unittest.expectedFailure
    def test_known_gap_factor(self):
        self.compare_observed('factor_text')

    def test_independent_simple_observed_prices(self):
        repo = Path(__file__).resolve().parents[1]
        evidence_dir = repo / 'docs/evidencias-04/ensayos'
        observed = json.loads((evidence_dir / 'simple-observado.json').read_text(encoding='utf-8'))
        fixture = repo / observed['fixture']
        self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(),
                         observed['fixture_sha256'])
        self.assertEqual(observed['source'], 'presto_observation')
        for evidence in observed['evidence']:
            self.assertTrue((evidence_dir / evidence).is_file())
        actual = snapshot(import_bc3(fixture).budget)
        for code, price in observed['observed_prices'].items():
            self.assertEqual(Decimal(actual['concepts'][code]['price']), Decimal(price))

    def test_ansi_crlf_variants_preserve_semantics(self):
        root = Path(__file__).parent / 'reference04'
        manifest = json.loads((root / 'presto88' / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(set(manifest), set(CASES))
        for name in CASES:
            with self.subTest(case=name):
                variant = root / 'presto88' / (name + '.bc3')
                data = variant.read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(),
                                 manifest[name]['fixture_sha256'])
                self.assertEqual(hashlib.sha256((root / (name + '.bc3')).read_bytes()).hexdigest(),
                                 manifest[name]['source_sha256'])
                self.assertEqual(data.count(b'\n'), data.count(b'\r\n'))
                self.assertIn(b'|ANSI|', data)
                self.assertEqual(snapshot(import_bc3(variant).budget),
                                 snapshot(import_bc3(root / (name + '.bc3')).budget))
