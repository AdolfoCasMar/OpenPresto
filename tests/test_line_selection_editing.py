import os,unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QItemSelectionModel
from openpresto.mdi_workspace import PrestoWorkspace
from openpresto.budget import BudgetMeasurement,BudgetConcept
from openpresto.bc3_measurements import parse_measurement
from openpresto.storage import dumps
from test_production import project


class LineSelectionEditingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setOrganizationName('OpenPrestoTests');cls.app.setApplicationName('LineSelectionEditing')
    def setUp(self):
        self.h=PrestoWorkspace();self.h.budget=project();self.h._reset_history();self.h._open_views()
    def tearDown(self):self.h.dirty=False;self.h.close()
    def native(self):
        h=self.h
        for rid,label,identity in [('A','One','one'),('B','Hidden other relation','other'),('A','Two','two'),('A','Three','three')]:h.budget.add_measurement(BudgetMeasurement(rid,comment=label,n_lines='1',id=identity))
        h._reset_history();h.refresh();h.show_panel('mediciones');self.select_key(('native','one'))
    def bc3(self):
        h=self.h;body=chr(92).join(tuple(v for label in ('One','Two','Three') for v in ('',label,'1','','','')))+chr(92)
        h.budget.bc3_measurements['A']=parse_measurement('ROOT'+chr(92)+'A||3|'+body+'|');h._reset_history();h.refresh();h.show_panel('mediciones');self.select_key(('A',0))
    def select_key(self,key):self.h.measurements_table.setCurrentCell(self.h._measurement_keys.index(key),0)
    def key(self):return self.h._measurement_keys[self.h.measurements_table.currentRow()]
    def test_bc3_moving_follows_the_line_at_its_new_position(self):
        self.bc3();h=self.h;h.move_measurement_line(1);self.assertEqual(self.key(),('A',1));self.assertEqual(h.measurements_table.item(h.measurements_table.currentRow(),0).text(),'One');self.assertFalse(h.measurements_table.isRowHidden(h.measurements_table.currentRow()));h.move_measurement_line(-1);self.assertEqual(self.key(),('A',0))
    def test_native_moving_respects_relation_group_and_identity(self):
        self.native();h=self.h;h.move_measurement_line(1);self.assertEqual(self.key(),('native','one'));self.assertEqual([m.id for m in h.budget.measurements if m.relation_id=='A'],['two','one','three']);self.assertTrue(h.measurements_table.isRowHidden(h._measurement_keys.index(('native','other'))));h.undo();self.assertEqual([m.id for m in h.budget.measurements if m.relation_id=='A'],['one','two','three'])
    def test_native_deletion_selects_visible_neighbor_not_hidden_relation(self):
        self.native();h=self.h;self.select_key(('native','two'));h.delete_selected();self.assertEqual(self.key(),('native','three'));self.assertFalse(h.measurements_table.isRowHidden(h.measurements_table.currentRow()));h.delete_selected();self.assertEqual(self.key(),('native','one'));h.delete_selected();self.assertEqual(h.measurements_table.currentRow(),-1);self.assertEqual(h.budget.relation_quantity('A'),0);self.assertEqual([m.id for m in h.budget.measurements],['other'])
    def test_bc3_delete_last_selects_previous_visible_line(self):
        self.bc3();h=self.h;self.select_key(('A',2));h.delete_selected();self.assertEqual(self.key(),('A',1));self.assertEqual(h.measurements_table.item(h.measurements_table.currentRow(),0).text(),'Two');h.undo();self.assertEqual(len(h.budget.bc3_measurements['A'].lines),3)
    def test_multi_delete_is_one_undo_and_chooses_neighbor(self):
        self.native();h=self.h;t=h.measurements_table;self.select_key(('native','two'));t.selectionModel().select(t.model().index(h._measurement_keys.index(('native','three')),0),QItemSelectionModel.SelectionFlag.Select|QItemSelectionModel.SelectionFlag.Rows);before=len(h._undo);h.delete_selected();self.assertEqual(self.key(),('native','one'));self.assertEqual(len(h._undo),before+1);h.undo();self.assertEqual(len(h.budget.measurements),4)
    def test_delete_with_no_selection_or_hidden_current_row_is_noop(self):
        self.native();h=self.h;before=dumps(h.budget);h.measurements_table.clearSelection();h.delete_selected();self.assertEqual(dumps(h.budget),before);self.select_key(('native','other'));h.move_measurement_line(1);h.delete_selected();self.assertEqual(dumps(h.budget),before)
    def test_boundaries_and_invalid_moves_do_not_change_history(self):
        self.bc3();h=self.h;before=dumps(h.budget);n=len(h._undo);h.move_measurement_line(-1);self.assertEqual(dumps(h.budget),before);self.assertEqual(len(h._undo),n)
        with patch.object(h,'_error') as error:h.move_measurement_line(2);error.assert_called_once()
        self.assertEqual(dumps(h.budget),before);self.assertEqual(self.key(),('A',0))
    def test_budget_deletion_preserves_search_and_selects_neighbor(self):
        h=self.h;h.search.setText('Wall');h.show_panel('precios');h.prices.setCurrentCell(0,0);h.delete_selected();self.assertEqual(h.search.text(),'Wall');self.assertEqual(h.prices.currentRow(),-1);self.assertEqual([r.id for r in h.budget.relations],['B'])
    def test_catalogue_delete_selects_remaining_neighbor(self):
        h=self.h;h.budget.add_concept(BudgetConcept('UNUSED'));h._reset_history();h.refresh();h.show_panel('conceptos');h.concepts_table.setCurrentCell(3,0);h.delete_selected();self.assertNotIn('UNUSED',h.budget.concepts);self.assertEqual(h.concepts_table.currentRow(),2)
