"""Resource costs retain explicit rates and never post financial documents."""
import json,unittest
from decimal import Decimal,localcontext
from dataclasses import replace
from openpresto.budget import BudgetConcept,BudgetError
from openpresto import resource_hours as h
from openpresto.storage import dumps,loads,to_dict,StorageError
from openpresto.commands import ProjectSession
from openpresto.reports import report_table,report_html
from test_production import project as production_project


def project():
    b=production_project()
    b.add_concept(BudgetConcept('L','h','Oficial','mano de obra',Decimal(25)))
    b.add_concept(BudgetConcept('M','h','Excavadora','maquinaria',Decimal(80)))
    return b


def create(b,reference='H1',resource='L',hours='8',rate='25',relation='A',day='2026-10-01'):
    h.set_entry(b,reference,day,'Equipo A',resource,hours,rate,relation,'Example')
    return h.validate(b)[-1]['id']


class ResourceHoursTests(unittest.TestCase):
    def test_confirmed_costs_group_by_resource_and_relation(self):
        b=project();first=create(b);second=create(b,'H2','M','2','80',None)
        for rid in (first,second):h.set_status(b,rid,'posted')
        create(b,'DRAFT',hours='100')
        v=h.snapshot(b,'2026-10-31');self.assertEqual(v['total'],Decimal(360));self.assertEqual(v['count'],2);self.assertEqual(v['unassigned'],Decimal(160))
        self.assertEqual(v['resources'][0][-2:],(Decimal(8),Decimal(200)))
        self.assertEqual(v['work_items'][0][2],'Sin asignar');self.assertEqual(h.snapshot(b,'2026-09-30')['total'],0)
    def test_repeated_work_code_keeps_relation_assignments_separate(self):
        from openpresto.budget import BudgetRelation,BudgetConcept
        b=project();b.add_concept(BudgetConcept('CH2',nature='capítulo'))
        b.add_relation(BudgetRelation('ROOT','CH2',Decimal(1),3,'root-ch2'))
        b.add_relation(BudgetRelation('CH2','A',Decimal(1),1,'A-again',Decimal(3)))
        first=create(b,relation='A');second=create(b,reference='H2',relation='A-again')
        for rid in (first,second):h.set_status(b,rid,'posted')
        rows=h.snapshot(b,'2026-10-31')['work_items']
        self.assertEqual([r[0] for r in rows],['A','A-again'])
        self.assertEqual([r[-1] for r in rows],[Decimal(200),Decimal(200)])
        self.assertEqual([r[-2] for r in rows],[Decimal(8),Decimal(8)])
    def test_saved_rate_survives_budget_price_changes(self):
        b=project();rid=create(b);h.set_status(b,rid,'posted')
        b.concepts['L']=replace(b.concepts['L'],base_price=Decimal(1000))
        self.assertEqual(h.snapshot(b,'2026-10-31')['total'],200)
        self.assertEqual(h.validate(loads(dumps(b)))[0]['rate'],'25')
    def test_commercial_rounding_is_per_entry_and_context_independent(self):
        b=project()
        for i in range(2):h.set_status(b,create(b,str(i),hours='1',rate='.005'),'posted')
        with localcontext() as context:
            context.prec=3
            self.assertEqual(h.snapshot(b,'2026-10-31')['total'],Decimal('.02'))
        self.assertEqual(h.report_rows(b)[0][10],Decimal('.01'))
    def test_zero_rate_and_team_hours_over24_are_explicitly_allowed(self):
        b=project();rid=create(b,hours='40',rate='0');h.set_status(b,rid,'posted')
        self.assertEqual(h.snapshot(b,'2026-10-31')['resources'][0][-2:],(Decimal(40),Decimal('0.00')))
    def test_invalid_values_do_not_mutate_project(self):
        for field,values in [('hours',['0','-1','NaN','Infinity','1e13','1e-13',True,1.5]),('rate',['-1','NaN','1e13','1e-13',True,1.5])]:
            for value in values:
                b=project();before=dumps(b)
                with self.assertRaises(BudgetError):create(b,**{field:value})
                self.assertEqual(dumps(b),before)
    def test_only_hourly_labour_or_equipment_and_valid_targets(self):
        b=project();b.add_concept(BudgetConcept('DAY','d','Machine day','maquinaria',Decimal(80)))
        for code in ('A','B','ROOT','missing','DAY'):
            with self.assertRaises(BudgetError):create(b,resource=code)
        with self.assertRaises(BudgetError):create(b,relation='missing')
        with self.assertRaises(BudgetError):create(b,relation='L')
    def test_lifecycle_and_reference_reservation(self):
        b=project();rid=create(b);h.set_status(b,rid,'posted');before=dumps(b)
        with self.assertRaises(BudgetError):h.set_entry(b,'H1','2026-10-01','','L','9','25',entry_id=rid)
        for day,reason in [('2026-09-01','Reason'),('2026-10-02',''),('bad','Reason')]:
            with self.assertRaises(BudgetError):h.set_status(b,rid,'cancelled',day,reason)
        self.assertEqual(dumps(b),before)
        h.set_status(b,rid,'cancelled','2026-10-02','Correction')
        self.assertEqual(h.snapshot(b,'2026-10-31')['total'],0)
        self.assertEqual(h.report_rows(b)[0][-2:],('2026-10-02','Correction'))
        with self.assertRaises(BudgetError):create(b,reference=' h1 ')
        with self.assertRaises(BudgetError):h.set_status(b,rid,'posted')
        create(b,day='2027-01-01')
    def test_native_storage30_and_corrupt_data(self):
        b=project();create(b);self.assertEqual(to_dict(b)['version'],30)
        self.assertEqual(h.report_rows(loads(dumps(b))),h.report_rows(b))
        data=h.validate(b);data[0]['resource_code']='missing';b.project_metadata[h.KEY]=json.dumps(data)
        with self.assertRaises(StorageError):dumps(b)
    def test_no_budget_production_certification_or_cash_changes(self):
        b=project();before=dumps(b);rid=create(b);h.set_status(b,rid,'posted')
        self.assertEqual(set(b.project_metadata),{h.KEY});del b.project_metadata[h.KEY]
        self.assertEqual(dumps(b),before)
    def test_commands_are_atomic_and_undoable(self):
        s=ProjectSession(project());params=dict(reference='P',date='2026-10-01',team='',resource_code='L',hours='1',rate='10')
        s.execute('resource.hours.set',params);rid=h.validate(s.budget)[0]['id']
        s.execute('resource.hours.status',dict(entry_id=rid,status='posted'))
        self.assertEqual(h.validate(s.undo())[0]['status'],'draft');s.redo();self.assertEqual(h.validate(s.budget)[0]['status'],'posted')
        before=dumps(s.budget)
        with self.assertRaises(BudgetError):s.execute('resource.hours.set',dict(params,reference='FAIL',hours='NaN'))
        self.assertEqual(dumps(s.budget),before)
    def test_reports_and_bad_parameters(self):
        b=project();rid=create(b,reference='<script>');h.set_status(b,rid,'posted')
        self.assertIn('&lt;script&gt;',report_html(b,'horas_recursos'))
        self.assertEqual(report_table(b,'horas_recursos:2026-10-31:recursos')[1][0][-1],200)
        self.assertEqual(report_table(b,'horas_recursos:2026-10-31:partidas')[1][0][0],'A')
        for kind in ('horas_recursos:bad:recursos','horas_recursos:2026-10-31:bad','horas_recursos:2026-10-31:recursos:extra'):
            with self.assertRaises(ValueError):report_table(b,kind)

if __name__=='__main__':unittest.main()
