import unittest,json
from dataclasses import replace
from decimal import Decimal
from openpresto import budget_baselines as b
from openpresto.budget import Budget,BudgetConcept,BudgetRelation,BudgetError
from openpresto.storage import dumps,loads,to_dict,StorageError
from openpresto.commands import ProjectSession
from openpresto.reports import report_table,report_html
from test_production import project


def freeze(p):
    b.freeze(p,'BASE','2026-10-01','Reference');return b.validate(p)[0]['id']


class BudgetBaselinesTests(unittest.TestCase):
    def test_price_quantity_and_factor_changes_against_saved_values(self):
        p=project();rid=freeze(p);before=p.project_metadata[b.KEY]
        p.concepts['A']=replace(p.concepts['A'],base_price=Decimal(25));p.relations=[replace(r,quantity=Decimal(12),factor=Decimal(2)) if r.id=='A' else r for r in p.relations]
        p=loads(dumps(p));v=b.comparison(p,rid,True);self.assertEqual(v['base_total'],500);self.assertEqual(v['current_total'],900);self.assertEqual(v['delta_total'],400)
        self.assertEqual(len(v['rows']),1);r=v['rows'][0];self.assertEqual(r[8:16],(Decimal(10),Decimal(12),Decimal(20),Decimal(25),Decimal(1),Decimal(2),Decimal(200),Decimal(600)))
        self.assertEqual(r[-1],'Modificada');self.assertEqual(p.project_metadata[b.KEY],before)
    def test_add_remove_and_historical_relations_without_current_concepts(self):
        p=project();rid=freeze(p);p.relations=[r for r in p.relations if r.id!='B'];del p.concepts['B'];p.add_concept(BudgetConcept('C','m','New','partida',Decimal(5)));p.add_relation(BudgetRelation('ROOT','C',Decimal(2),3,'C'))
        v=b.comparison(loads(dumps(p)),rid,True);rows={r[0]:r for r in v['rows']}
        self.assertEqual(rows['B'][-2:],(Decimal(-300),'Baja'));self.assertEqual(rows['C'][-2:],(Decimal(10),'Alta'));self.assertEqual(v['delta_total'],-290)
    def test_reassigned_identity_is_not_silently_matched_by_code(self):
        p=project();rid=freeze(p);p.add_concept(BudgetConcept('C','m','Changed','partida',Decimal(5)));p.relations=[replace(r,child_code='C') if r.id=='A' else r for r in p.relations]
        self.assertEqual(b.comparison(loads(dumps(p)),rid,True)['rows'][0][-1],'Reasignada')
    def test_summary_and_units_are_visible_changes(self):
        p=project();rid=freeze(p);p.concepts['A']=replace(p.concepts['A'],summary='New description',unit='m')
        row=b.comparison(p,rid,True)['rows'][0];self.assertEqual(row[6:8],('m2','m'));self.assertEqual(row[-1],'Modificada');self.assertEqual(row[-2],0)
    def test_numeric_formatting_alone_is_not_change(self):
        p=project();rid=freeze(p);p.relations=[replace(r,quantity=Decimal('10.000')) for r in p.relations]
        self.assertEqual(b.comparison(loads(dumps(p)),rid,True)['rows'],[])
    def test_roundtrip_container33_and_invalid_model(self):
        p=project();rid=freeze(p);self.assertEqual(to_dict(p)['version'],33);self.assertEqual(b.comparison(loads(dumps(p)),rid),b.comparison(p,rid))
        data=b.validate(p);data[0]['rows'][0]['amount']='NaN';p.project_metadata[b.KEY]=json.dumps(data)
        with self.assertRaises(StorageError):dumps(p)
    def test_capture_readonly_and_budget_state_unchanged(self):
        p=project();before=dumps(p);b.capture(p);self.assertEqual(dumps(p),before);rid=freeze(p);before=dumps(p);b.comparison(p,rid);self.assertEqual(dumps(p),before)
    def test_duplicate_bad_date_missing_root_and_bad_id_rejected(self):
        p=project();rid=freeze(p);before=dumps(p)
        with self.assertRaises(BudgetError):b.freeze(p,' base ','2026-10-02')
        with self.assertRaises(BudgetError):b.freeze(p,'NEW','bad')
        self.assertEqual(before,dumps(p))
        with self.assertRaises(BudgetError):b.freeze(Budget(),'EMPTY','2026-10-01')
        with self.assertRaises(BudgetError):b.comparison(p,'missing')
        with self.assertRaises(BudgetError):b.remove(p,'missing')
    def test_history_can_restore_removed_reference(self):
        s=ProjectSession(project());s.execute('budget.baseline.freeze',dict(reference='BASE',date='2026-10-01'));rid=b.validate(s.budget)[0]['id']
        s.execute('budget.baseline.remove',dict(baseline_id=rid));self.assertEqual(b.validate(s.budget),[]);self.assertEqual(b.validate(s.undo())[0]['id'],rid);s.redo();self.assertEqual(b.validate(s.budget),[])
    def test_reports_preserve_escaped_reference(self):
        p=project();b.freeze(p,'<script>','2026-10-01');rid=b.validate(p)[0]['id'];self.assertIn('&lt;script&gt;',report_html(p,'lineas_base'));self.assertEqual(len(report_table(p,'comparacion_base:'+rid)[1]),2)
        self.assertEqual(report_table(p,'comparacion_base:'+rid+':cambios')[1],[])
        with self.assertRaises(ValueError):report_table(p,'comparacion_base:'+rid+':bad')
    def test_nested_rows_not_summed_as_project_total(self):
        p=project();p.add_concept(BudgetConcept('L','h','Labour','mano de obra',Decimal(4)));p.add_relation(BudgetRelation('A','L',Decimal(2),1,'A-L'));rid=freeze(p)
        self.assertEqual(b.comparison(p,rid)['base_total'],380);self.assertEqual(sum(Decimal(r['amount']) for r in b.validate(p)[0]['rows']),388)

if __name__=='__main__':unittest.main()
