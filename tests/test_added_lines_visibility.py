import os,unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication,QLineEdit
from PySide6.QtCore import QTimer
from openpresto.mdi_workspace import PrestoWorkspace
from openpresto.storage import dumps
from openpresto.bc3_measurements import parse_measurement
from test_production import project


class AddedLinesVisibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setOrganizationName('OpenPrestoTests');cls.app.setApplicationName('AddedLinesVisibility')
    def setUp(self):
        self.h=PrestoWorkspace();self.h.budget=project();self.h._reset_history();self.h._open_views()
    def tearDown(self):self.h.dirty=False;self.h.close()
    def relation(self,parent='A',child='B',cancel=False):
        def complete():
            d=QApplication.activeModalWidget();d.parent_code.setCurrentText(parent);d.child_code.setCurrentText(child);d.quantity.setText('2,5');d.reject() if cancel else d.accept()
        QTimer.singleShot(0,complete);self.h.add_relation()
    def measurement(self,comment='New measurement',cancel=False):
        def complete():
            d=QApplication.activeModalWidget();d.comment.setText(comment);d.n.setText('2,5');d.length.setText('3,2');d.reject() if cancel else d.accept()
        QTimer.singleShot(0,complete);self.h.add_measurement()
    def test_new_relation_under_another_parent_is_revealed(self):
        h=self.h;h.search.setText('Wall');self.relation();self.assertEqual(h.current_code,'A');self.assertEqual(h.active_concept,'B');self.assertEqual(h.search.text(),'')
        r=h.budget._relation(h.selected_relation);self.assertEqual(str(r.quantity),'2.5');self.assertEqual(h.prices.item(h.prices.currentRow(),0).text(),'B');self.assertFalse(h.prices.isRowHidden(h.prices.currentRow()))
        h.undo();self.assertNotIn(r.id,h.budget._relations_by_id);h.redo();self.assertIn(r.id,h.budget._relations_by_id)
    def test_explicit_repeated_relation_selects_its_own_identity(self):
        h=self.h;original=h.selected_relation;self.relation('ROOT','A');self.assertNotEqual(h.selected_relation,original);self.assertEqual(h.prices.currentRow(),2)
    def test_new_native_measurement_is_visible_and_selected(self):
        h=self.h;self.measurement('First');first=h._measurement_keys[h.measurements_table.currentRow()];self.measurement('Second');second=h._measurement_keys[h.measurements_table.currentRow()]
        self.assertNotEqual(first,second);self.assertEqual(h.measurements_table.item(h.measurements_table.currentRow(),0).text(),'Second');self.assertFalse(h.measurements_table.isRowHidden(h.measurements_table.currentRow()));self.assertFalse(h.windows['mediciones'].isHidden())
        self.assertEqual(str(h.budget.relation_quantity('A')),'16.00');h.undo();self.assertEqual(len(h.budget.measurements),1)
    def test_native_subtotal_is_revealed(self):
        h=self.h;self.measurement();h.add_measurement_subtotal(False);key=h._measurement_keys[h.measurements_table.currentRow()];self.assertEqual(h.budget.project_metadata['measurement_kind:'+key[1]],'1');self.assertFalse(h.measurements_table.isRowHidden(h.measurements_table.currentRow()))
    def test_cancel_and_cycle_keep_model_filter_and_history(self):
        h=self.h;h.search.setText('Wall');before=dumps(h.budget);count=len(h._undo);self.relation(cancel=True)
        with patch.object(h,'_error') as error:self.relation('A','ROOT');error.assert_called_once()
        self.assertEqual(dumps(h.budget),before);self.assertEqual(len(h._undo),count);self.assertEqual(h.search.text(),'Wall')
        self.measurement(cancel=True);self.assertEqual(dumps(h.budget),before)
    def test_bc3_added_line_is_selected_and_decimal_comma_accepted(self):
        h=self.h;h.budget.bc3_measurements['A']=parse_measurement('ROOT'+chr(92)+'A||1|'+chr(92).join(('', 'Original','1','','','',''))+'|');h._reset_history();h.refresh()
        def complete():
            d=QApplication.activeModalWidget();edits=d.findChildren(QLineEdit);edits[1].setText('Added BC3');edits[2].setText('2,5');edits[3].setText('3,2');d.accept()
        QTimer.singleShot(0,complete);h.add_measurement();self.assertEqual(h._measurement_keys[h.measurements_table.currentRow()],('A',1));self.assertEqual(h.measurements_table.item(h.measurements_table.currentRow(),0).text(),'Added BC3');self.assertFalse(h.measurements_table.isRowHidden(h.measurements_table.currentRow()));self.assertEqual(str(h.budget.bc3_measurements['A'].calculated_quantity),'9.00')
