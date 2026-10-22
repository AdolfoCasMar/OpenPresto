import os,unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from openpresto.mdi_workspace import PrestoWorkspace
from openpresto.budget import BudgetMeasurement
from openpresto.bc3_measurements import parse_measurement
from openpresto.storage import dumps
from test_production import project


class OperationResultsVisibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setOrganizationName('OpenPrestoTests');cls.app.setApplicationName('OperationResultsVisibility')
    def setUp(self):
        self.h=PrestoWorkspace();self.h.budget=project();self.h._reset_history();self.h._open_views()
    def tearDown(self):self.h.dirty=False;self.h.close()
    def copy(self,source='A',destination='B'):
        labels={r.id:f'{r.parent_code} → {r.child_code} [{r.id}]' for r in self.h.budget.relations}
        with patch('openpresto.mdi_workspace.QInputDialog.getItem',side_effect=[(labels[source],True),(labels[destination],True)]):self.h.copy_relation_measurements()
    def key(self):return self.h._measurement_keys[self.h.measurements_table.currentRow()]
    def test_moving_to_another_parent_reveals_exact_relation_and_undo_restores_level(self):
        h=self.h;h.search.setText('Wall');h.show_panel('precios');h.prices.setCurrentCell(0,0)
        with patch('openpresto.mdi_workspace.QInputDialog.getItem',return_value=('B',True)),patch('openpresto.mdi_workspace.QInputDialog.getInt',return_value=(1,True)):h.move_active_relation()
        self.assertEqual(h.current_code,'B');self.assertEqual(h.selected_relation,'A');self.assertEqual(h.search.text(),'');self.assertFalse(h.prices.isRowHidden(h.prices.currentRow()));self.assertEqual(len(h._undo),1)
        h.undo();self.assertEqual(h.current_code,'ROOT');self.assertEqual(h.search.text(),'Wall');h.redo();self.assertEqual(h.current_code,'B');self.assertEqual(h.selected_relation,'A')
    def test_duplicate_selects_catalogue_copy_without_adding_it_to_budget(self):
        h=self.h
        with patch('openpresto.mdi_workspace.QInputDialog.getText',return_value=('COPY',True)):h.duplicate_active_concept()
        self.assertEqual(h.active_concept,'COPY');self.assertIs(h.mdi.activeSubWindow(),h.windows['conceptos']);self.assertEqual(h.concepts_table.item(h.concepts_table.currentRow(),0).text(),'COPY');self.assertFalse(any(r.child_code=='COPY' for r in h.budget.relations));self.assertEqual(len(h._undo),1)
        h.undo();self.assertNotIn('COPY',h.budget.concepts);h.redo();self.assertEqual(h.active_concept,'COPY')
    def test_native_copy_reveals_destination_and_new_measurement_identity(self):
        h=self.h;h.budget.add_measurement(BudgetMeasurement('A',comment='Copied',n_lines='2',id='source'));h.budget.add_measurement(BudgetMeasurement('B',comment='Replaced',id='old'));h._reset_history();h.refresh();self.copy()
        self.assertEqual(h.selected_relation,'B');self.assertEqual(h.budget.relation_quantity('B'),2);self.assertEqual(h.measurements_table.item(h.measurements_table.currentRow(),0).text(),'Copied');self.assertNotEqual(self.key(),('native','source'));self.assertIs(h.mdi.activeSubWindow(),h.windows['mediciones']);self.assertEqual(len(h._undo),1)
        h.undo();self.assertIn('old',{m.id for m in h.budget.measurements});h.redo();self.assertEqual(h.selected_relation,'B');self.assertEqual(h.measurements_table.item(h.measurements_table.currentRow(),0).text(),'Copied')
    def test_bc3_copy_selects_first_destination_line(self):
        h=self.h;body=chr(92).join(('', 'BC3 source','3','','',''))+chr(92);h.budget.bc3_measurements['A']=parse_measurement('ROOT'+chr(92)+'A||3|'+body+'|');h._reset_history();h.refresh();self.copy()
        self.assertEqual(self.key(),('B',0));self.assertEqual(h.measurements_table.item(h.measurements_table.currentRow(),0).text(),'BC3 source');self.assertFalse(h.measurements_table.isRowHidden(h.measurements_table.currentRow()))
    def test_copy_without_lines_clears_destination_selection(self):
        h=self.h;h.budget.add_measurement(BudgetMeasurement('B',comment='Remove',id='old'));h._reset_history();h.refresh();self.copy();self.assertEqual(h.selected_relation,'B');self.assertEqual(h.measurements_table.currentRow(),-1);self.assertEqual(h.budget.relation_quantity('B'),10)
    def test_rejected_duplicate_and_cycle_do_not_navigate_or_add_history(self):
        h=self.h;before=dumps(h.budget);context=h._history_context()
        with patch('openpresto.mdi_workspace.QInputDialog.getText',return_value=('B',True)),patch.object(h,'_error') as error:h.duplicate_active_concept();error.assert_called_once()
        with patch('openpresto.mdi_workspace.QInputDialog.getItem',return_value=('A',True)),patch('openpresto.mdi_workspace.QInputDialog.getInt',return_value=(1,True)),patch.object(h,'_error') as error:h.move_active_relation();error.assert_called_once()
        self.assertEqual(dumps(h.budget),before);self.assertEqual(h._history_context(),context);self.assertEqual(len(h._undo),0)
    def test_cancelled_operations_leave_model_and_context_unchanged(self):
        h=self.h;before=dumps(h.budget);context=h._history_context()
        with patch('openpresto.mdi_workspace.QInputDialog.getText',return_value=('',False)):h.duplicate_active_concept()
        with patch('openpresto.mdi_workspace.QInputDialog.getItem',return_value=('',False)):h.move_active_relation();h.copy_relation_measurements()
        self.assertEqual(dumps(h.budget),before);self.assertEqual(h._history_context(),context);self.assertEqual(len(h._undo),0)
