import os,unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QLineEdit
from openpresto.mdi_workspace import PrestoWorkspace
from openpresto import budget_baselines as b
from test_production import project

class BudgetBaselinesPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setOrganizationName('OpenPrestoTests');cls.app.setApplicationName('BudgetBaselinesPanel')
    def setUp(self):
        self.host=PrestoWorkspace();self.host.budget=project();self.host._reset_history();self.host._open_views();self.host.section_ui.tabs.setCurrentIndex(3);self.panel=self.host.panels['gestion'][1].budget_baselines
    def tearDown(self):self.host.dirty=False;self.host.close()
    def test_create_filter_remove_and_undo(self):
        def accept():
            d=self.app.activeModalWidget();d.findChild(QLineEdit,'baseline-reference').setText('BASE');d.accept()
        QTimer.singleShot(0,accept);self.panel.freeze();self.assertEqual(self.panel.choice.count(),1);self.assertEqual(self.panel.table.rowCount(),2)
        self.panel.changed.setChecked(True);self.assertEqual(self.panel.table.rowCount(),0);self.panel.remove();self.assertEqual(b.validate(self.host.budget),[])
        self.host.undo();self.assertEqual(self.panel.choice.count(),1)
    def test_cancel_creation_preserves_project(self):
        QTimer.singleShot(0,lambda:self.app.activeModalWidget().reject());self.panel.freeze();self.assertEqual(b.validate(self.host.budget),[])

if __name__=='__main__':unittest.main()
