import unittest
from openpresto import nonconformities as nc,quality_control as q,site_issues as issues
from openpresto.budget import BudgetError
from openpresto.commands import ProjectSession
from openpresto.storage import dumps,loads,to_dict,StorageError
from test_quality_control import project,create,checks


def sample():
    b=project();rid=create(b,lines=checks('fail','Crack observed'));q.set_status(b,rid,'reviewed','2026-10-02');return b,rid


class NonconformityTests(unittest.TestCase):
    def test_source_and_issue_have_explicit_stable_link(self):
        b,rid=sample();nc.create_issue(b,rid,0,'NC-1','2026-10-03','Team','high','2026-10-10')
        case=issues.validate(b)[0];self.assertEqual(case['category'],'quality');self.assertEqual(case['relation_id'],'A');self.assertIn('Crack observed',case['description']);self.assertEqual(nc.listing(b)[0]['issue_id'],case['id']);self.assertEqual(to_dict(b)['version'],34)
        self.assertEqual(nc.listing(loads(dumps(b))),nc.listing(b))
    def test_failed_creation_rolls_back_both_models_even_without_command_wrapper(self):
        b,rid=sample();before=dumps(b)
        for params in [dict(opened='2026-10-01'),dict(opened='2026-10-03',due='2026-10-01'),dict(opened='bad')]:
            with self.assertRaises(BudgetError):nc.create_issue(b,rid,0,'NC-1',**params)
            self.assertEqual(dumps(b),before)
    def test_duplicate_prohibited_after_resolution(self):
        b,rid=sample();nc.create_issue(b,rid,0,'NC-1','2026-10-03');case=issues.validate(b)[0];issues.set_status(b,case['id'],'resolved','2026-10-04','Fixed')
        self.assertEqual(nc.listing(b,pending_only=True),[]);self.assertEqual(q.verdict(q.validate(b)[0]),'No conforme')
        with self.assertRaises(BudgetError):nc.create_issue(b,rid,0,'NC-2','2026-10-05')
        issues.set_status(b,case['id'],'open','2026-10-05','Returned');self.assertEqual(nc.listing(b)[0]['row'][-1],'Pendiente')
    def test_cancelled_inspection_does_not_cancel_issue(self):
        b,rid=sample();nc.create_issue(b,rid,0,'NC-1','2026-10-03');q.set_status(b,rid,'cancelled','2026-10-04','Replaced')
        self.assertEqual(nc.listing(b),[]);self.assertEqual(len(nc.listing(b,include_cancelled=True)),1);self.assertEqual(issues.validate(b)[0]['status'],'open')
    def test_cancelled_issue_needs_review_and_does_not_erase_link(self):
        b,rid=sample();nc.create_issue(b,rid,0,'NC-1','2026-10-03');case=issues.validate(b)[0];issues.set_status(b,case['id'],'cancelled','2026-10-04','Wrong issue')
        self.assertEqual(nc.listing(b,pending_only=True)[0]['row'][-1],'Revisar incidencia anulada')
    def test_only_reviewed_failed_checks_allowed(self):
        b=project();rid=create(b)
        with self.assertRaises(BudgetError):nc.create_issue(b,rid,0,'NC','2026-10-03')
        q.set_status(b,rid,'reviewed','2026-10-02')
        with self.assertRaises(BudgetError):nc.create_issue(b,rid,0,'NC','2026-10-03')
        b,rid=sample()
        for index in (True,-1,1,'0'):
            with self.assertRaises(BudgetError):nc.create_issue(b,rid,index,'NC','2026-10-03')
    def test_atomic_command_undo_restores_unlinked_state(self):
        b,rid=sample();s=ProjectSession(b);s.execute('quality.issue.create',dict(inspection_id=rid,check_index=0,reference='NC',opened='2026-10-03'))
        self.assertEqual(len(nc.validate(s.budget)),1);s.undo();self.assertEqual(nc.validate(s.budget),[]);self.assertEqual(issues.validate(s.budget),[]);s.redo();self.assertEqual(len(nc.validate(s.budget)),1)
    def test_dangling_links_rejected_and_reports(self):
        from openpresto.reports import report_table
        b,rid=sample();nc.create_issue(b,rid,0,'NC','2026-10-03');self.assertEqual(len(report_table(b,'no_conformidades')[1]),1)
        b.project_metadata[issues.KEY]='[]'
        with self.assertRaises(StorageError):dumps(b)

if __name__=='__main__':unittest.main()
