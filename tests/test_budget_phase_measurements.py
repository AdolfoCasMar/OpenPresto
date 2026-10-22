import json,struct,unittest
from decimal import Decimal
from openpresto import budget_phase_measurements as phases
from openpresto.pzh_importer import _Reader,_import,HEADER_BYTES
from openpresto.pzh_archive import pzh_source_bytes
from openpresto.storage import dumps,loads,to_dict,StorageError
from openpresto.calculations import calculator_for
from openpresto.commands import ProjectSession,execute
from openpresto.budget import BudgetError
from test_pzh_percentage_amount import fixture as budget_fixture


def fixture(bad=False):
    raw=budget_fixture();reader=_Reader(raw);boundary=HEADER_BYTES+4+len(reader.config);out=bytearray(raw[:boundary]);measurements=[]
    for i,n in enumerate((1,2)):
        body=bytes((0,))+b'ROOT'.ljust(13,b' ')+b'ITEM'.ljust(13,b' ')+b'  '+bytes((i+1,))+bytes((12,))+struct.pack('<d',n)
        if bad and i==1:body+=bytes((1,3))
        measurements.append(struct.pack('<III',len(body),i,i)+body)
    for table in range(24):
        count,start,end=reader.tables[table];body=raw[start:end]
        if table==4:count=2;body=b''.join(measurements)
        begin=len(out);out+=body;struct.pack_into('<III',out,34+table*88,count,begin,len(out))
    return bytes(out)


class BudgetPhaseTests(unittest.TestCase):
    def test_all_phases_copy_without_changing_active_quantities(self):
        raw=fixture();b=_import(raw,'own.pzh').budget;before=calculator_for(b).total();phases.copy_source(b)
        data=phases.state(b);self.assertEqual(data['approved_through'],1);self.assertIsNone(data['active_through']);self.assertEqual([r['phase'] for r in data['lines']],[1,2]);self.assertEqual(before,Decimal('10.43'));self.assertEqual(calculator_for(b).total(),before)
        restored=loads(dumps(b));self.assertEqual(to_dict(b)['version'],37);self.assertEqual(phases.state(restored),data);self.assertEqual(pzh_source_bytes(restored),raw)
    def test_edit_apply_undo_redo_preserves_source_approval(self):
        b=_import(fixture(),'own.pzh').budget;s=ProjectSession(b);s.execute('budget.phases.copy_pzh');s.execute('budget.phases.line.edit',{'line_id':'1','changes':{'n_lines':'3'}})
        self.assertEqual(calculator_for(s.budget).total(),Decimal('10.43'))
        s.execute('budget.phases.apply',{'phase':2});self.assertEqual(calculator_for(s.budget).total(),Decimal('41.72'));self.assertEqual(phases.state(s.budget)['approved_through'],1);self.assertEqual(phases.state(s.budget)['active_through'],2)
        s.undo();self.assertEqual(calculator_for(s.budget).total(),Decimal('10.43'));s.redo();self.assertEqual(calculator_for(s.budget).total(),Decimal('41.72'))
        s.execute('budget.phases.apply',{'phase':1});self.assertEqual(calculator_for(s.budget).total(),Decimal('10.43'))
    def test_invalid_edits_and_failed_source_conversion_are_atomic(self):
        b=_import(fixture(),'own.pzh').budget;phases.copy_source(b);before=dumps(b)
        for changes in ({'n_lines':'NaN'},{'phase':99},{'length':'1e100'},{'formula':'UNKNOWN'}):
            with self.subTest(changes=changes),self.assertRaises(BudgetError):phases.edit_line(b,'1',changes)
            self.assertEqual(dumps(b),before)
        broken=_import(fixture(True),'bad-later-phase.pzh').budget
        with self.assertRaises(BudgetError):phases.copy_source(broken)
        self.assertNotIn(phases.KEY,broken.project_metadata)
    def test_copy_is_idempotent_and_direct_apply_returns_independent_project(self):
        b=_import(fixture(),'own.pzh').budget;phases.copy_source(b);phases.edit_line(b,'1',{'comment':'Native edit'});before=dumps(b);phases.copy_source(b);self.assertEqual(dumps(b),before)
        updated=phases.apply_through(b,2);self.assertEqual(dumps(b),before);self.assertEqual(calculator_for(updated).total(),Decimal('31.29'))
    def test_report_and_invalid_native_link(self):
        from openpresto.reports import report_table
        b=_import(fixture(),'own.pzh').budget;phases.copy_source(b);self.assertEqual(len(report_table(b,'mediciones_fases')[1]),2)
        data=phases.state(b);data['lines'][0]['relation_id']='missing';b.project_metadata[phases.KEY]=json.dumps(data)
        with self.assertRaises(StorageError):dumps(b)
    def test_automatic_conversion_includes_all_budget_phases(self):
        b=_import(fixture(),'own.pzh',native_modules=True).budget;self.assertEqual(len(phases.state(b)['lines']),2)

    def test_later_only_relationship_does_not_fall_back_to_manual_quantity(self):
        from openpresto.budget import BudgetConcept,BudgetRelation
        b=_import(fixture(),'own.pzh').budget;phases.copy_source(b)
        b.add_concept(BudgetConcept('FUTURE',base_price=Decimal(2)))
        b.add_relation(BudgetRelation('ROOT','FUTURE',Decimal(5),2,'future'))
        data=phases.state(b);row=dict(data['lines'][1]);row.update(id='99',relation_id='future');data['lines'].append(row)
        b.project_metadata[phases.KEY]=json.dumps(data)
        applied=phases.apply_through(b,1)
        self.assertEqual(applied.relation_quantity('future'),Decimal(0))
        self.assertEqual(b.relation_quantity('future'),Decimal(5))

    def test_preview_is_read_only_and_does_not_sum_nested_amount_changes(self):
        b=_import(fixture(),'own.pzh').budget;phases.copy_source(b)
        data=phases.state(b);row=dict(data['lines'][1]);row.update(id='2',relation_id='pzh-r1',n_lines='2');data['lines'].append(row)
        b.project_metadata[phases.KEY]=json.dumps(data);before=dumps(b)
        view=phases.preview(b,2)
        self.assertEqual(dumps(b),before)
        self.assertEqual(view['before_total'],Decimal('10.43'))
        self.assertEqual(view['after_total'],Decimal('62.61'))
        self.assertEqual(view['delta_total'],Decimal('52.18'))
        self.assertEqual(view['changed_relations'],2)
        self.assertNotEqual(sum(r[-1] for r in view['rows']),view['delta_total'])

    def test_clear_copy_retains_applied_budget_and_undo_restores_editable_phases(self):
        b=_import(fixture(),'own.pzh').budget;phases.copy_source(b);s=ProjectSession(b)
        s.execute('budget.phases.apply',{'phase':2});before=calculator_for(s.budget).total();raw=pzh_source_bytes(s.budget)
        s.execute('budget.phases.clear');self.assertIsNone(phases.state(s.budget));self.assertEqual(calculator_for(s.budget).total(),before);self.assertEqual(pzh_source_bytes(s.budget),raw)
        s.undo();self.assertEqual(phases.state(s.budget)['active_through'],2)
