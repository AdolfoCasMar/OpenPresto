import os,unittest
from decimal import Decimal
from dataclasses import asdict,replace
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication,QDialog
from openpresto.budget import BudgetConcept,BudgetRelation
from openpresto.commands import ProjectSession
from openpresto.calculations import calculator_for
from openpresto.storage import dumps,loads
from test_production import project


def fixture():
    b=project();b.project_metadata['engine']='native-v1'
    b.add_concept(BudgetConcept('RES',base_price='100'));b.add_concept(BudgetConcept('%CI',base_price='0'))
    for parent in ('A','B'):
        b.add_relation(BudgetRelation(parent,'RES',position=1,id=parent+'-resource'));b.add_relation(BudgetRelation(parent,'%CI',quantity='.07',position=2,id=parent+'-percentage'))
    return b


class PercentageConceptReplacementTests(unittest.TestCase):
    def test_native_rate_updates_all_uses_and_catalogue_fallback(self):
        b=fixture();session=ProjectSession(b);data=asdict(replace(b.concepts['%CI'],summary='Updated',base_price=Decimal('10')));session.execute('budget.concept.replace',dict(data=data));r=loads(dumps(session.budget));self.assertEqual(calculator_for(r).total(),Decimal('2200.00'));self.assertEqual(r.concepts['%CI'].base_price,10)
        for rid in ('A-percentage','B-percentage'):self.assertEqual(r._relation(rid).quantity,Decimal('.1'))
        self.assertEqual(b._relation('A-percentage').quantity,Decimal('.07'));session.undo();self.assertEqual(calculator_for(session.budget).total(),Decimal('2140.00'));session.redo();self.assertEqual(calculator_for(session.budget).total(),Decimal('2200.00'))
    def test_summary_only_preserves_rate_and_existing_catalogue_value(self):
        b=fixture();session=ProjectSession(b);session.execute('budget.concept.replace',dict(data=asdict(replace(b.concepts['%CI'],summary='Description',base_price=Decimal('7')))));self.assertEqual(calculator_for(session.budget).total(),Decimal('2140.00'));self.assertEqual(session.budget.concepts['%CI'].base_price,0)
    def test_detached_percentage_retains_new_rate_after_last_use_is_removed(self):
        b=fixture();session=ProjectSession(b);session.execute('budget.concept.replace',dict(data=asdict(replace(b.concepts['%CI'],base_price=Decimal('12')))));session.execute('budget.relations.remove',dict(relation_ids=['A-percentage','B-percentage']));self.assertEqual(calculator_for(session.budget).price('%CI'),Decimal('12.00'))
    def test_legacy_profile_also_retains_updated_catalogue_rate(self):
        b=fixture();b.project_metadata.clear();b.percentage_profile='presto88_bc3';session=ProjectSession(b);session.execute('budget.concept.replace',dict(data=asdict(replace(b.concepts['%CI'],base_price=Decimal('9')))));self.assertEqual(session.budget.concepts['%CI'].base_price,9);self.assertEqual(session.budget._relation('A-percentage').quantity,Decimal('.09'))


class PercentageConceptDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setOrganizationName('OpenPrestoTests');cls.app.setApplicationName('PercentageConceptDialog')
    def setUp(self):
        from openpresto.mdi_workspace import PrestoWorkspace
        self.h=PrestoWorkspace();self.h.budget=fixture();self.h._reset_history();self.h._open_views();self.h.show_panel('conceptos');self.h.concepts_table.setCurrentCell(list(self.h.budget.concepts).index('%CI'),0);self.h.select_concept()
    def tearDown(self):self.h.dirty=False;self.h.close()
    def test_dialog_displays_actual_shared_rate_and_applies_decimal_comma(self):
        h=self.h
        def accept(dialog):
            self.assertEqual(Decimal(dialog.price.text()),7);self.assertTrue(dialog.price.isEnabled());dialog.price.setText('10,5');return QDialog.DialogCode.Accepted
        with patch('openpresto.editor.ConceptDialog.exec',new=accept):h.edit_selected()
        self.assertEqual(h.budget._relation('A-percentage').quantity,Decimal('.105'));self.assertEqual(h.budget.concepts['%CI'].base_price,Decimal('10.5'));self.assertEqual(calculator_for(h.budget).total(),Decimal('2210.00'));self.assertEqual(len(h._undo),1);h.undo();self.assertEqual(calculator_for(h.budget).total(),Decimal('2140.00'));h.redo();self.assertEqual(calculator_for(h.budget).total(),Decimal('2210.00'))
    def test_cancel_preserves_original_rate_and_history(self):
        h=self.h;before=dumps(h.budget)
        with patch('openpresto.editor.ConceptDialog.exec',return_value=QDialog.DialogCode.Rejected):h.edit_selected()
        self.assertEqual(dumps(h.budget),before);self.assertEqual(len(h._undo),0)
