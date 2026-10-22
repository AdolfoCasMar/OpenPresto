import os,unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication,QMessageBox,QLineEdit,QTableWidget,QLabel
from PySide6.QtCore import QTimer
from openpresto.mdi_workspace import PrestoWorkspace
from openpresto.pzh_importer import _import
from openpresto.calculations import calculator_for
from test_budget_phase_measurements import fixture

class BudgetPhasePanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setOrganizationName('OpenPrestoTests');cls.app.setApplicationName('BudgetPhases')
    def test_copy_filter_reviewed_apply_and_undo(self):
        host=PrestoWorkspace()
        try:
            host.budget=_import(fixture(),'own.pzh').budget;host._reset_history();host._open_views();host.section_ui.tabs.setCurrentIndex(3)
            panel=host.panels['gestion'][1].budget_phase_measurements;panel.copy();self.assertEqual(panel.table.rowCount(),2)
            panel.phase.setCurrentIndex(panel.phase.findData(2));self.assertEqual(panel.table.rowCount(),1)
            panel.table.setCurrentCell(0,0)
            def accept_edit():
                dialog=QApplication.activeModalWidget();dialog.findChild(QLineEdit,'phase-n_lines').setText('3');dialog.accept()
            QTimer.singleShot(0,accept_edit);panel.edit()
            history_before=len(host._undo);observed={}
            def inspect_preview():
                dialog=QApplication.activeModalWidget();observed['totals']=dialog.findChild(QLabel,'phase-preview-totals').text();observed['rows']=dialog.findChild(QTableWidget,'phase-preview-table').rowCount();dialog.accept()
            QTimer.singleShot(0,inspect_preview);panel.preview()
            self.assertIn('41.72',observed['totals']);self.assertEqual(observed['rows'],1);self.assertEqual(len(host._undo),history_before)
            with patch('openpresto.budget_phase_measurements_panel.QMessageBox.question',return_value=QMessageBox.StandardButton.No):panel.apply()
            self.assertEqual(str(calculator_for(host.budget).total()),'10.43')
            with patch('openpresto.budget_phase_measurements_panel.QMessageBox.question',return_value=QMessageBox.StandardButton.Yes):panel.apply()
            self.assertEqual(str(calculator_for(host.budget).total()),'41.72');host.undo();self.assertEqual(str(calculator_for(host.budget).total()),'10.43')
        finally:host.dirty=False;host.close()
