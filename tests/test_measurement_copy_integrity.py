import unittest
from openpresto.budget import BudgetMeasurement
from openpresto.bc3_measurements import parse_measurement
from openpresto.editing_services import copy_measurements,replace_text,reorder_children
from openpresto.hierarchy_services import move_relation
from openpresto.measurement_operations import insert_subtotal,native_display
from openpresto.storage import dumps,loads
from openpresto.commands import ProjectSession
from test_production import project


class MeasurementCopyIntegrityTests(unittest.TestCase):
    def test_replaced_native_subtotal_metadata_is_removed_and_new_ids_keep_kinds(self):
        b=project();b.add_measurement(BudgetMeasurement('A',n_lines='3',id='source'));b=insert_subtotal(b,'A');b=insert_subtotal(b,'B',True)
        old=next(m.id for m in b.measurements if m.relation_id=='B');before=dumps(b);result=loads(dumps(copy_measurements(b,'A','B')))
        self.assertNotIn('measurement_kind:'+old,result.project_metadata)
        rows=[m for m in result.measurements if m.relation_id=='B'];self.assertEqual(len(rows),2);self.assertEqual(result.relation_quantity('B'),3);self.assertEqual(native_display(result,rows[-1].id)[1],3)
        self.assertEqual(result.project_metadata['measurement_kind:'+rows[-1].id],'1');self.assertEqual(dumps(b),before)
    def test_bc3_replacement_also_cleans_removed_native_metadata(self):
        b=insert_subtotal(project(),'B',True);old=b.measurements[0].id
        body=chr(92).join(('', 'BC3','2','','',''))+chr(92);b.bc3_measurements['A']=parse_measurement('ROOT'+chr(92)+'A|phase|2|'+body+'|')
        r=loads(dumps(copy_measurements(b,'A','B')));self.assertNotIn('measurement_kind:'+old,r.project_metadata);self.assertEqual(r.bc3_measurements['B'].reference,'ROOT'+chr(92)+'B');self.assertEqual(r.bc3_measurements['B'].phase,'phase');self.assertEqual(r.relation_quantity('B'),2)
    def test_copy_without_lines_removes_old_subtotal_metadata(self):
        b=insert_subtotal(project(),'B');old=b.measurements[0].id;r=copy_measurements(b,'A','B');self.assertNotIn('measurement_kind:'+old,r.project_metadata);self.assertEqual(r.relation_quantity('B'),10)
    def test_moving_bc3_relationship_updates_reference_after_save_and_reopen(self):
        b=project();b.project_metadata['engine']='native-v1';b.bc3_zero_dimensions_as_blank=True;body=chr(92).join(('', 'Moved','2','','',''))+chr(92);b.bc3_measurements['A']=parse_measurement('ROOT'+chr(92)+'A|phase|2|'+body+'|',zero_dimensions_as_blank=True,native_formulas=True)
        original=b.bc3_measurements['A'];r=loads(dumps(move_relation(b,'A','B',1)));record=r.bc3_measurements['A'];self.assertEqual(record.reference,'B'+chr(92)+'A');self.assertTrue(record.raw_body.startswith(record.reference+'|'));self.assertEqual(record.phase,original.phase);self.assertEqual(record.raw_body.split('|',1)[1],original.raw_body.split('|',1)[1]);self.assertEqual(record.declared_quantity,original.declared_quantity);self.assertEqual(record.lines,original.lines);self.assertTrue(record.zero_dimensions_as_blank);self.assertTrue(record.native_formulas);self.assertEqual(r.relation_quantity('A'),2);self.assertEqual(b.bc3_measurements['A'],original)
    def test_editing_helpers_share_large_immutable_source_and_isolate_mutable_data(self):
        b=project();text='Preserved source ' * 10000;b.project_metadata['large-original']=text
        for result in (copy_measurements(b,'A','B'),replace_text(b,'Wall','Updated'),reorder_children(b,'ROOT')):
            self.assertTrue(result.project_metadata['large-original'] is text);result.project_metadata['changed']='yes';self.assertNotIn('changed',b.project_metadata)
    def test_copy_metadata_cleanup_is_undoable(self):
        b=insert_subtotal(project(),'B',True);old=b.measurements[0].id;session=ProjectSession(b);session.execute('budget.measurement.copy',dict(source='A',destination='B'));self.assertNotIn('measurement_kind:'+old,session.budget.project_metadata);session.undo();self.assertEqual(session.budget.project_metadata['measurement_kind:'+old],'2');session.redo();self.assertNotIn('measurement_kind:'+old,session.budget.project_metadata)
