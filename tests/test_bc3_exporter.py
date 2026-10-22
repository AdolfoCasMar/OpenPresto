from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import hashlib
import json
import tempfile
import unittest

from openpresto.bc3_importer import import_bc3
from openpresto.bc3_exporter import render_bc3, save_bc3, BC3ExportError
from openpresto.calculations import BudgetCalculator
from openpresto.storage import dumps


class ExportTests(unittest.TestCase):
    def test_percentage_export_matches_independently_recalculated_presto_fixture(self):
        from openpresto.storage import load_budget
        from openpresto.calculations import calculator_for
        from openpresto.percentage_calculations import set_percentage_rate
        repo = Path(__file__).resolve().parents[1]
        directory = repo / 'docs/evidencias-04/ensayos'
        observation = json.loads((directory / 'porcentajes-exportados-observados.json').read_text(encoding='utf-8'))
        fixture = repo / observation['fixture']
        self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(), observation['fixture_sha256'])
        for name, digest in observation['evidence_sha256'].items():
            self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(), digest)
        budget = load_budget(repo / observation['generated_from'])
        set_percentage_rate(budget, observation['edit']['code'], observation['edit']['rate'])
        before = dumps(budget)
        rendered = render_bc3(budget)
        self.assertEqual(rendered.data, fixture.read_bytes())
        self.assertEqual(dumps(budget), before)
        restored = import_bc3(fixture, observed_presto88=True).budget
        restored.percentage_profile = 'presto88_bc3'
        calculator = calculator_for(restored)
        for code, value in observation['observed_prices'].items():
            actual_code = next(c for c in restored.concepts if c.rstrip('#') == code)
            self.assertEqual(calculator.price(actual_code), Decimal(value))
        for expected in observation['percentage_rows']:
            relation = next(r for r in restored.relations
                            if r.parent_code == expected['parent'] and r.child_code == expected['code'])
            actual = calculator.relation(relation.id)
            self.assertEqual(actual.quantity, Decimal(expected['quantity']))
            self.assertEqual(actual.unit_price, Decimal(expected['price']))
            self.assertEqual(actual.amount, Decimal(expected['amount']))
            self.assertEqual(relation.quantity, actual.unit_price / 100)
        self.assertNotIn(b'~M|PCTD\\M%FIRST', rendered.data)
        self.assertNotIn(b'~M|PCTD\\M%SECOND', rendered.data)

    def test_percentage_export_requires_explicit_profile_and_contrasted_rate_precision(self):
        from openpresto.storage import load_budget
        repo = Path(__file__).resolve().parents[1]
        budget = load_budget(repo / 'openpresto/data/porcentajes-demo.openpresto.json')
        budget.percentage_profile = None
        with self.assertRaises(BC3ExportError):
            render_bc3(budget)
        budget.percentage_profile = 'presto88_bc3'
        original = next(r for r in budget.relations if r.child_code == 'M%FIRST')
        for quantity in ('-.1', '.12345'):
            changed = replace(original, quantity=Decimal(quantity))
            budget.relations[budget.relations.index(budget._relation(original.id))] = changed
            budget._relations_by_id[original.id] = changed
            with self.subTest(quantity=quantity), self.assertRaises(BC3ExportError):
                render_bc3(budget)

    def test_edited_export_matches_independent_presto_observation(self):
        repo = Path(__file__).resolve().parents[1]
        directory = repo / 'docs/evidencias-04/ensayos'
        observation = json.loads((directory / 'exportacion-editada-observada.json').read_text(encoding='utf-8'))
        fixture = repo / observation['fixture']
        self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(), observation['fixture_sha256'])
        self.assertEqual(observation['source'], 'presto_observation')
        self.assertTrue((directory / observation['evidence']).is_file())
        budget = import_bc3(repo / 'tests/reference04/presto88/simple.bc3', observed_presto88=True).budget
        budget.concepts['ITEM'] = replace(budget.concepts['ITEM'], base_price='7.50', text='Ensayo de exportacion propia 0.4')
        self.assertEqual(render_bc3(budget).data, fixture.read_bytes())
        calculator = BudgetCalculator(budget)
        for code, price in observation['observed_prices'].items():
            self.assertEqual(calculator.price(code), Decimal(price))
        result = calculator.relation(budget.relations[0].id)
        self.assertEqual(result.quantity, Decimal(observation['observed_quantity']))
        self.assertEqual(result.amount, Decimal(observation['observed_amount']))

    def test_optional_profile_roundtrip_five_cases(self):
        fixtures = Path(__file__).parent / 'reference04/presto88'
        with tempfile.TemporaryDirectory() as temporary:
            for name in ('simple', 'reuse', 'dimensions', 'rounding', 'factor_text'):
                with self.subTest(case=name):
                    source = fixtures / (name + '.bc3')
                    original = source.read_bytes()
                    budget = import_bc3(source, observed_presto88=True).budget
                    previous = dumps(budget)
                    target = Path(temporary) / (name + '.bc3')
                    result = save_bc3(budget, target)
                    self.assertTrue(result.warnings)
                    restored = import_bc3(target, observed_presto88=True).budget
                    self.assertEqual(BudgetCalculator(restored).total(), BudgetCalculator(budget).total())
                    self.assertEqual(dumps(budget), previous)
                    self.assertEqual(source.read_bytes(), original)
                    self.assertEqual(result.data.count(b'\n'), result.data.count(b'\r\n'))

    def test_export_uses_edited_prices_and_text_instead_of_original_records(self):
        source = Path(__file__).parent / 'reference04/presto88/simple.bc3'
        budget = import_bc3(source, observed_presto88=True).budget
        budget.concepts['ITEM'] = replace(budget.concepts['ITEM'], base_price='7.50', text='Texto nuevo')
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'edited.bc3'
            save_bc3(budget, target)
            restored = import_bc3(target, observed_presto88=True).budget
            self.assertEqual(BudgetCalculator(restored).total(), Decimal('15.00'))
            self.assertEqual(restored.concepts['ITEM'].text, 'Texto nuevo')

    def test_existing_file_is_protected_and_no_temporary_left(self):
        budget = import_bc3(Path(__file__).parent / 'reference04/presto88/simple.bc3').budget
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'source.bc3'
            target.write_bytes(b'original')
            with self.assertRaises(BC3ExportError):
                save_bc3(budget, target)
            self.assertEqual(target.read_bytes(), b'original')
            self.assertEqual(list(Path(temporary).iterdir()), [target])

    def test_unknown_records_and_unrepresentable_text_rejected(self):
        budget = import_bc3(Path(__file__).parent / 'reference04/presto88/simple.bc3').budget
        budget.source_records += (('G', 'ITEM|imagen.png|'),)
        with self.assertRaises(BC3ExportError):
            render_bc3(budget)
        budget.source_records = ()
        for text in ('texto|separador', 'texto~registro', '漢字'):
            budget.concepts['ITEM'] = replace(budget.concepts['ITEM'], text=text)
            with self.subTest(text=text), self.assertRaises(BC3ExportError):
                render_bc3(budget)
