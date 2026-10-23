import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QToolBar
from openpresto.budget import Budget, BudgetConcept, BudgetRelation
from openpresto.storage import dumps
from openpresto.concept_appearance import COLOURS, code_kind


class BudgetViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        from openpresto.mdi_workspace import PrestoWorkspace
        self.host=PrestoWorkspace();b=Budget('R')
        for code,nature in (('R',''),('C1','Capítulo'),('C2','Capítulo'),('P','Partida'),('M','Material'),('L','Mano de obra')):
            b.add_concept(BudgetConcept(code,summary=code,nature=nature,base_price='3'))
        for position,(parent,child,rid) in enumerate((('R','C1','r1'),('R','C2','r2'),('C1','P','p1'),('C2','P','p2'),('P','M','m'),('P','L','l')),1):
            b.add_relation(BudgetRelation(parent,child,'1',position,id=rid))
        self.host.budget=b;self.host._reset_history();self.host.show();self.host._open_views();self.app.processEvents()

    def tearDown(self):
        self.host.dirty=False;self.host.close();self.host.deleteLater();self.app.processEvents()

    def test_five_shortcuts_have_icons_and_open_distinct_views(self):
        for key in ('precios','conceptos','arbol','capitulos','capitulos-partidas'):
            action=self.host.commands['ver-'+key][0]
            self.assertFalse(action.icon().isNull())
            self.assertTrue(any(action in bar.actions() for bar in self.host.findChildren(QToolBar)))
            action.trigger();self.assertTrue(self.host.windows[key].isVisible())
        self.assertIsNot(self.host.panels['capitulos'][1],self.host.panels['capitulos-partidas'][1])

    def test_chapters_and_work_items_filter_resources_and_preserve_reused_paths(self):
        before=dumps(self.host.budget)
        self.host.show_panel('capitulos');chapters=self.host.panels['capitulos'][1].tree
        self.assertEqual(chapters.topLevelItemCount(),2)
        self.assertEqual(chapters.topLevelItem(0).childCount(),0)
        self.host.show_panel('capitulos-partidas');view=self.host.panels['capitulos-partidas'][1]
        second=view.tree.topLevelItem(1).child(0)
        self.assertEqual(second.text(0),'P');self.assertEqual(second.childCount(),0)
        view.navigate(second,0)
        self.assertEqual(self.host.current_code,'C2');self.assertEqual(self.host.selected_relation,'p2')
        self.assertEqual(dumps(self.host.budget),before);self.assertEqual(len(self.host._undo),0)
        self.host.show_panel('arbol');tree=self.host.panels['arbol'][1].tree
        self.assertEqual(tree.topLevelItem(0).child(1).child(0).childCount(),2)

    def test_code_colours_are_consistent_and_do_not_change_values(self):
        host=self.host;before=dumps(host.budget)
        for row,concept in enumerate(host.budget.concepts.values()):
            expected=COLOURS[code_kind(concept,'R')][0]
            self.assertEqual(host.concepts_table.item(row,0).background().color().name(),expected)
        self.assertEqual(host.prices.item(0,0).background().color().name(),COLOURS['capitulo'][0])
        host.show_panel('arbol');view=host.panels['arbol'][1]
        item=view.tree.topLevelItem(0)
        self.assertEqual(item.background(0).color().name(),COLOURS['obra'][0])
        stamp=view._stamp;view.render();self.assertIs(view._stamp,stamp)
        self.assertEqual(dumps(host.budget),before)
        self.assertEqual(code_kind(BudgetConcept('%CI'),None),'porcentaje')
        self.assertEqual(code_kind(BudgetConcept('X',nature='Desconocida'),None),'otro')

    def test_embedded_tree_selects_reused_relation_without_rebuilding_and_preserves_expansion(self):
        host=self.host;view=host.budget_structure;before=dumps(host.budget)
        path=('r2','p2');root=view.items[()];root.setExpanded(True);view.items[('r2',)].setExpanded(True)
        stamp=view._stamp;view.tree.setCurrentItem(view.items[path]);self.app.processEvents()
        self.assertEqual(host.selected_relation,'p2');self.assertEqual(host.active_concept,'P');self.assertEqual(host.current_code,'C2');self.assertIs(view._stamp,stamp)
        view._stamp=(host.budget,object(),view._stamp[2]);view.render();self.assertEqual(view.tree.currentItem().data(0,Qt.ItemDataRole.UserRole),path)
        self.assertTrue(view.items[('r2',)].isExpanded());self.assertEqual(dumps(host.budget),before);self.assertEqual(host._undo,[])
        host.set_budget_view('precios');self.assertIs(host.budget_stack.currentWidget(),host.prices)

    def test_collapsed_branch_survives_model_copy_on_edit_and_undo(self):
        host=self.host;view=host.budget_structure;view.items[('r1',)].setExpanded(False)
        host._execute('budget.concept.edit',code='P',changes={'summary':'Own revised summary'})
        self.assertFalse(view.items[('r1',)].isExpanded());host.undo();self.assertFalse(view.items[('r1',)].isExpanded())

    def test_tree_search_keeps_ancestors_and_resets_without_modifying_budget(self):
        host=self.host;view=host.budget_structure;before=dumps(host.budget)
        host.search.setText('M');self.assertFalse(view.items[('r2','p2','m')].isHidden());self.assertFalse(view.items[('r2',)].isHidden());self.assertTrue(view.items[('r2','p2','l')].isHidden())
        host.search.clear();self.assertFalse(view.items[('r2','p2','l')].isHidden());self.assertEqual(dumps(host.budget),before)

    def test_root_selection_does_not_delete_a_stale_hidden_price_row(self):
        host=self.host;before=dumps(host.budget);host.budget_structure.tree.setCurrentItem(host.budget_structure.items[()])
        self.assertIsNone(host.selected_relation);host.delete_selected();self.assertEqual(dumps(host.budget),before)


if __name__=='__main__':unittest.main()
