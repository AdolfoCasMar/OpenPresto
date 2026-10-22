import unittest,json
from decimal import Decimal
from openpresto.budget import Budget,BudgetConcept,BudgetRelation,BudgetError
from openpresto import production as p
from openpresto.storage import dumps,loads,to_dict,StorageError
from openpresto.commands import ProjectSession


def project():
    b=Budget()
    for c in (BudgetConcept('ROOT',nature='capítulo'),BudgetConcept('A','m2','Wall','partida',Decimal(20)),BudgetConcept('B','m3','Concrete','partida',Decimal(30))):b.add_concept(c)
    b.set_root('ROOT')
    for i,code in enumerate(('A','B'),1):b.add_relation(BudgetRelation('ROOT',code,Decimal(10),i,code))
    return b


def create(b,reference='P1',quantity='2.5',date='2026-10-01'):
    p.set_report(b,reference,date,'Team A','Example',[dict(relation_id='A',quantity=quantity)])
    return p.validate(b)[-1]['id']


class ProductionTests(unittest.TestCase):
    def test_confirm_and_cancel_do_not_change_budget_or_other_modules(self):
        b=project();total=b.total();rid=create(b)
        self.assertEqual(p.quantities(b,'2026-10-31'),{})
        p.set_status(b,rid,'posted');self.assertEqual(p.quantities(b,'2026-10-31'),{'A':Decimal('2.5')})
        self.assertEqual(p.quantities(b,'2026-09-30'),{})
        p.set_status(b,rid,'cancelled','2026-10-02','Correction')
        self.assertEqual(p.quantities(b,'2026-10-31'),{});self.assertEqual(b.total(),total)
        self.assertEqual(set(b.project_metadata),{p.KEY})
    def test_multiline_and_distinct_units_are_separate(self):
        b=project();p.set_report(b,'P1','2026-10-01','','',[dict(relation_id='A',quantity='12'),dict(relation_id='B',quantity='3')])
        p.set_status(b,p.validate(b)[0]['id'],'posted');self.assertEqual(p.quantities(b,'2026-10-31'),{'A':Decimal(12),'B':Decimal(3)})
        self.assertEqual(len(p.report_rows(b)),2)
    def test_invalid_quantities_and_relations_are_atomic(self):
        for quantity in ('0','-1','NaN','Infinity','1e16','1e-13',True,1.5):
            b=project();before=dumps(b)
            with self.assertRaises(BudgetError):create(b,quantity=quantity)
            self.assertEqual(dumps(b),before)
        for relation in ('missing','ROOT'):
            with self.assertRaises(BudgetError):p.set_report(project(),'P','2026-10-01','','',[dict(relation_id=relation,quantity='1')])
    def test_duplicate_lines_and_reference_rejected(self):
        b=project();rid=create(b)
        with self.assertRaises(BudgetError):create(b,reference=' p1 ')
        with self.assertRaises(BudgetError):p.set_report(b,'P2','2026-10-01','','',[dict(relation_id='A',quantity='1')]*2)
        create(b,reference='P1',date='2027-01-01');p.set_status(b,rid,'cancelled','2026-10-02','Reason')
        with self.assertRaises(BudgetError):create(b)
    def test_confirmed_is_immutable_and_cancellation_needs_reason(self):
        b=project();rid=create(b);p.set_status(b,rid,'posted');before=dumps(b)
        with self.assertRaises(BudgetError):p.set_report(b,'P','2026-10-01','','',[dict(relation_id='A',quantity='1')],rid)
        for day,reason in (('2026-09-01','Reason'),('2026-10-02',''),('invalid','Reason')):
            with self.assertRaises(BudgetError):p.set_status(b,rid,'cancelled',day,reason)
        self.assertEqual(before,dumps(b))
        with self.assertRaises(BudgetError):p.set_status(b,rid,'draft')
    def test_version29_roundtrip_and_corrupt_model_rejected(self):
        b=project();create(b);self.assertEqual(to_dict(b)['version'],29)
        self.assertEqual(p.validate(loads(dumps(b))),p.validate(b))
        data=p.validate(b);data[0]['lines'][0]['relation_id']='missing';b.project_metadata[p.KEY]=json.dumps(data)
        with self.assertRaises(StorageError):dumps(b)
    def test_command_history(self):
        s=ProjectSession(project());s.execute('production.report.set',dict(reference='P',date='2026-10-01',team='',note='',lines=[dict(relation_id='A',quantity='1')]))
        rid=p.validate(s.budget)[0]['id'];s.execute('production.report.status',dict(report_id=rid,status='posted'))
        self.assertEqual(p.validate(s.undo())[0]['status'],'draft');s.redo();self.assertEqual(p.validate(s.budget)[0]['status'],'posted')
    def test_report_export_escapes_text(self):
        from openpresto.reports import report_html,report_csv
        b=project();create(b,reference='<script>')
        self.assertIn('&lt;script&gt;',report_html(b,'partes_obra'));self.assertIn('Team A',report_csv(b,'partes_obra'))

if __name__=='__main__':unittest.main()
