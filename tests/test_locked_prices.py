from dataclasses import replace
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import unittest

from openpresto.bc3_importer import import_bc3
from openpresto.locked_prices import LockedPriceCalculator
from openpresto.storage import dumps
from openpresto.storage import loads, to_dict, from_dict, StorageError, save_budget, load_budget
import copy
import tempfile
from openpresto.calculations import calculator_for

ROOT = Path(__file__).resolve().parents[1]


class LockedPriceTests(unittest.TestCase):
    def test_own_export_matches_received_and_recalculated_native_values(self):
        from openpresto.bc3_exporter import render_bc3
        observed = json.loads((ROOT / 'docs/evidencias-04/ensayos/bloqueo-propio-observado.json').read_text(encoding='utf-8'))
        fixture = ROOT / observed['fixture']
        self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(), observed['fixture_sha256'])
        for shot in observed['screenshots']:
            self.assertEqual(hashlib.sha256((ROOT / shot['path']).read_bytes()).hexdigest(), shot['sha256'])
        imported = import_bc3(fixture, observed_presto88=True)
        received = observed['received']
        for code, key in (('OVROOT##', 'root'), ('OVA#', 'OVA'), ('OVB#', 'OVB'), ('OVITEM', 'OVITEM')):
            self.assertEqual(imported.declared_prices[code], Decimal(received[key]))
        calc = calculator_for(imported.budget)
        expected = observed['recalculated']
        self.assertEqual(calc.total(), Decimal(expected['root']))
        for code in ('OVA', 'OVB', 'OVITEM'):
            self.assertEqual(calc.price(code + '#' if code != 'OVITEM' else code), Decimal(expected[code]))
        for occurrence in expected['occurrences']:
            relation = next(r for r in imported.budget.relations if r.parent_code == occurrence['parent'] + '#' and r.child_code == 'OVITEM')
            values = calc.relation(relation.id)
            self.assertEqual(values.quantity, Decimal(occurrence['quantity']))
            self.assertEqual(values.amount, Decimal(occurrence['amount']))
        original = import_bc3(ROOT / 'tests/reference04/price_override/baseline.bc3', observed_presto88=True).budget
        original.concepts['OVR1'] = replace(original.concepts['OVR1'], base_price=Decimal('5'))
        original.locked_prices = {'OVITEM': Decimal('20')}
        before = dumps(original)
        exported = render_bc3(original)
        self.assertEqual(exported.data, fixture.read_bytes())
        self.assertEqual(dumps(original), before)
        self.assertTrue(any('JSON' in warning for warning in exported.warnings))

    def test_received_prices_are_not_automatically_real_locks(self):
        observed = json.loads((ROOT / 'docs/evidencias-04/ensayos/bloqueo-sin-recalcular-observado.json').read_text(encoding='utf-8'))
        fixture = ROOT / observed['fixture']
        self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(), observed['fixture_sha256'])
        for shot in observed['screenshots']:
            self.assertEqual(hashlib.sha256((ROOT / shot['path']).read_bytes()).hexdigest(), shot['sha256'])
        result = import_bc3(fixture, observed_presto88=True)
        received = observed['received']
        self.assertEqual(result.declared_prices['OVROOT##'], Decimal(received['root']))
        self.assertEqual(result.declared_prices['OVITEM'], Decimal(received['OVITEM']))
        self.assertNotEqual(calculator_for(result.budget).total(), Decimal(received['root']))
        self.assertEqual(result.budget.locked_prices, {})
        edit = observed['resource_edit']
        result.budget.concepts[edit['code']] = replace(result.budget.concepts[edit['code']], base_price=Decimal(edit['new_price']))
        calc = calculator_for(result.budget)
        self.assertEqual(calc.total(), Decimal(edit['root']))
        self.assertEqual(calc.price('OVITEM'), Decimal(edit['OVITEM']))
        for code in ('OVA', 'OVB'):
            self.assertEqual(calc.price(code + '#'), Decimal(edit[code]))

    def test_locked_price_export_trial_keeps_manual_prices_and_decomposition(self):
        from openpresto.bc3_exporter import render_locked_price_trial, render_bc3, BC3ExportError
        budget = import_bc3(ROOT / 'tests/reference04/price_override/baseline.bc3', observed_presto88=True).budget
        budget.concepts['OVR1'] = replace(budget.concepts['OVR1'], base_price=Decimal('5'))
        budget.locked_prices = {'OVITEM': Decimal('20')}
        before = dumps(budget)
        trial = render_locked_price_trial(budget)
        self.assertEqual(trial.data, (ROOT / 'docs/evidencias-04/ensayos/bloqueo-generado-openpresto-pendiente.bc3').read_bytes())
        self.assertEqual(dumps(budget), before)
        self.assertEqual(render_bc3(budget), trial)
        native = import_bc3(ROOT / 'docs/evidencias-04/ensayos/bloqueo-exportado-presto88-20261016.bc3', observed_presto88=True)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'trial.bc3'
            path.write_bytes(trial.data)
            imported = import_bc3(path, observed_presto88=True)
        self.assertEqual(imported.declared_prices, native.declared_prices)
        def relations(project):
            return sorted((r.parent_code, r.child_code, r.quantity, r.factor, r.position) for r in project.relations)
        self.assertEqual(relations(imported.budget), relations(native.budget))
        self.assertEqual(calculator_for(imported.budget).total(), Decimal('98.00'))
        self.assertEqual(imported.budget.locked_prices, {})
        self.assertTrue(any('JSON' in warning for warning in trial.warnings))
        budget.root_quantity_decimals = 3
        with self.assertRaises(BC3ExportError):
            render_locked_price_trial(budget)

    def test_native_lock_persistence_and_bc3_recalculation_are_distinct(self):
        path = ROOT / 'docs/evidencias-04/ensayos/bloqueo-persistencia-intercambio-observados.json'
        observed = json.loads(path.read_text(encoding='utf-8'))
        fixture = ROOT / observed['fixture']
        self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(), observed['fixture_sha256'])
        for shot in observed['screenshots']:
            self.assertEqual(hashlib.sha256((ROOT / shot['path']).read_bytes()).hexdigest(), shot['sha256'])
        budget = import_bc3(fixture, observed_presto88=True).budget
        budget.concepts['OVR1'] = replace(budget.concepts['OVR1'], base_price=Decimal('5'))
        budget.locked_prices = {'OVITEM': Decimal('20')}
        restored = loads(dumps(budget))
        expected = observed['reopen']
        calc = calculator_for(restored)
        self.assertEqual(calc.total(), Decimal(expected['root']))
        self.assertEqual(calc.price('OVITEM'), Decimal(expected['OVITEM']))
        for code in ('OVA', 'OVB'):
            self.assertEqual(calc.price(code + '#'), Decimal(expected[code]))
        export = observed['native_export']
        native_path = ROOT / export['path']
        self.assertEqual(hashlib.sha256(native_path.read_bytes()).hexdigest(), export['sha256'])
        imported = import_bc3(native_path, observed_presto88=True)
        self.assertEqual(imported.declared_prices, {code: Decimal(price) for code, price in export['declared_prices'].items()})
        self.assertEqual(imported.record_counts['D'], export['decomposition_records'])
        self.assertEqual(imported.record_counts.get('M', 0), export['measurement_records'])
        self.assertEqual(imported.budget.locked_prices, {})
        expected = observed['native_reimport']
        calc = calculator_for(imported.budget)
        self.assertEqual(calc.total(), Decimal(expected['root']))
        self.assertEqual(calc.price('OVITEM'), Decimal(expected['OVITEM']))
        for code in ('OVA', 'OVB'):
            self.assertEqual(calc.price(code + '#'), Decimal(expected[code]))
        for resource in expected['resources']:
            relation = next(r for r in imported.budget.relations if r.parent_code == 'OVITEM' and r.child_code == resource['code'])
            amount = calc.relation(relation.id)
            self.assertEqual(amount.quantity, Decimal(resource['quantity']))
            self.assertEqual(amount.unit_price, Decimal(resource['price']))
            self.assertEqual(amount.amount, Decimal(resource['amount']))

    def test_native_evidence_uses_exact_fixture_and_baseline(self):
        folder = ROOT / 'tests/reference04/price_override'
        manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        digest = hashlib.sha256((folder / manifest['fixture']).read_bytes()).hexdigest()
        self.assertEqual(digest, manifest['sha256'])
        baseline = json.loads((ROOT / manifest['native_results'][0]).read_text(encoding='utf-8'))
        self.assertEqual(digest, baseline['sha256'])
        budget = import_bc3(folder / manifest['fixture'], observed_presto88=True).budget
        calculator = calculator_for(budget)
        observed = baseline['baseline']
        self.assertEqual(calculator.total(), Decimal(observed['root']))
        for code in ('OVA', 'OVB'):
            self.assertEqual(calculator.price(code + '#'), Decimal(observed[code]))
        self.assertEqual(calculator.price('OVITEM'), Decimal(observed['OVITEM']))

    def test_project_lock_persistence_and_export_protection(self):
        from openpresto.bc3_exporter import render_bc3, BC3ExportError
        budget = import_bc3(ROOT / 'tests/reference04/price_override/baseline.bc3', observed_presto88=True).budget
        base = to_dict(budget)
        budget.locked_prices = {'OVITEM': Decimal('20')}
        document = to_dict(budget)
        self.assertEqual(document['version'], 13)
        self.assertEqual(document['project'], base)
        self.assertEqual(budget.total(), Decimal('140.00'))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'locked.json'
            save_budget(budget, path)
            restored = load_budget(path)
        self.assertEqual(to_dict(restored), document)
        self.assertEqual(calculator_for(restored).total(), Decimal('140.00'))
        restored.concepts['OVR1'] = replace(restored.concepts['OVR1'], base_price=Decimal('5'))
        self.assertEqual(loads(dumps(restored)).total(), Decimal('140.00'))
        restored.locked_prices = {}
        self.assertEqual(restored.total(), Decimal('98'))
        self.assertEqual(to_dict(restored)['version'], base['version'])
        self.assertTrue(render_bc3(budget).warnings)
        for locks in ({'unknown': '20'}, {'OVITEM': 'NaN'}, {'OVR1': '20'}, {}):
            invalid = copy.deepcopy(document)
            invalid['locked_prices'] = locks
            with self.subTest(locks=locks), self.assertRaises(StorageError):
                from_dict(invalid)
        budget.indirect_config = {'profile': 'presto88_default'}
        with self.assertRaises(StorageError):
            dumps(budget)

    def test_native_lock_resource_change_and_unlock(self):
        folder = ROOT / 'docs/evidencias-04/ensayos'
        lock = json.loads((folder / 'precio-bloqueado-observado.json').read_text(encoding='utf-8'))
        unlock = json.loads((folder / 'precio-desbloqueado-observado.json').read_text(encoding='utf-8'))
        for observation in (lock, unlock):
            for shot in observation['screenshots']:
                self.assertEqual(hashlib.sha256((ROOT / shot['path']).read_bytes()).hexdigest(), shot['sha256'])
        budget = import_bc3(ROOT / 'tests/reference04/price_override/baseline.bc3', observed_presto88=True).budget
        before = dumps(budget)
        config = {'OVITEM': Decimal('20')}
        calculator = LockedPriceCalculator(budget, config)
        config['OVITEM'] = Decimal('99')
        observed = lock['observed']
        self.assertEqual(calculator.total(), Decimal(observed['root']))
        for code in ('OVA', 'OVB'):
            self.assertEqual(calculator.price(code + '#'), Decimal(observed[code]))
        self.assertEqual(calculator.price('OVITEM'), Decimal(observed['OVITEM_A']))
        self.assertEqual(dumps(budget), before)
        budget.concepts['OVR1'] = replace(budget.concepts['OVR1'], base_price=Decimal('5'))
        self.assertEqual(calculator.price('OVITEM'), Decimal(lock['resource_edit']['OVITEM_price']))
        self.assertEqual(calculator.total(), Decimal(unlock['before_unlock']['root_after_resource_edit']))
        unlocked = calculator.without_lock('OVITEM')
        after = unlock['after_unlock']
        self.assertEqual(unlocked.price('OVITEM'), Decimal(after['OVITEM_price']))
        self.assertEqual(unlocked.total(), Decimal(after['OVROOT']))
        for code in ('OVA', 'OVB'):
            self.assertEqual(unlocked.price(code + '#'), Decimal(after[code]))
