import unittest
from decimal import Decimal
from dataclasses import replace
from unittest.mock import patch
from openpresto.budget import Budget,BudgetConcept,BudgetRelation,BudgetMeasurement,BudgetError
from openpresto.calculations import calculator_for,BudgetCalculator,CalculationPolicy
from openpresto.bc3_measurements import parse_measurement
from openpresto.storage import dumps,loads
from test_production import project


class NativeQuantityBatchTests(unittest.TestCase):
    def fixture(self):
        b=project();b.project_metadata['engine']='native-v1';b.concepts['A']=replace(b.concepts['A'],measurement_decimals=2)
        b.add_measurement(BudgetMeasurement('A',n_lines='2',length='1.235',id='one'));b.add_measurement(BudgetMeasurement('B',n_lines='4',id='other'));b.add_measurement(BudgetMeasurement('A',n_lines='0',id='subtotal'));b.project_metadata['measurement_kind:subtotal']='1'
        return b
    def test_quantities_totals_and_precision_match_existing_budget_rules(self):
        b=self.fixture();before=dumps(b)
        for root_decimals in (None,0,2):
            b.root_quantity_decimals=root_decimals
            for policy in (None,CalculationPolicy(2,3,2,root_decimals)):
                c=calculator_for(b,policy);old=BudgetCalculator(b,policy)
                self.assertEqual(c.total(),old.total())
                for r in b.relations:self.assertEqual(c.quantity(r.id),old.quantity(r.id));self.assertEqual(c.relation(r.id),old.relation(r.id))
        b.root_quantity_decimals=None;self.assertEqual(dumps(b),before)
    def test_batch_reuses_quantities_and_releases_them_after_scope(self):
        b=self.fixture();c=calculator_for(b)
        with patch.object(b,'measurement_partial',wraps=b.measurement_partial) as partial:
            with c.batch():
                self.assertEqual(c.quantity('A'),Decimal('2.480'));c.total()
                calls=partial.call_count
                with c.batch():c.quantity('A');c.quantity('B');c.total()
                self.assertEqual(partial.call_count,calls)
        self.assertEqual(c._quantity_cache,{});self.assertEqual(c._measurement_rows,{})
    def test_reused_calculator_observes_measurement_edits_additions_and_removals(self):
        b=self.fixture();c=calculator_for(b);self.assertEqual(c.quantity('A'),Decimal('2.480'))
        b.measurements[0]=replace(b.measurements[0],n_lines='4');self.assertEqual(c.quantity('A'),Decimal('4.960'))
        b.add_measurement(BudgetMeasurement('A',n_lines='-1',id='negative'));self.assertEqual(c.quantity('A'),Decimal('3.960'))
        b.measurements=[m for m in b.measurements if m.relation_id!='A'];b._measurements_by_id={m.id for m in b.measurements};self.assertEqual(c.quantity('A'),Decimal('10.000'))
    def test_bc3_quantity_and_direct_fallback_remain_unchanged(self):
        b=project();b.project_metadata['engine']='native-v1';body=chr(92).join(('', 'BC3','2.3456','','',''))+chr(92);b.bc3_measurements['A']=parse_measurement('ROOT'+chr(92)+'A||2.3456|'+body+'|')
        c=calculator_for(loads(dumps(b)));self.assertEqual(c.quantity('A'),Decimal('2.350'));self.assertEqual(c.quantity('B'),Decimal('10.000'))
        b.bc3_measurements['A']=parse_measurement('ROOT'+chr(92)+'A|||');self.assertEqual(calculator_for(b).quantity('A'),Decimal('10.000'))
    def test_exception_drops_cached_values_and_next_call_sees_current_data(self):
        b=self.fixture();c=calculator_for(b)
        with self.assertRaises(BudgetError),c.batch():c.total();c.quantity('missing')
        self.assertEqual(c._quantity_cache,{});self.assertEqual(c._measurement_rows,{})
        b.measurements[0]=replace(b.measurements[0],n_lines='1');self.assertEqual(c.quantity('A'),Decimal('1.240'))
    def test_many_relationships_index_measurements_once_per_evaluation(self):
        b=Budget();b.project_metadata['engine']='native-v1';b.add_concept(BudgetConcept('ROOT'));b.add_concept(BudgetConcept('A',base_price='20'));b.set_root('ROOT')
        for i in range(300):
            rid=str(i);b.add_relation(BudgetRelation('ROOT','A',position=i+1,id=rid));b.add_measurement(BudgetMeasurement(rid,n_lines='2.5',id='m'+rid))
        class CountedRows(list):
            scans=0
            def __iter__(self):self.scans+=1;return super().__iter__()
        b.measurements=CountedRows(b.measurements);c=calculator_for(b)
        with c.batch():self.assertEqual(c.total(),Decimal('15000.00'));self.assertEqual(c.quantity('299'),Decimal('2.500'))
        self.assertEqual(b.measurements.scans,1)
