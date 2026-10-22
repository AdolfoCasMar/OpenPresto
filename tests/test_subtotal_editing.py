import os,unittest
from dataclasses import asdict,replace
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication,QDialog
from openpresto.budget import BudgetMeasurement,BudgetError
from openpresto.commands import ProjectSession
from openpresto.measurement_operations import insert_subtotal,native_display
from openpresto.storage import dumps,loads
from test_production import project


def fixture():
    b=project();b.add_measurement(BudgetMeasurement('A',n_lines='3',id='normal'));b=insert_subtotal(b,'A',True);return b,b.measurements[-1].id


class SubtotalEditingTests(unittest.TestCase):
    def test_numeric_formula_and_annulment_changes_are_rejected_atomically(self):
        b,mid=fixture();session=ProjectSession(b);before=dumps(b)
        for field,value in (('n_lines','10'),('length','2'),('width','4'),('height','5'),('formula','a*b'),('annulled_dimensions',['length'])):
            with self.subTest(field=field),self.assertRaises(BudgetError):session.execute('budget.measurement.edit',dict(measurement_id=mid,field=field,value=value))
            self.assertEqual(dumps(session.budget),before)
    def test_full_replacement_also_rejects_ignored_dimensions(self):
        b,mid=fixture();session=ProjectSession(b);old=b.measurements[-1]
        with self.assertRaises(BudgetError):session.execute('budget.measurement.replace',dict(data=asdict(replace(old,n_lines='9'))))
        self.assertEqual(dumps(session.budget),dumps(b))
    def test_comment_changes_keep_subtotal_value_and_survive_save_undo_redo(self):
        b,mid=fixture();session=ProjectSession(b);session.execute('budget.measurement.edit',dict(measurement_id=mid,field='comment',value='Checked total'));r=loads(dumps(session.budget));self.assertEqual(native_display(r,mid)[1],3);self.assertEqual(r.measurements[-1].comment,'Checked total');session.undo();self.assertEqual(session.budget.measurements[-1].comment,'Subtotal acumulado');session.redo();self.assertEqual(session.budget.measurements[-1].comment,'Checked total')
    def test_unchanged_numeric_values_and_normal_measurements_still_work(self):
        b,mid=fixture();session=ProjectSession(b);session.execute('budget.measurement.edit',dict(measurement_id=mid,field='n_lines',value='0'));session.execute('budget.measurement.edit',dict(measurement_id='normal',field='n_lines',value='4'));self.assertEqual(native_display(session.budget,mid)[1],4)


class SubtotalEditingPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setOrganizationName('OpenPrestoTests');cls.app.setApplicationName('SubtotalEditing')
    def setUp(self):
        from openpresto.mdi_workspace import PrestoWorkspace
        self.h=PrestoWorkspace();self.h.budget,self.mid=fixture();old=self.h.budget.measurements[-1];self.h.budget.measurements[-1]=replace(old,length='2.3456',formula=' ',annulled_dimensions=('length',));self.h._reset_history();self.h._open_views();self.h._reveal_measurement(('native',self.mid),'A')
    def tearDown(self):self.h.dirty=False;self.h.close()
    def test_dialog_changes_only_comment_and_preserves_hidden_source_values(self):
        h=self.h;old=h.budget.measurements[-1];self.assertEqual(h.measurements_table.currentRow(),1)
        def accept(dialog):
            self.assertTrue(dialog.comment.isEnabled())
            for w in (dialog.n,dialog.length,dialog.width,dialog.height,dialog.formula,*dialog.annulled.values()):self.assertFalse(w.isEnabled())
            dialog.comment.setText('Own comment');return QDialog.DialogCode.Accepted
        with patch('openpresto.editor.MeasurementDialog.exec',new=accept):h.edit_selected()
        self.assertEqual(h.budget.measurements[-1],replace(old,comment='Own comment'));self.assertEqual(len(h._undo),1);self.assertEqual(h.measurements_table.currentRow(),1);h.undo();self.assertEqual(h.budget.measurements[-1],old);h.redo();self.assertEqual(h.budget.measurements[-1].comment,'Own comment')
    def test_cancel_does_not_change_model_or_history(self):
        h=self.h;before=dumps(h.budget)
        with patch('openpresto.editor.MeasurementDialog.exec',return_value=QDialog.DialogCode.Rejected):h.edit_selected()
        self.assertEqual(dumps(h.budget),before);self.assertEqual(len(h._undo),0)
