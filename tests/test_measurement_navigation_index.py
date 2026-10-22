import os,unittest
from dataclasses import asdict
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from openpresto.mdi_workspace import PrestoWorkspace
from openpresto.budget import BudgetConcept,BudgetRelation,BudgetMeasurement
from openpresto.bc3_measurements import parse_measurement
from openpresto.storage import dumps
from test_production import project


class MeasurementNavigationIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setOrganizationName('OpenPrestoTests');cls.app.setApplicationName('MeasurementNavigationIndex')
    def setUp(self):
        h=self.h=PrestoWorkspace();h.budget=project();h.budget.add_concept(BudgetConcept('C'));h.budget.add_relation(BudgetRelation('ROOT','C',position=3,id='C'))
        for rid,mid in (('A','a1'),('B','b1'),('A','a2'),('B','b2')):h.budget.add_measurement(BudgetMeasurement(rid,id=mid))
        body=chr(92).join(('', 'BC3','3','','',''))+chr(92);h.budget.bc3_measurements['C']=parse_measurement('ROOT'+chr(92)+'C||3|'+body+'|');h._reset_history();h._open_views()
    def tearDown(self):self.h.dirty=False;self.h.close()
    def visible(self):
        h=self.h;return [key for row,key in enumerate(h._measurement_keys) if not h.measurements_table.isRowHidden(row)]
    def test_initial_filter_and_switch_between_native_and_bc3(self):
        h=self.h;self.assertEqual(self.visible(),[('native','a1'),('native','a2')]);h._reveal_relation('C');self.assertEqual(self.visible(),[('C',0)]);h._reveal_relation('B');self.assertEqual(self.visible(),[('native','b1'),('native','b2')])
    def test_navigation_updates_only_previous_and_destination_rows(self):
        h=self.h;before=dumps(h.budget)
        with patch.object(h.measurements_table,'setRowHidden',wraps=h.measurements_table.setRowHidden) as hide:h._reveal_relation('B');self.assertEqual(hide.call_count,4)
        self.assertEqual(dumps(h.budget),before);self.assertEqual(len(h._undo),0);self.assertFalse(h.dirty)
    def test_repeated_selection_does_not_touch_row_visibility(self):
        h=self.h
        with patch.object(h.measurements_table,'setRowHidden',wraps=h.measurements_table.setRowHidden) as hide:
            h.filter_measurements();h.sync_secondary();h.filter_measurements();self.assertEqual(hide.call_count,0)
        self.assertEqual(self.visible(),[('native','a1'),('native','a2')])
    def test_no_relationship_hides_previous_group_and_can_restore_it(self):
        h=self.h;h.selected_relation=None;h.filter_measurements();self.assertEqual(self.visible(),[]);h._reveal_relation('C');self.assertEqual(self.visible(),[('C',0)])
    def test_add_remove_undo_and_redo_rebuild_groups_without_stale_rows(self):
        h=self.h;h._execute('budget.measurement.add',data=asdict(BudgetMeasurement('A',id='new')));self.assertIn(('native','new'),self.visible())
        h.undo();self.assertNotIn(('native','new'),h._measurement_keys);h.redo();self.assertIn(('native','new'),self.visible())
        h._execute('budget.measurement.remove',keys=[('native','a1')]);self.assertNotIn(('native','a1'),h._measurement_keys);h._reveal_relation('B');self.assertEqual(self.visible(),[('native','b1'),('native','b2')]);h._reveal_relation('A');self.assertEqual(self.visible(),[('native','a2'),('native','new')])
    def test_price_information_and_quantity_editability_stay_correct(self):
        h=self.h
        for row in range(3):
            self.assertIn('m',h.prices.item(row,2).text());self.assertFalse(h.prices.item(row,5).flags() & Qt.ItemFlag.ItemIsEditable)
        h._execute('budget.measurement.remove',keys=[('native','a1'),('native','a2')]);row=next(i for i,r in enumerate(h._visible_relations) if r.id=='A');self.assertNotIn('m',h.prices.item(row,2).text());self.assertTrue(h.prices.item(row,5).flags() & Qt.ItemFlag.ItemIsEditable)
