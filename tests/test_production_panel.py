import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QLineEdit
from openpresto.mdi_workspace import PrestoWorkspace
from openpresto.production import validate,quantities
from test_production import project

class ProductionPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setOrganizationName('OpenPrestoTests');cls.app.setApplicationName('ProductionPanel')
    def setUp(self):
        self.host=PrestoWorkspace();self.host.budget=project();self.host._reset_history();self.host._open_views();self.host.section_ui.tabs.setCurrentIndex(3)
        self.panel=self.host.panels['gestion'][1].production
    def tearDown(self):
        self.host.dirty=False;self.host.close()
    def test_create_confirm_and_undo(self):
        def accept():
            dialog=self.app.activeModalWidget();dialog.findChild(QLineEdit,'production-reference').setText('P1');dialog.accept()
        QTimer.singleShot(0,accept);self.panel.edit(True)
        self.assertEqual(len(validate(self.host.budget)),1);self.assertEqual(self.panel.table.rowCount(),1)
        self.panel.table.setCurrentCell(0,0);self.panel.confirm();self.assertEqual(validate(self.host.budget)[0]['status'],'posted')
        self.host.undo();self.assertEqual(validate(self.host.budget)[0]['status'],'draft')
    def test_dialog_cancel_does_not_create_part(self):
        QTimer.singleShot(0,lambda:self.app.activeModalWidget().reject());self.panel.edit(True)
        self.assertEqual(validate(self.host.budget),[])

if __name__=='__main__':unittest.main()
