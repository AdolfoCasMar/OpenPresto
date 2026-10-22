"""Documented certification rule; own examples, no executed parity claim."""
from decimal import Decimal
from dataclasses import replace
import unittest

from openpresto.budget import Budget, BudgetConcept, BudgetRelation, BudgetError
from openpresto.certifications import CertificationAtOrigin
from openpresto.storage import dumps, loads, StorageError


class CertificationTests(unittest.TestCase):
    def test_independent_presto88_origin_observation(self):
        import hashlib
        import json
        from pathlib import Path
        from openpresto.storage import load_budget
        from openpresto.bc3_exporter import render_bc3
        from openpresto.calculations import BudgetCalculator
        repo = Path(__file__).resolve().parents[1]
        directory = repo / 'docs/evidencias-04/ensayos'
        observed = json.loads((directory / 'certificacion-origen-observada.json').read_text(encoding='utf-8'))
        self.assertEqual(observed['source'], 'presto_observation')
        fixture = repo / observed['fixture']
        native = repo / observed['native_project']
        self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(), observed['fixture_sha256'])
        self.assertEqual(hashlib.sha256(native.read_bytes()).hexdigest(), observed['native_project_sha256'])
        for name, digest in observed['evidence'].items():
            self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(), digest)
        b = load_budget(native)
        rid = next(r.id for r in b.relations if r.parent_code == observed['relation']['parent_code'] and r.child_code == observed['relation']['child_code'])
        b.certified_quantities.clear()
        self.assertEqual(render_bc3(b).data, fixture.read_bytes())
        baseline = dumps(b)
        for case in observed['cases']:
            result = CertificationAtOrigin(b, {rid:case['certified_quantity']}).relation(rid)
            self.assertEqual(result.quantity, Decimal(case['certified_quantity']))
            self.assertEqual(result.unit_price, Decimal(case['unit_price']))
            self.assertEqual(result.amount, Decimal(case['amount']))
            self.assertEqual(result.budget_quantity, Decimal(observed['budget']['quantity']))
            self.assertEqual(BudgetCalculator(b).total(), Decimal(observed['budget']['amount']))
            self.assertEqual(dumps(b), baseline)

    def test_v9_preserves_other_project_features(self):
        from openpresto.budget import BudgetMeasurement
        b = self.budget()
        b.root_quantity_decimals = 1
        b.bc3_zero_dimensions_as_blank = True
        b.concepts['CH1'] = replace(b.concepts['CH1'], measurement_decimals=2, text='Texto propio')
        relation = b.relations[1]
        updated = replace(relation, factor=Decimal('1.5'))
        b.relations[1] = updated
        b._relations_by_id[updated.id] = updated
        b.add_measurement(BudgetMeasurement('r1', n_lines=2, length=3, height='0.2345', annulled_dimensions=('height',)))
        b.add_measurement(BudgetMeasurement('r2', n_lines=2, length=3, formula='B^2'))
        b.certified_quantities = {'r1':Decimal(4)}
        encoded = dumps(b)
        restored = loads(encoded)
        self.assertEqual(dumps(restored), encoded)
        self.assertEqual(restored.relation_quantity('r1'), 6)
        self.assertEqual(restored.relation_quantity('r2'), 18)

    def test_project_v9_roundtrip_and_legacy_budget_unchanged(self):
        import json
        b = self.budget()
        previous = dumps(b)
        b.certified_quantities = {'r1':Decimal('4.125'), 'r2':Decimal('0')}
        encoded = dumps(b)
        self.assertEqual(json.loads(encoded)['version'], 9)
        restored = loads(encoded)
        self.assertEqual(restored.certified_quantities, b.certified_quantities)
        self.assertEqual(CertificationAtOrigin(restored, restored.certified_quantities).relation('r1').amount, Decimal('51.56'))
        restored.certified_quantities.clear()
        self.assertEqual(dumps(restored), previous)
        from openpresto.bc3_exporter import render_bc3, BC3ExportError
        with self.assertRaises(BC3ExportError):
            render_bc3(b)

    def test_project_rejects_orphans_and_non_decimal_fields(self):
        import json
        b = self.budget()
        b.certified_quantities = {'r1':Decimal(4)}
        data = json.loads(dumps(b))
        data['certification_at_origin']['missing'] = '1'
        with self.assertRaises(StorageError):
            loads(json.dumps(data))
        data['certification_at_origin'] = {'r1':4}
        with self.assertRaises(StorageError):
            loads(json.dumps(data))

    def budget(self):
        b = Budget('ROOT')
        for c in (BudgetConcept('ROOT'), BudgetConcept('CH1', nature='capitulo'),
                  BudgetConcept('CH2', nature='capítulo'),
                  BudgetConcept('ITEM', nature='partida', base_price='12.50')):
            b.add_concept(c)
        for r in (BudgetRelation('ROOT','CH1',position=1,id='c1'),
                  BudgetRelation('ROOT','CH2',position=2,id='c2'),
                  BudgetRelation('CH1','ITEM',quantity=10,id='r1'),
                  BudgetRelation('CH2','ITEM',quantity=20,id='r2')):
            b.add_relation(r)
        return b

    def test_reused_item_has_separate_cumulative_quantities(self):
        b = self.budget()
        before = dumps(b)
        quantities = {'r1':'4', 'r2':'3'}
        cert = CertificationAtOrigin(b, quantities)
        quantities['r1'] = '100'
        self.assertEqual(cert.relation('r1').amount, Decimal('50.00'))
        self.assertEqual(cert.relation('r2').amount, Decimal('37.50'))
        self.assertEqual(cert.relation('r1').budget_quantity, 10)
        self.assertEqual(dumps(b), before)
        self.assertEqual(len(cert.rows()), 2)

    def test_over_budget_is_reported_not_clamped(self):
        cert = CertificationAtOrigin(self.budget(), {'r1':11})
        self.assertTrue(cert.relation('r1').exceeds_budget)
        self.assertEqual(cert.relation('r1').amount, Decimal('137.50'))
        self.assertEqual(cert.relation('r2').quantity, 0)

    def test_unit_price_uses_budget_decomposition(self):
        b = self.budget()
        b.add_concept(BudgetConcept('LABOUR', base_price=5))
        b.add_relation(BudgetRelation('ITEM','LABOUR',quantity=3,id='resource'))
        result = CertificationAtOrigin(b, {'r1':2}).relation('r1')
        self.assertEqual(result.unit_price, Decimal('15.00'))
        self.assertEqual(result.amount, Decimal('30.00'))
        with self.assertRaises(BudgetError):
            CertificationAtOrigin(b, {'resource':1})

    def test_invalid_and_ambiguous_inputs(self):
        b = self.budget()
        for quantities in ({'missing':1}, {'c1':1}, {'r1':'NaN'}, {'r1':True}, {'r1':1.2}):
            with self.assertRaises(BudgetError):
                CertificationAtOrigin(b, quantities)
        b.concepts['ITEM'] = replace(b.concepts['ITEM'], nature='0')
        with self.assertRaises(BudgetError):
            CertificationAtOrigin(b, {'r1':1})

    def test_revalidates_after_structure_change(self):
        b = self.budget()
        cert = CertificationAtOrigin(b, {'r1':2})
        b.concepts['CH1'] = replace(b.concepts['CH1'], nature='partida')
        with self.assertRaises(BudgetError):
            cert.rows()


if __name__ == '__main__':
    unittest.main()
