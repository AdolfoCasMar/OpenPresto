"""Own examples of documented phase rules; not runtime comparison evidence."""
from dataclasses import replace
from decimal import Decimal
import unittest

from openpresto.certification_phases import CertificationSchedule, PhasedCertification
from openpresto.budget import BudgetError
from openpresto.storage import dumps
import test_certifications as certification_fixture


class CertificationPhasesTests(unittest.TestCase):
    def test_independent_presto88_approval_and_future_exclusion(self):
        import json
        import hashlib
        from pathlib import Path
        from openpresto.storage import load_budget
        from openpresto.calculations import BudgetCalculator
        repo = Path(__file__).resolve().parents[1]
        directory = repo / 'docs/evidencias-04/ensayos'
        observed = json.loads((directory / 'fases-certificacion-observadas.json').read_text(encoding='utf-8'))
        self.assertEqual(observed['source'], 'presto_observation')
        for key in ('base_fixture','native_project'):
            self.assertEqual(hashlib.sha256((repo / observed[key]).read_bytes()).hexdigest(), observed[key+'_sha256'])
        for name, digest in observed['evidence'].items():
            self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(), digest)
        b = load_budget(repo / observed['native_project'])
        b.certified_quantities.clear()
        rid = next(r.id for r in b.relations if r.parent_code == observed['relation']['parent_code'] and r.child_code == observed['relation']['child_code'])
        before = dumps(b)
        for case in observed['cases']:
            schedule = CertificationSchedule(observed['comparison_start_date'], tuple(observed['end_dates']), case['approved'])
            values = {int(number):{rid:quantity} for number,quantity in case['quantities'].items()}
            result = PhasedCertification(b, schedule, values).relation(rid)
            self.assertEqual(result.cumulative_quantity, Decimal(case['cumulative_quantity']))
            self.assertEqual(result.cumulative_amount, Decimal(case['cumulative_amount']))
            self.assertEqual(result.unit_price, Decimal(observed['unit_price']))
            self.assertEqual(BudgetCalculator(b).total(), Decimal(observed['budget_amount']))
            self.assertEqual(dumps(b), before)

    def test_project_v10_roundtrip_and_separate_modes(self):
        import json
        from openpresto.storage import loads
        from openpresto.certification_phases import project_phases
        b = certification_fixture.CertificationTests().budget()
        b.certified_quantities = {'r2':Decimal(1)}
        b.certification_schedule = self.schedule()
        b.phase_certified_quantities = {1:{'r1':Decimal(2)},2:{'r1':Decimal(3)},3:{'r1':Decimal(100)}}
        encoded = dumps(b)
        self.assertEqual(json.loads(encoded)['version'], 10)
        restored = loads(encoded)
        self.assertEqual(dumps(restored), encoded)
        self.assertEqual(project_phases(restored).relation('r1').cumulative_amount, Decimal('62.50'))
        self.assertEqual(restored.certified_quantities, {'r2':Decimal(1)})
        self.assertTrue(restored.has_certification('r1'))

    def test_project_rejects_overlap_orphan_calendar_and_duplicate_phase(self):
        import json
        from openpresto.storage import loads, StorageError
        b = certification_fixture.CertificationTests().budget()
        b.phase_certified_quantities = {1:{'r1':Decimal(1)}}
        with self.assertRaises(BudgetError):
            dumps(b)
        b.certification_schedule = self.schedule()
        b.certified_quantities = {'r1':Decimal(1)}
        with self.assertRaises(BudgetError):
            dumps(b)
        b.certified_quantities.clear()
        data = json.loads(dumps(b))
        data['certification_phases']['quantities'].append(data['certification_phases']['quantities'][0])
        with self.assertRaises(StorageError):
            loads(json.dumps(data))

    def schedule(self, current=2):
        return CertificationSchedule('2026-01-01', ('2026-01-31','2026-02-28','2026-03-31'), current)

    def test_cumulative_previous_and_future_exclusion(self):
        b = certification_fixture.CertificationTests().budget()
        before = dumps(b)
        data = {1:{'r1':2}, 2:{'r1':3}, 3:{'r1':100}}
        view = PhasedCertification(b, self.schedule(), data)
        data[1]['r1'] = 900
        row = view.relation('r1')
        self.assertEqual(row.phase_quantity, 3)
        self.assertEqual(row.previous_quantity, 2)
        self.assertEqual(row.cumulative_quantity, 5)
        self.assertEqual(row.previous_amount, Decimal('25.00'))
        self.assertEqual(row.cumulative_amount, Decimal('62.50'))
        self.assertEqual(row.current_amount, Decimal('37.50'))
        self.assertEqual(dumps(b), before)
        approved = PhasedCertification(b, self.schedule(3), view.quantities).relation('r1')
        self.assertEqual(approved.cumulative_quantity, 105)

    def test_current_amount_is_difference_of_valuations(self):
        b = certification_fixture.CertificationTests().budget()
        view = PhasedCertification(b, self.schedule(), {1:{'r1':'.001'},2:{'r1':'.001'}})
        row = view.relation('r1')
        self.assertEqual(row.previous_amount, Decimal('.01'))
        self.assertEqual(row.cumulative_amount, Decimal('.03'))
        self.assertEqual(row.current_amount, Decimal('.02'))

    def test_no_approved_phase_excludes_all_quantities(self):
        view = PhasedCertification(certification_fixture.CertificationTests().budget(), self.schedule(0), {1:{'r1':10}})
        row = view.relation('r1')
        self.assertEqual(row.current_amount, 0)
        self.assertEqual(row.cumulative_quantity, 0)
        self.assertEqual(view.schedule.state(1), 2)

    def test_calendar_and_states(self):
        calendar = self.schedule()
        self.assertEqual(calendar.period(1), ('2026-01-01','2026-01-31'))
        self.assertEqual(calendar.period(2), ('2026-02-01','2026-02-28'))
        self.assertEqual([calendar.state(i) for i in (1,2,3)], [0,3,2])

    def test_invalid_dates_order_and_references(self):
        for start, ends, current in (
            ('2026-02-30', (), 0), ('2026-01-01', ('2025-12-31',), 1),
            ('2026-01-01', ('2026-03-31','2026-02-28'), 1),
            ('2026-01-01', ('2026-01-31','2026-01-31'), 1),
            ('20260101', (), 0), ('2026-01-01', (), True)):
            with self.assertRaises(BudgetError):
                CertificationSchedule(start, ends, current)
        for values in ({4:{'r1':1}}, {True:{'r1':1}}, {1:{'missing':1}}, {3:{'r1':'NaN'}}):
            with self.assertRaises(BudgetError):
                PhasedCertification(certification_fixture.CertificationTests().budget(), self.schedule(), values)

    def test_reused_item_and_changed_structure(self):
        b = certification_fixture.CertificationTests().budget()
        view = PhasedCertification(b, self.schedule(), {1:{'r1':2,'r2':1},3:{'r2':3}})
        self.assertEqual(view.relation('r1').cumulative_quantity, 2)
        self.assertEqual(view.relation('r2').cumulative_quantity, 1)
        b.concepts['CH2'] = replace(b.concepts['CH2'], nature='partida')
        with self.assertRaises(BudgetError):
            view.relation('r1')


if __name__ == '__main__':
    unittest.main()
