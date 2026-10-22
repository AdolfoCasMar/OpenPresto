import unittest,json
from openpresto import quality_control as q
from openpresto.budget import Budget,BudgetError
from openpresto.storage import dumps,loads,to_dict,StorageError
from openpresto.commands import ProjectSession
from openpresto.reports import report_table,report_html
from test_production import project


def checks(result='pass',note=''):
    return [dict(criterion='Visual check',result=result,note=note)]


def create(b,reference='QC-1',lines=None,inspector='Inspector',relation='A'):
    q.set_inspection(b,reference,'2026-10-01','Inspection',checks() if lines is None else lines,inspector,relation)
    return q.validate(b)[-1]['id']


class QualityControlTests(unittest.TestCase):
    def test_draft_is_not_conformity_and_review_freezes_results(self):
        b=project();rid=create(b);self.assertEqual(q.verdict(q.validate(b)[0]),'Pendiente de revisión')
        q.set_status(b,rid,'reviewed','2026-10-02');self.assertEqual(q.verdict(q.validate(b)[0]),'Conforme')
        with self.assertRaises(BudgetError):q.set_inspection(b,'QC-1','2026-10-01','Changed',checks('fail','Problem'),inspection_id=rid)
        self.assertEqual(q.validate(b)[0]['checks'],checks())
    def test_failed_check_means_nonconformity_after_review(self):
        b=project();rid=create(b,lines=checks()+checks('fail','Crack observed')+checks('na'))
        q.set_status(b,rid,'reviewed','2026-10-02');row=q.report_rows(b)[0]
        self.assertEqual(row[7:12],('No conforme',1,1,0,1));self.assertEqual(q.detail_rows(b)[1][-1],'Crack observed')
    def test_incomplete_unassigned_and_all_na_reviews_rejected(self):
        for lines,inspector in [(checks('pending'),'Inspector'),(checks('na'),'Inspector'),(checks(),' '),(checks('fail'),'Inspector')]:
            b=project();rid=create(b,lines=lines,inspector=inspector);before=dumps(b)
            with self.assertRaises(BudgetError):q.set_status(b,rid,'reviewed','2026-10-02')
            self.assertEqual(dumps(b),before)
    def test_review_and_cancellation_date_validation(self):
        b=project();rid=create(b)
        for day in ('bad','2026-09-30'):
            with self.assertRaises(BudgetError):q.set_status(b,rid,'reviewed',day)
        q.set_status(b,rid,'reviewed','2026-10-03')
        for day,reason in [('2026-10-02','Reason'),('2026-10-04','')]:
            with self.assertRaises(BudgetError):q.set_status(b,rid,'cancelled',day,reason)
        q.set_status(b,rid,'cancelled','2026-10-04','Replacement needed')
        row=q.report_rows(b)[0];self.assertEqual(row[7],'Anulado');self.assertEqual(row[12],'2026-10-03');self.assertEqual(row[-2:],('2026-10-04','Replacement needed'))
        with self.assertRaises(BudgetError):q.set_status(b,rid,'reviewed','2026-10-05')
    def test_draft_can_be_cancelled_without_manufactured_review(self):
        b=project();rid=create(b,lines=checks('pending'));q.set_status(b,rid,'cancelled','2026-10-02','Not applicable')
        self.assertIsNone(q.validate(b)[0]['reviewed_on'])
    def test_reference_unique_and_no_empty_checklist(self):
        b=project();create(b)
        with self.assertRaises(BudgetError):create(b,reference=' qc-1 ')
        with self.assertRaises(BudgetError):create(b,reference='QC-2',lines=[])
    def test_invalid_data_is_atomic(self):
        for params in [dict(title=' '),dict(relation_id='missing'),dict(checks=[dict(criterion='',result='pass',note='')]),dict(checks=checks('unknown')),dict(inspector=1)]:
            b=project();before=dumps(b);args=dict(reference='QC',date='2026-10-01',title='Inspection',checks=checks());args.update(params)
            with self.assertRaises(BudgetError):q.set_inspection(b,**args)
            self.assertEqual(dumps(b),before)
    def test_storage32_and_corrupt_review_rejected(self):
        b=project();rid=create(b);q.set_status(b,rid,'reviewed','2026-10-02');self.assertEqual(to_dict(b)['version'],32)
        self.assertEqual(q.validate(loads(dumps(b))),q.validate(b))
        data=q.validate(b);data[0]['checks'][0]['result']='pending';b.project_metadata[q.KEY]=json.dumps(data)
        with self.assertRaises(StorageError):dumps(b)
    def test_commands_and_undo_redo(self):
        s=ProjectSession(project());s.execute('quality.inspection.set',dict(reference='QC',date='2026-10-01',title='Inspection',checks=checks(),inspector='Inspector'))
        rid=q.validate(s.budget)[0]['id'];s.execute('quality.inspection.status',dict(inspection_id=rid,status='reviewed',date='2026-10-02'))
        self.assertEqual(q.validate(s.undo())[0]['status'],'draft');s.redo();self.assertEqual(q.verdict(q.validate(s.budget)[0]),'Conforme')
    def test_economic_and_other_modules_unchanged(self):
        b=project();before=dumps(b);rid=create(b);q.set_status(b,rid,'reviewed','2026-10-02');self.assertEqual(set(b.project_metadata),{q.KEY});del b.project_metadata[q.KEY];self.assertEqual(dumps(b),before)
    def test_general_control_and_reports(self):
        b=project();create(b,reference='<script>',relation=None)
        self.assertIn('&lt;script&gt;',report_html(b,'calidad_controles'));self.assertEqual(len(report_table(b,'calidad_comprobaciones')[1]),1)
        self.assertEqual(q.report_rows(b)[0][3:5],('',''))
        empty=Budget();q.set_inspection(empty,'GEN','2026-10-01','General',checks());self.assertEqual(len(q.validate(empty)),1)

if __name__=='__main__':unittest.main()
