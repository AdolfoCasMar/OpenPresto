import os,unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QLineEdit
from openpresto.mdi_workspace import PrestoWorkspace
from openpresto import nonconformities as nc,site_issues as issues
from test_nonconformities import sample

class NonconformityPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setOrganizationName('OpenPrestoTests');cls.app.setApplicationName('NonconformitiesPanel')
    def setUp(self):
        self.host=PrestoWorkspace();self.host.budget,_=sample();self.host._reset_history();self.host._open_views();self.host.section_ui.tabs.setCurrentIndex(3);self.manager=self.host.panels['gestion'][1];self.panel=self.manager.nonconformities
    def tearDown(self):self.host.dirty=False;self.host.close()
    def test_creation_navigation_and_undo(self):
        self.panel.table.setCurrentCell(0,0)
        def accept():
            d=self.app.activeModalWidget();d.findChild(QLineEdit,'nc-reference').setText('NC');d.accept()
        QTimer.singleShot(0,accept);self.panel.create();self.assertEqual(len(nc.validate(self.host.budget)),1);self.panel.table.setCurrentCell(0,0);self.panel.open_issue()
        self.assertIs(self.manager.tabs.currentWidget(),self.manager.site_issues);self.assertEqual(self.manager.site_issues.table.currentRow(),0)
        self.host.undo();self.assertEqual(issues.validate(self.host.budget),[])
    def test_quality_shortcut(self):
        self.manager.quality_control.track();self.assertIs(self.manager.tabs.currentWidget(),self.panel)

if __name__=='__main__':unittest.main()
