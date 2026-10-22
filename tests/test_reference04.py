"""Regressions for the existing profile; optional, independently observed oracle.

Synthetic harness checks are never evidence of Presto equivalence.
"""
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import unittest

from openpresto.bc3_importer import import_bc3
from openpresto.calculations import BudgetCalculator
from openpresto.storage import dumps, loads

FIXTURES = Path(__file__).parent / 'reference04'
CASES = ('simple', 'reuse', 'dimensions', 'rounding', 'factor_text')
PROFILE = {
    'quantity_decimals': 3, 'price_decimals': 2, 'amount_decimals': 2,
    'rounding': 'ROUND_HALF_UP', 'measurement_decimals': 2,
    'formula_scope': 'per_line',
}


def snapshot(budget):
    """Stable identities across imports: concept code and parent/position/child."""
    calculator = BudgetCalculator(budget)
    relations = {}
    for relation in budget.relations:
        key = json.dumps([relation.parent_code, relation.position, relation.child_code],
                         ensure_ascii=False, separators=(',', ':'))
        amount = calculator.relation(relation.id)
        record = budget.bc3_measurements.get(relation.id)
        relations[key] = {
            'quantity': str(budget.relation_quantity(relation.id)),
            'rounded_quantity': str(amount.quantity),
            'unit_price': str(amount.unit_price), 'amount': str(amount.amount),
            'lines': [] if record is None else [
                {'kind': row.kind, 'partial': None if row.partial is None else str(row.partial)}
                for row in record.lines],
        }
    return {
        'total': str(calculator.total()),
        'concepts': {code: {'price': str(calculator.price(code)), 'text': concept.text}
                     for code, concept in budget.concepts.items()},
        'relations': relations,
    }


def validate_observation(document, base):
    """Require provenance, exact fixture binding and complete expected snapshot.

    Validation verifies structure and local evidence existence, not authenticity.
    """
    if (not isinstance(document, dict)
            or type(document.get('schema_version')) is not int
            or document['schema_version'] != 1):
        raise ValueError('schema_version must be 1')
    if document.get('source') != 'presto_observation':
        raise ValueError('source must identify an independent Presto observation')
    for name in ('presto_version', 'observed_at', 'operator'):
        if not isinstance(document.get(name), str) or not document[name].strip():
            raise ValueError('Missing provenance: ' + name)
    if document.get('profile') != PROFILE:
        raise ValueError('Observation profile differs from the tested OpenPresto profile')
    cases = document.get('cases')
    if not isinstance(cases, dict) or not cases or set(cases) - set(CASES):
        raise ValueError('cases must be a nonempty subset of the known fixtures')
    for name, case in cases.items():
        if not isinstance(case, dict):
            raise ValueError('Invalid case: ' + name)
        expected_hash = hashlib.sha256((FIXTURES / (name + '.bc3')).read_bytes()).hexdigest()
        if case.get('fixture_sha256') != expected_hash:
            raise ValueError('Fixture hash mismatch: ' + name)
        evidence = case.get('evidence')
        if not isinstance(evidence, list) or not evidence:
            raise ValueError('Evidence required: ' + name)
        for path in evidence:
            if not isinstance(path, str) or not path.strip() or not (base / path).is_file():
                raise ValueError('Evidence file unavailable: ' + str(path))
        expected = case.get('expected')
        template = snapshot(import_bc3(FIXTURES / (name + '.bc3')).budget)
        _validate_snapshot(expected, template)
    return cases


def _validate_snapshot(value, template, label='expected'):
    if isinstance(template, dict):
        if not isinstance(value, dict) or set(value) != set(template):
            raise ValueError('Missing/extra snapshot fields: ' + label)
        for key in template:
            _validate_snapshot(value[key], template[key], label + '.' + key)
    elif isinstance(template, list):
        if not isinstance(value, list) or len(value) != len(template):
            raise ValueError('Incorrect line count: ' + label)
        for index, item in enumerate(template):
            _validate_snapshot(value[index], item, label + '.' + str(index))
    elif label.endswith(('.text', '.kind')):
        if not isinstance(value, str):
            raise ValueError('Text required: ' + label)
    else:
        try:
            if not isinstance(value, str) or not Decimal(value).is_finite():
                raise ValueError('Finite decimal string required: ' + label)
        except InvalidOperation as exc:
            raise ValueError('Invalid decimal: ' + label) from exc


def normalized(value, label='expected'):
    if isinstance(value, dict):
        return {key: normalized(item, label + '.' + key) for key, item in value.items()}
    if isinstance(value, list):
        return [normalized(item, label + '.' + str(i)) for i, item in enumerate(value)]
    if label.endswith(('.text', '.kind')) or value is None:
        return value
    return Decimal(value)


