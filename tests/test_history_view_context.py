import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from dataclasses import replace,asdict
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from openpresto.mdi_workspace import PrestoWorkspace
from openpresto.budget import BudgetMeasurement,BudgetRelation,BudgetConcept
from openpresto.bc3_measurements import parse_measurement
from openpresto.history_snapshots import capture_snapshot,restore_snapshot
from openpresto.storage import dumps
from test_production import project


class HistoryViewContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setOrganizationName('OpenPrestoTests');cls.app.setApplicationName('HistoryViewContext')
    def setUp(self):
        self.h=PrestoWorkspace();self.h.budget=project();self.h._reset_history();self.h._open_views()
    def tearDown(self):self.h.dirty=False;self.h.close()
    def current_measurement(self):return self.h._measurement_keys[self.h.measurements_table.currentRow()]
    def test_bc3_move_undo_redo_restore_line_identity_and_pane(self):
        h=self.h;body=chr(92).join(tuple(v for text in ('One','Two') for v in ('',text,'1','','','')))+chr(92)
        h.budget.bc3_measurements['A']=parse_measurement('ROOT'+chr(92)+'A||2|'+body+'|');h._reset_history();h.refresh();h.show_panel('mediciones');h.measurements_table.setCurrentCell(0,0)
        h.move_measurement_line(1);self.assertEqual(self.current_measurement(),('A',1));h.undo();self.assertEqual(self.current_measurement(),('A',0));self.assertEqual(h.measurements_table.item(0,0).text(),'One');self.assertIs(h.mdi.activeSubWindow(),h.windows['mediciones']);h.redo();self.assertEqual(self.current_measurement(),('A',1));self.assertEqual(h.measurements_table.item(1,0).text(),'One')
    def test_deleted_native_line_is_selected_again_on_undo(self):
        h=self.h
        for name in ('One','Two','Three'):h.budget.add_measurement(BudgetMeasurement('A',comment=name,id=name))
        h._reset_history();h.refresh();h.show_panel('mediciones');h.measurements_table.setCurrentCell(1,0);h.delete_selected();self.assertEqual(self.current_measurement(),('native','Three'))
        h.undo();self.assertEqual(self.current_measurement(),('native','Two'));self.assertIs(h.mdi.activeSubWindow(),h.windows['mediciones']);h.redo();self.assertEqual(self.current_measurement(),('native','Three'))
    def test_new_relationship_undo_redo_restore_previous_and_destination_levels(self):
        h=self.h;r=BudgetRelation('A','B','2',1,'new-r');h._execute('budget.relation.add',data=asdict(r));h._reveal_relation(r.id);self.assertEqual(h.current_code,'A')
        h.undo();self.assertEqual(h.current_code,'ROOT');self.assertEqual(h.selected_relation,'A');h.redo();self.assertEqual(h.current_code,'A');self.assertEqual(h.selected_relation,'new-r');self.assertEqual(h.active_concept,'B')
    def test_search_and_catalogue_selection_are_restored(self):
        h=self.h;h.search.setText('Wall');h.show_panel('precios');h.prices.setCurrentCell(0,0);h.delete_selected();h.undo();self.assertEqual(h.search.text(),'Wall');self.assertEqual(h.selected_relation,'A');self.assertFalse(h.prices.isRowHidden(h.prices.currentRow()))
        h.redo();self.assertEqual(h.search.text(),'Wall');self.assertEqual(h.prices.currentRow(),-1)
    def test_catalogue_removal_undo_restores_deleted_code_selection(self):
        h=self.h;h.budget.add_concept(BudgetConcept('UNUSED'));h._reset_history();h.refresh();h.show_panel('conceptos');h.concepts_table.setCurrentCell(3,0);h.select_concept();h.delete_selected();h.undo();self.assertEqual(h.active_concept,'UNUSED');self.assertEqual(h.concepts_table.item(h.concepts_table.currentRow(),0).text(),'UNUSED');self.assertIs(h.mdi.activeSubWindow(),h.windows['conceptos'])
    def test_management_section_and_module_survive_history(self):
        h=self.h;h.section_ui.tabs.setCurrentIndex(3);manager=h.panels['gestion'][1];manager.tabs.setCurrentWidget(manager.technical_documents);index=manager.tabs.currentIndex();h._execute('technical.document.set',reference='DOC',title='Example',text='Text');h.section_ui.tabs.setCurrentIndex(0);h.undo();self.assertEqual(h.section_ui.tabs.currentIndex(),3);self.assertEqual(manager.tabs.currentIndex(),index)
    def test_save_as_keeps_context_and_does_not_serialize_it(self):
        h=self.h;h.search.setText('ui-history-private-filter');r=BudgetRelation('A','B','2',1,'new-r');h._execute('budget.relation.add',data=asdict(r));h._reveal_relation(r.id);context=h._undo[-1].context
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'copy.json'
            with patch('openpresto.editor.QFileDialog.getSaveFileName',return_value=(str(target),'')):self.assertTrue(h.save_as())
            self.assertEqual(h._undo[-1].context,context);self.assertNotIn('ui-history-private-filter',target.read_text(encoding='utf-8'));h.undo();self.assertEqual(h.current_code,'ROOT');self.assertEqual(h.search.text(),'ui-history-private-filter');h.redo();self.assertEqual(h.current_code,'A');self.assertFalse(h.dirty)
    def test_noop_and_failed_command_leave_history_and_dirty_flag_unchanged(self):
        h=self.h;h.search.setText('Wall');h._execute('budget.concept.edit',code='A',changes={'summary':'Wall'});self.assertEqual(len(h._undo),0);self.assertFalse(h.dirty)
        with patch.object(h,'_error') as error:h._execute('budget.relation.add',data=asdict(BudgetRelation('A','ROOT','1',1)));error.assert_called_once()
        self.assertEqual(len(h._undo),0);self.assertFalse(h.dirty)
    def test_context_is_excluded_from_model_equality_and_portable_json(self):
        b=project();s=capture_snapshot(b);annotated=replace(s,context=('ui-history-private-filter',));self.assertEqual(s,annotated);self.assertEqual(dumps(restore_snapshot(annotated)),dumps(b));self.assertNotIn('private',repr(annotated))
