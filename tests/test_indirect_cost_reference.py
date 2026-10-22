"""Independent baseline for indirect-cost trials; no indirect engine claimed."""
from decimal import Decimal
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import unittest
import copy
import tempfile

from openpresto.bc3_importer import import_bc3
from openpresto.calculations import calculator_for
from openpresto.budget import BudgetError
from openpresto.indirect_costs import Presto88IndirectCalculator
from openpresto.storage import dumps, loads, to_dict, from_dict, save_budget, load_budget, StorageError


ROOT = Path(__file__).resolve().parents[1]


class IndirectCostReferenceTests(unittest.TestCase):
    def test_indirect_import_rejects_unobserved_coefficients_and_precisions(self):
        from openpresto.bc3_importer import BC3ImportError
        raw = (ROOT / 'docs/evidencias-04/ensayos/'
               'indirectos-generados-exportador-pendiente.bc3').read_bytes()
        record = b'~K|\\2\\2\\3\\2\\2\\2\\2\\EUR\\|5.00|'
        self.assertIn(record, raw)
        variants = [record.replace(b'5.00', b'5\\13'), record.replace(b'5.00', b'-5'),
                    record.replace(b'5.00', b'5.001'), record.replace(b'EUR', b'USD'),
                    record.replace(b'\\3\\', b'\\4\\'), record + b'\r\n' + record]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'unsupported.bc3'
            for variant in variants:
                path.write_bytes(raw.replace(record, variant))
                with self.subTest(variant=variant), self.assertRaises(BC3ImportError):
                    import_bc3(path, observed_presto88=True)

    def test_generated_indirect_bc3_roundtrip_with_explicit_profile(self):
        from openpresto.bc3_exporter import render_bc3
        original = load_budget(ROOT / 'openpresto/data/indirectos-demo.openpresto.json')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'roundtrip.bc3'
            exported = render_bc3(original).data
            path.write_bytes(exported)
            restored = import_bc3(path, observed_presto88=True).budget
        self.assertEqual(restored.total(), Decimal('390.22'))
        self.assertEqual(loads(dumps(restored)).total(), original.total())
        self.assertFalse(restored.indirect_config['exclude_undecomposed'])
        self.assertEqual(render_bc3(restored).data, exported)

    def test_generated_bytes_and_native_observations_remain_linked(self):
        from openpresto.bc3_exporter import render_indirect_trial
        from openpresto.storage import load_budget
        observation = json.loads((ROOT / 'docs/evidencias-04/ensayos/'
                                  'indirectos-generador-observado.json').read_text(encoding='utf-8'))
        budget = load_budget(ROOT / 'openpresto/data/indirectos-demo.openpresto.json')
        before = dumps(budget)
        generated = render_indirect_trial(budget).data
        self.assertEqual(generated, (ROOT / observation['input']).read_bytes())
        self.assertEqual(hashlib.sha256(generated).hexdigest(), observation['sha256'])
        for screenshot in observation['screenshots']:
            self.assertEqual(hashlib.sha256((ROOT / screenshot['path']).read_bytes()).hexdigest(),
                             screenshot['sha256'])
        expected = observation['observed']
        calculator = calculator_for(budget)
        self.assertEqual(calculator.total(), Decimal(expected['root']))
        for chapter in ('CIA', 'CIB'):
            self.assertEqual(calculator.price(chapter + '#'), Decimal(expected[chapter]))
        for child in ('CID', 'CIS'):
            relation = next(r for r in budget.relations
                            if r.parent_code == 'CIA#' and r.child_code == child)
            row = calculator.relation(relation.id)
            self.assertEqual(row.quantity, Decimal(expected['CIA_' + child + '_quantity']))
            self.assertEqual(row.unit_price, Decimal(expected[child + '_direct_price']))
            self.assertEqual(row.amount, Decimal(expected['CIA_' + child + '_amount']))
        self.assertEqual(dumps(budget), before)

    def test_experimental_export_preserves_direct_prices_and_fractional_inputs(self):
        from openpresto.bc3_exporter import render_indirect_trial, render_bc3, BC3ExportError
        _, budget = self.load()
        budget.indirect_config = {'profile': 'presto88_default', 'chapter_codes': ['CIA#', 'CIB#'],
                                  'rate': '5', 'exclude_undecomposed': False}
        before = dumps(budget)
        result = render_indirect_trial(budget)
        rows = result.data.decode('cp1252').splitlines()
        self.assertIn('~K|\\2\\2\\3\\2\\2\\2\\2\\EUR\\|5|', rows)
        prices = {r.split('|')[1]: Decimal(r.split('|')[4]) for r in rows if r.startswith('~C|')}
        self.assertEqual(prices['CIROOT##'], Decimal('390.22'))
        self.assertEqual(prices['CID'], Decimal('70.05'))
        self.assertFalse(any(r.startswith('~M|') for r in rows))
        self.assertEqual(dumps(budget), before)
        self.assertEqual(render_bc3(budget).data, result.data)
        budget.indirect_config['exclude_undecomposed'] = True
        with self.assertRaises(BC3ExportError):
            render_indirect_trial(budget)

    def test_native_reimport_default_configuration_matches_explicit_view(self):
        observation = json.loads((ROOT / 'docs/evidencias-04/ensayos/'
                                  'indirectos-reimportacion-observada.json').read_text(encoding='utf-8'))
        self.assertEqual(hashlib.sha256((ROOT / observation['input']).read_bytes()).hexdigest(),
                         observation['sha256'])
        for screenshot in observation['screenshots']:
            self.assertEqual(hashlib.sha256((ROOT / screenshot['path']).read_bytes()).hexdigest(),
                             screenshot['sha256'])
        _, budget = self.load()
        relation = next(r for r in budget.relations if r.child_code == 'R01')
        updated = replace(relation, quantity=Decimal('0.333'))
        budget.relations[budget.relations.index(relation)] = updated
        budget._relations_by_id[relation.id] = updated
        expected = observation['after']
        calculator = Presto88IndirectCalculator(budget, chapter_codes={'CIA#', 'CIB#'},
            rate=Decimal(expected['rate']), exclude_undecomposed=expected['exclude_simple'])
        self.assertEqual(calculator.total(), Decimal(expected['root']))
        self.assertEqual(calculator.direct_total(), Decimal(expected['direct_budget_cost']))
        for chapter in ('CIA', 'CIB'):
            self.assertEqual(calculator.price(chapter + '#'), Decimal(expected[chapter]))
        for child in ('CID', 'CIS'):
            row = next(r for r in budget.relations if r.parent_code == 'CIA#' and r.child_code == child)
            amount = calculator.relation(row.id)
            native = expected['CIA_' + child]
            self.assertEqual(amount.quantity, Decimal(native['quantity']))
            self.assertEqual(amount.unit_price, Decimal(native['direct_price']))
            self.assertEqual(amount.amount, Decimal(native['amount']))

    def test_native_export_with_unapplied_economic_configuration_is_rejected(self):
        from openpresto.bc3_importer import BC3ImportError
        path = ROOT / 'docs/evidencias-04/ensayos/indirectos-exportado-presto88-20261015.bc3'
        for profile in (False, True):
            with self.subTest(profile=profile), self.assertRaisesRegex(BC3ImportError, '~K'):
                import_bc3(path, observed_presto88=profile)

    def test_persistent_profile_roundtrip_and_export_guard(self):
        from openpresto.bc3_exporter import render_bc3, BC3ExportError
        _, budget = self.load()
        base = to_dict(budget)
        budget.indirect_config = {'profile': 'presto88_default',
            'chapter_codes': ['CIA#', 'CIB#'], 'rate': '5.00', 'exclude_undecomposed': False}
        document = to_dict(budget)
        self.assertEqual(document['version'], 12)
        self.assertEqual(document['project'], base)
        self.assertEqual(budget.total(), Decimal('390.22'))
        self.assertEqual(calculator_for(budget).total(), budget.total())
        relation = next(r for r in budget.relations if r.parent_code == 'CIA#' and r.child_code == 'CID')
        self.assertEqual(budget.relation_amount(relation.id), Decimal('147.10'))
        self.assertEqual(budget.concept_price('CID'), Decimal('70.05'))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'project.json'
            save_budget(budget, path)
            restored = load_budget(path)
            self.assertEqual(to_dict(restored), document)
            self.assertEqual(restored.total(), Decimal('390.22'))
        restored.indirect_config['exclude_undecomposed'] = True
        self.assertEqual(loads(dumps(restored)).total(), Decimal('389.14'))
        self.assertEqual(budget.total(), Decimal('390.22'))
        self.assertEqual(render_bc3(budget).data[:3], b'~V|')
        for field, value in [('profile', 'unknown'), ('rate', 'NaN'),
                             ('chapter_codes', ['CIA#', 'CIA#']), ('exclude_undecomposed', 1)]:
            invalid = copy.deepcopy(document)
            invalid['indirect_costs'][field] = value
            with self.subTest(field=field), self.assertRaises(StorageError):
                from_dict(invalid)
        invalid = copy.deepcopy(document)
        invalid['project'] = document
        with self.assertRaises(StorageError):
            from_dict(invalid)
        document['indirect_costs']['rate'] = '10'
        self.assertEqual(budget.indirect_config['rate'], '5.00')

    def load(self):
        observation = json.loads((ROOT / 'docs/evidencias-04/ensayos/'
                                  'indirectos-observados.json').read_text(encoding='utf-8'))
        budget = import_bc3(ROOT / observation['input_fixture'], observed_presto88=True).budget
        return observation, budget

    def test_indirect_view_matches_both_native_rate5_configurations(self):
        observation, budget = self.load()
        before = dumps(budget)
        codes = {'CIROOT': 'CIROOT##', 'CIA': 'CIA#', 'CIB': 'CIB#'}
        for name in ('rate5', 'rate5_exclude_undecomposed'):
            case = observation[name]
            calculator = Presto88IndirectCalculator(
                budget, chapter_codes={'CIA#', 'CIB#'}, rate=Decimal(case['rate']),
                exclude_undecomposed=case['exclude_undecomposed'])
            self.assertEqual(calculator.total(), Decimal(case['root']))
            self.assertEqual(calculator.direct_total(), Decimal('371.64'))
            for code, price in case['chapters'].items():
                self.assertEqual(calculator.price(codes[code]), Decimal(price))
            for expected in case['rows']:
                relation = next(r for r in budget.relations
                                if r.parent_code == codes.get(expected['parent'], expected['parent'])
                                and r.child_code == expected['child'])
                row = calculator.relation(relation.id)
                self.assertEqual(row.quantity, Decimal(expected['quantity']))
                self.assertEqual(row.unit_price, Decimal(expected['price']))
                self.assertEqual(row.amount, Decimal(expected['amount']))
            for expected in observation['baseline']['rows'][2:]:
                relation = next(r for r in budget.relations if r.parent_code == expected['parent']
                                and r.child_code == expected['child'])
                self.assertEqual(calculator.relation(relation.id).amount, Decimal(expected['amount']))
        self.assertEqual(dumps(budget), before)
        self.assertEqual(calculator_for(budget).total(), Decimal('371.64'))

    def test_fractional_resource_matches_native_default_rounding(self):
        observation, budget = self.load()
        old = next(r for r in budget.relations if r.child_code == 'R01')
        updated = replace(old, quantity=Decimal('0.333'))
        budget.relations[budget.relations.index(old)] = updated
        budget._relations_by_id[old.id] = updated
        calculator = Presto88IndirectCalculator(budget, chapter_codes={'CIA#', 'CIB#'},
                                              rate=Decimal('5'), exclude_undecomposed=True)
        expected = observation['fractional_resource_trial']['before_option_change']
        relation = next(r for r in budget.relations if r.parent_code == 'CIA#' and r.child_code == 'CID')
        self.assertEqual(calculator.price('CID'), Decimal(expected['displayed_direct_price']))
        self.assertEqual(calculator.relation(relation.id).amount,
                         Decimal(expected['displayed_CIA_CID_amount']))
        self.assertEqual(calculator.direct_total(), Decimal(expected['direct_budget_cost']))

    def test_unobserved_combinations_rejected(self):
        _, budget = self.load()
        for rate in (Decimal('NaN'), Decimal('Infinity'), Decimal('-5'), Decimal('5.001'), 5):
            with self.subTest(rate=rate), self.assertRaises(BudgetError):
                Presto88IndirectCalculator(budget, chapter_codes={'CIA#', 'CIB#'}, rate=rate)
        with self.assertRaises(BudgetError):
            Presto88IndirectCalculator(budget, chapter_codes={'CIA#'}, rate=Decimal('5'))
        budget.percentage_profile = 'presto88_bc3'
        with self.assertRaises(BudgetError):
            Presto88IndirectCalculator(budget, chapter_codes={'CIA#', 'CIB#'}, rate=Decimal('5'))

    def test_native_baseline_prices_and_observed_rows(self):
        observation = json.loads((ROOT / 'docs/evidencias-04/ensayos/'
                                  'indirectos-observados.json').read_text(encoding='utf-8'))
        fixture = ROOT / observation['input_fixture']
        self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(),
                         observation['input_fixture_sha256'])
        for screenshot in observation['screenshots']:
            self.assertEqual(hashlib.sha256((ROOT / screenshot['path']).read_bytes()).hexdigest(),
                             screenshot['sha256'])
        budget = import_bc3(fixture, observed_presto88=True).budget
        before = dumps(budget)
        calculator = calculator_for(budget)
        # Presto displays chapter codes without the BC3 ~C suffix. The importer
        # deliberately preserves literal declared codes; do not change the fixture.
        native_to_bc3 = {'CIROOT': 'CIROOT##', 'CIA': 'CIA#', 'CIB': 'CIB#'}
        for code, price in observation['baseline']['prices'].items():
            with self.subTest(code=code):
                self.assertEqual(calculator.price(native_to_bc3.get(code, code)), Decimal(price))
        for expected in observation['baseline']['rows']:
            relation = next(r for r in budget.relations
                            if r.parent_code == native_to_bc3.get(expected['parent'], expected['parent'])
                            and r.child_code == native_to_bc3.get(expected['child'], expected['child']))
            actual = calculator.relation(relation.id)
            with self.subTest(parent=relation.parent_code, child=relation.child_code):
                self.assertEqual(actual.quantity, Decimal(expected['quantity']))
                self.assertEqual(actual.unit_price, Decimal(expected['price']))
                self.assertEqual(actual.amount, Decimal(expected['amount']))
        self.assertEqual(dumps(budget), before)


if __name__ == '__main__':
    unittest.main()
