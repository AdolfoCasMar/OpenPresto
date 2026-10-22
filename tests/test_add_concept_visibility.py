import os,unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication,QCheckBox
from PySide6.QtCore import QTimer
from openpresto.mdi_workspace import PrestoWorkspace
from openpresto.budget import Budget,BudgetError
from openpresto.commands import execute
from openpresto.storage import dumps
from test_production import project


class AddConceptVisibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setOrganizationName('OpenPrestoTests');cls.app.setApplicationName('AddConceptVisibility')
    def setUp(self):
        self.h=PrestoWorkspace();self.h.budget=project();self.h._reset_history();self.h._open_views()
    def tearDown(self):self.h.dirty=False;self.h.close()
    def add(self,code='NEW',catalogue=False,cancel=False):
        def complete():
            dialog=QApplication.activeModalWidget();dialog.code.setText(code);dialog.summary.setText('New line');dialog.price.setText('2,50')
            checkbox=dialog.findChild(QCheckBox,'insert-concept-in-budget')
            if catalogue and checkbox is not None:checkbox.setChecked(False)
            dialog.reject() if cancel else dialog.accept()
        QTimer.singleShot(0,complete);self.h.add_concept()
    def test_budget_add_is_visible_selected_and_single_undo_restores_both(self):
        h=self.h;h.search.setText('A');before=len(h._undo);self.add()
        self.assertEqual(h.search.text(),'');self.assertEqual(h.active_concept,'NEW');self.assertEqual(h.prices.item(h.prices.currentRow(),0).text(),'NEW')
        self.assertFalse(h.prices.isRowHidden(h.prices.currentRow()));self.assertEqual(len(h._undo),before+1)
        self.assertEqual(str(h.budget.concepts['NEW'].base_price),'2.50');self.assertTrue(any(r.parent_code=='ROOT' and r.child_code=='NEW' for r in h.budget.relations))
        h.undo();self.assertNotIn('NEW',h.budget.concepts);self.assertFalse(any(r.child_code=='NEW' for r in h.budget.relations));h.redo();self.assertIn('NEW',h.budget.concepts)
    def test_nested_budget_add_uses_open_parent(self):
        h=self.h;h.current_code='A';h.refresh();self.add();self.assertEqual(h.current_code,'A');self.assertEqual(h.active_concept,'NEW');self.assertTrue(any(r.parent_code=='A' and r.child_code=='NEW' for r in h.budget.relations))
    def test_catalogue_only_add_reveals_new_concept_without_budget_line(self):
        h=self.h;self.add(catalogue=True);self.assertEqual(h.active_concept,'NEW');self.assertEqual(h.concepts_table.item(h.concepts_table.currentRow(),0).text(),'NEW');self.assertFalse(any(r.child_code=='NEW' for r in h.budget.relations));self.assertFalse(h.windows['conceptos'].isHidden())
    def test_creation_from_catalogue_defaults_to_catalogue(self):
        h=self.h;h.concepts_table.setCurrentCell(0,0);h.select_concept();self.add();self.assertEqual(h.active_concept,'NEW');self.assertFalse(any(r.child_code=='NEW' for r in h.budget.relations))
    def test_first_concept_becomes_visible_root(self):
        h=self.h;h.budget=Budget();h.current_code=None;h._reset_history();h.refresh();self.add();self.assertEqual(h.budget.root_code,'NEW');self.assertEqual(h.active_concept,'NEW');self.assertEqual(h.concepts_table.item(h.concepts_table.currentRow(),0).text(),'NEW')
    def test_cancel_and_existing_line_do_not_add_history_or_duplicate_rows(self):
        h=self.h;before=dumps(h.budget);count=len(h._undo);self.add(cancel=True);self.assertEqual(dumps(h.budget),before)
        with patch.object(h,'_error') as error:self.add(code='A');error.assert_not_called()
        self.assertEqual(h.active_concept,'A')
        self.assertEqual(dumps(h.budget),before);self.assertEqual(len(h._undo),count)
    def test_invalid_parent_command_is_atomic(self):
        b=project();before=dumps(b)
        with self.assertRaises(BudgetError):execute(b,'budget.concept.add',dict(data=dict(code='NEW'),parent_code='MISSING'))
        self.assertEqual(dumps(b),before)

    def test_existing_detached_concept_is_reused_without_changing_its_data(self):
        from openpresto.budget import BudgetConcept
        h=self.h;h.budget.add_concept(BudgetConcept('EXISTING','m','Original',base_price='7'));h._reset_history();h.refresh();before=len(h._undo)
        self.add(code='EXISTING');self.assertEqual(h.active_concept,'EXISTING');self.assertEqual(h.budget.concepts['EXISTING'].summary,'Original');self.assertEqual(str(h.budget.concepts['EXISTING'].base_price),'7');self.assertEqual(len(h._undo),before+1)
        h.undo();self.assertIn('EXISTING',h.budget.concepts);self.assertFalse(any(r.child_code=='EXISTING' for r in h.budget.relations))

    def test_reusing_an_ancestor_rejects_cycle_without_changing_the_project(self):
        h=self.h;h.current_code='A';h.refresh();before=dumps(h.budget);count=len(h._undo)
        with patch.object(h,'_error') as error:self.add(code='ROOT');error.assert_called_once()
        self.assertEqual(dumps(h.budget),before);self.assertEqual(len(h._undo),count);self.assertEqual(h.current_code,'A')