class Reference04RegressionTests(unittest.TestCase):
    def load(self, name):
        return import_bc3(FIXTURES / (name + '.bc3')).budget

    def test_simple_price_and_quantity(self):
        budget = self.load('simple')
        self.assertEqual(BudgetCalculator(budget).total(), Decimal('25.00'))
        self.assertEqual(budget.relation_quantity(budget.relations[0].id), Decimal('2'))

    def test_hierarchy_and_reuse(self):
        budget = self.load('reuse')
        self.assertEqual(BudgetCalculator(budget).total(), Decimal('21.00'))
        self.assertEqual([r.quantity for r in budget.relations if r.child_code == 'ITEM'],
                         [Decimal('2'), Decimal('5')])

    def test_missing_zero_negative_dimensions(self):
        budget = self.load('dimensions')
        record = next(iter(budget.bc3_measurements.values()))
        self.assertEqual([row.partial for row in record.lines],
                         list(map(Decimal, ['6', '0', '-2', '0'])))
        self.assertEqual(BudgetCalculator(budget).total(), Decimal('40.00'))

    def test_rounding_subtotals_formula(self):
        budget = self.load('rounding')
        record = next(iter(budget.bc3_measurements.values()))
        self.assertEqual([row.partial for row in record.lines],
                         list(map(Decimal, ['0.01', '-0.01', '0', '2', '2', '0.01'])))
        self.assertEqual(BudgetCalculator(budget).total(), Decimal('4.02'))

    def test_factor_and_unicode_text(self):
        budget = self.load('factor_text')
        self.assertEqual(budget.relations[0].quantity, Decimal('3'))
        self.assertEqual(BudgetCalculator(budget).total(), Decimal('12.75'))
        self.assertEqual(budget.concepts['ITEM'].text,
                         'Texto sintético: áéíóú, ñ y €; revisión 0.4.')

    def test_all_fixtures_persist_without_mutating_originals(self):
        for name in CASES:
            with self.subTest(case=name):
                path = FIXTURES / (name + '.bc3')
                before = path.read_bytes()
                budget = self.load(name)
                self.assertEqual(snapshot(loads(dumps(budget))), snapshot(budget))
                self.assertEqual(path.read_bytes(), before)


class Reference04HarnessTests(unittest.TestCase):
    """Synthetic self-checks of the harness; no observed Presto results."""
    def document(self):
        path = FIXTURES / 'simple.bc3'
        return {'schema_version': 1, 'source': 'presto_observation',
                'presto_version': 'SYNTHETIC HARNESS SELF-CHECK',
                'observed_at': 'not a real observation', 'operator': 'unit test',
                'profile': dict(PROFILE), 'cases': {'simple': {
                    'fixture_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                    'evidence': ['simple.bc3'],
                    'expected': snapshot(import_bc3(path).budget)}}}

    def test_valid_synthetic_structure_and_decimal_normalization(self):
        document = self.document()
        document['cases']['simple']['expected']['total'] = '25.0000'
        cases = validate_observation(document, FIXTURES)
        self.assertEqual(normalized(cases['simple']['expected']),
                         normalized(snapshot(import_bc3(FIXTURES / 'simple.bc3').budget)))

    def test_rejects_missing_provenance_hash_evidence_profile_and_snapshot(self):
        changes = [lambda d: d.pop('presto_version'),
                   lambda d: d.update(schema_version=2),
                   lambda d: d.update(schema_version=True),
                   lambda d: d.update(profile={}),
                   lambda d: d['cases']['simple'].update(fixture_sha256='wrong'),
                   lambda d: d['cases']['simple'].update(evidence=[]),
                   lambda d: d['cases']['simple'].update(evidence=['missing.png']),
                   lambda d: d['cases']['simple']['expected'].update(total='NaN'),
                   lambda d: d['cases']['simple']['expected'].pop('relations')]
        for index, change in enumerate(changes):
            with self.subTest(check=index):
                document = self.document()
                change(document)
                with self.assertRaises(ValueError):
                    validate_observation(document, FIXTURES)

    def test_changed_observation_is_detected(self):
        expected = self.document()['cases']['simple']['expected']
        actual = snapshot(import_bc3(FIXTURES / 'simple.bc3').budget)
        expected['total'] = '25.01'
        self.assertNotEqual(normalized(expected), normalized(actual))


class Presto04ComparisonTests(unittest.TestCase):
    def test_independent_presto_observations(self):
        source = os.environ.get('OPENPRESTO_REFERENCE04')
        if not source:
            self.skipTest('No Presto observations: set OPENPRESTO_REFERENCE04 to external JSON')
        path = Path(source)
        document = json.loads(path.read_text(encoding='utf-8'))
        cases = validate_observation(document, path.parent)
        for name in CASES:
            with self.subTest(case=name):
                if name not in cases:
                    self.skipTest('No independent Presto observation for ' + name)
                actual = snapshot(import_bc3(FIXTURES / (name + '.bc3')).budget)
                self.assertEqual(normalized(cases[name]['expected']), normalized(actual))


if __name__ == '__main__':
    unittest.main()
