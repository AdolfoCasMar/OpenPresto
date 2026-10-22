import unittest,json
from openpresto.budget import Budget,BudgetError,BudgetConcept,BudgetRelation
from openpresto import site_issues as issues
from openpresto.storage import dumps,loads,to_dict,StorageError
from openpresto.commands import ProjectSession
from openpresto.reports import report_table,report_html
from test_production import project
from decimal import Decimal


def create(b,reference='I-1',due='2026-10-05',relation='A',opened='2026-10-01'):
    issues.set_issue(b,reference,opened,'Crack in wall','Team A','high','quality',due,relation,'Example')
    return issues.validate(b)[-1]['id']


class SiteIssuesTests(unittest.TestCase):
    def test_lifecycle_preserves_dated_notes_and_reopens(self):
        b=project();rid=create(b)
        issues.set_status(b,rid,'in_progress','2026-10-02','Investigating')
        issues.set_status(b,rid,'resolved','2026-10-03','Repaired and checked')
        self.assertEqual(issues.listing(b,'2026-10-10',True),[])
        issues.set_status(b,rid,'open','2026-10-04','Problem returned')
        self.assertEqual([e['status'] for e in issues.validate(b)[0]['events']],['open','in_progress','resolved','open'])
        self.assertTrue(issues.listing(b,'2026-10-10')[0]['overdue']);self.assertEqual(issues.event_rows(b)[-1][-1],'Problem returned')
    def test_overdue_boundary_unknown_date_and_future_opening(self):
        b=project();create(b);create(b,'I-2',due=None);create(b,'I-3',due='2026-11-05',opened='2026-11-01')
        self.assertEqual(len(issues.listing(b,'2026-10-05')),2)
        self.assertEqual(issues.listing(b,'2026-10-05',overdue_only=True),[])
        self.assertEqual(len(issues.listing(b,'2026-10-06',overdue_only=True)),1)
        self.assertEqual(issues.report_rows(b,'2026-10-06')[1][7],'Sin fecha')
    def test_closed_entries_excluded_from_pending_and_cannot_edit(self):
        b=project();rid=create(b);issues.set_status(b,rid,'resolved','2026-10-02','Done')
        self.assertEqual(issues.listing(b,'2026-10-10',True),[])
        with self.assertRaises(BudgetError):issues.set_issue(b,'I-1','2026-10-01','Changed',issue_id=rid)
        issues.set_status(b,rid,'open','2026-10-03','Reopened');issues.set_issue(b,'I-1','2026-10-01','Changed',issue_id=rid)
        self.assertEqual(issues.validate(b)[0]['title'],'Changed')
    def test_illegal_transitions_missing_notes_and_dates_are_atomic(self):
        b=project();rid=create(b);before=dumps(b)
        for status,day,note in [('open','2026-10-02','Reason'),('resolved','2026-10-02',''),('cancelled','2026-10-02',''),('in_progress','2026-09-01',''),('in_progress','bad','')]:
            with self.assertRaises(BudgetError):issues.set_status(b,rid,status,day,note)
            self.assertEqual(dumps(b),before)
        issues.set_status(b,rid,'cancelled','2026-10-02','Not applicable')
        with self.assertRaises(BudgetError):issues.set_status(b,rid,'open','2026-10-03','Reason')
    def test_reference_unique_and_opening_immutable(self):
        b=project();rid=create(b)
        with self.assertRaises(BudgetError):create(b,reference=' i-1 ')
        with self.assertRaises(BudgetError):issues.set_issue(b,'I-NEW','2026-10-01','Changed',issue_id=rid)
        with self.assertRaises(BudgetError):issues.set_issue(b,'I-1','2026-10-02','Changed',issue_id=rid)
        create(b,due=None,opened='2027-01-01')
    def test_general_issue_needs_no_budget_relations(self):
        b=Budget();issues.set_issue(b,'GEN','2026-10-01','Access blocked')
        self.assertEqual(issues.report_rows(b,'2026-10-10')[0][8:10],('',''))
    def test_invalid_properties_rejected(self):
        for params in [dict(title=' '),dict(priority='unknown'),dict(category=[]),dict(due='2026-09-30'),dict(due='bad'),dict(relation_id='missing'),dict(responsible=1)]:
            b=project();before=dumps(b);args=dict(reference='I',opened='2026-10-01',title='Issue');args.update(params)
            with self.assertRaises(BudgetError):issues.set_issue(b,**args)
            self.assertEqual(dumps(b),before)
    def test_storage31_and_corrupt_history_rejected(self):
        b=project();rid=create(b);issues.set_status(b,rid,'resolved','2026-10-02','Done')
        self.assertEqual(to_dict(b)['version'],31);self.assertEqual(issues.validate(loads(dumps(b))),issues.validate(b))
        data=issues.validate(b);data[0]['events'][-1]['status']='cancelled';b.project_metadata[issues.KEY]=json.dumps(data)
        with self.assertRaises(StorageError):dumps(b)
    def test_does_not_change_economic_or_production_data(self):
        b=project();before=dumps(b);rid=create(b);issues.set_status(b,rid,'resolved','2026-10-02','Done')
        self.assertEqual(set(b.project_metadata),{issues.KEY});del b.project_metadata[issues.KEY];self.assertEqual(dumps(b),before)
    def test_commands_support_undo_and_redo(self):
        s=ProjectSession(project());s.execute('site.issue.set',dict(reference='I',opened='2026-10-01',title='Issue'))
        rid=issues.validate(s.budget)[0]['id'];s.execute('site.issue.status',dict(issue_id=rid,status='resolved',date='2026-10-02',note='Done'))
        self.assertEqual(issues.validate(s.undo())[0]['status'],'open');s.redo();self.assertEqual(len(issues.event_rows(s.budget)),2)
    def test_filtered_reports_and_escaping(self):
        b=project();rid=create(b,reference='<script>');self.assertIn('&lt;script&gt;',report_html(b,'incidencias:2026-10-10:todas'))
        self.assertEqual(len(report_table(b,'incidencias:2026-10-10:vencidas')[1]),1)
        self.assertEqual(len(report_table(b,'incidencias_historial')[1]),1)
        for kind in ('incidencias:bad:todas','incidencias:2026-10-10','incidencias:2026-10-10:unknown'):
            with self.assertRaises(ValueError):report_table(b,kind)
    def test_same_code_different_chapters_remains_distinct(self):
        b=project();b.add_concept(BudgetConcept('CH2',nature='capítulo'));b.add_relation(BudgetRelation('ROOT','CH2',Decimal(1),3,'root2'));b.add_relation(BudgetRelation('CH2','A',Decimal(1),1,'A2'))
        create(b);create(b,'I-2',relation='A2')
        self.assertEqual({r[8] for r in issues.report_rows(b,'2026-10-10')},{'A','A2'})

if __name__=='__main__':unittest.main()
