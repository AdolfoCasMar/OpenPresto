import os,unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication,QDialog,QTreeWidget
from openpresto.mdi_workspace import PrestoWorkspace
from openpresto.budget import BudgetConcept,BudgetRelation
from openpresto.tree_navigation import show_tree
from openpresto.storage import dumps
from test_production import project


class SearchTreeNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setOrganizationName('OpenPrestoTests');cls.app.setApplicationName('SearchTreeNavigation')
    def setUp(self):
        h=self.h=PrestoWorkspace();h.budget=project();h.budget.add_concept(BudgetConcept('C',summary='Child',base_price='2'));h.budget.add_relation(BudgetRelation('A','C',position=1,id='AC'));h.budget.add_relation(BudgetRelation('B','A',position=1,id='BA'));h._reset_history();h._open_views()
    def tearDown(self):self.h.dirty=False;self.h.close()
    def enter(self,rid):
        h=self.h;row=next(i for i,r in enumerate(h._visible_relations) if r.id==rid);h.enter_concept(row,0)
    def test_enter_clears_parent_filter_and_up_restores_it_and_selection(self):
        h=self.h;before=dumps(h.budget);h.search.setText('Wall');self.enter('A');self.assertEqual(h.current_code,'A');self.assertEqual(h.search.text(),'');self.assertEqual(h.selected_relation,'AC');self.assertFalse(h.prices.isRowHidden(0));h.go_up();self.assertEqual(h.current_code,'ROOT');self.assertEqual(h.search.text(),'Wall');self.assertEqual(h.selected_relation,'A');self.assertEqual(dumps(h.budget),before);self.assertFalse(h.dirty);self.assertEqual(len(h._undo),0)
    def test_each_level_recovers_its_own_filter(self):
        h=self.h;h.search.setText('Concrete');self.enter('B');h.search.setText('Wall');self.enter('BA');h.go_up();self.assertEqual(h.current_code,'B');self.assertEqual(h.search.text(),'Wall');self.assertEqual(h.selected_relation,'BA');h.go_up();self.assertEqual(h.search.text(),'Concrete');self.assertEqual(h.selected_relation,'B')
    def test_hidden_row_cannot_be_entered(self):
        h=self.h;h.search.setText('Nothing');self.enter('A');self.assertEqual(h.current_code,'ROOT');self.assertEqual(h._navigation,[])
    def test_root_discards_deeper_filters_and_navigation(self):
        h=self.h;self.enter('B');h.search.setText('Wall');self.enter('BA');h.search.setText('Nothing');h.go_root();self.assertEqual(h.current_code,'ROOT');self.assertEqual(h.search.text(),'');self.assertEqual(h._navigation,[]);self.assertFalse(h.prices.isRowHidden(0))
    def test_undo_redo_keeps_return_path_and_parent_filter(self):
        h=self.h;h.search.setText('Wall');self.enter('A');h._execute('budget.concept.edit',code='C',changes={'summary':'Edited child'});h.undo();h.redo();self.assertEqual(h.current_code,'A');h.go_up();self.assertEqual(h.search.text(),'Wall');self.assertEqual(h.selected_relation,'A')
    def test_tree_jump_reveals_exact_reused_path_and_up_follows_that_path(self):
        h=self.h;h.search.setText('Nothing');h.show_panel('conceptos');h.concepts_table.setCurrentCell(2,0);h.select_concept();before=dumps(h.budget)
        def choose(dialog):
            tree=dialog.findChild(QTreeWidget);node=tree.topLevelItem(0).child(1).child(0).child(0);tree.itemDoubleClicked.emit(node,0);return QDialog.DialogCode.Accepted
        with patch('openpresto.tree_navigation.QDialog.exec',new=choose):show_tree(h)
        self.assertEqual(h.current_code,'A');self.assertEqual(h.selected_relation,'AC');self.assertEqual(h.search.text(),'');self.assertEqual(h._selection_origin,'precios');self.assertFalse(h.prices.isRowHidden(h.prices.currentRow()));h.go_up();self.assertEqual(h.current_code,'B');self.assertEqual(h.selected_relation,'BA');h.go_up();self.assertEqual(h.current_code,'ROOT');self.assertEqual(h.selected_relation,'B');self.assertEqual(dumps(h.budget),before);self.assertEqual(len(h._undo),0)
    def test_cancelled_tree_preserves_filter_and_navigation(self):
        h=self.h;h.search.setText('Wall');before=h._history_context()
        with patch('openpresto.tree_navigation.QDialog.exec',return_value=QDialog.DialogCode.Rejected):show_tree(h)
        self.assertEqual(h._history_context(),before)
