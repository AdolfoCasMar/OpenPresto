import os,unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QLineEdit,QComboBox
from openpresto.mdi_workspace import PrestoWorkspace
from openpresto import resource_hours as h
from openpresto.storage import dumps
from test_resource_hours import project

class ResourceHoursPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setOrganizationName('OpenPrestoTests');cls.app.setApplicationName('ResourceHoursPanel')
    def setUp(self):
        self.host=PrestoWorkspace();self.host.budget=project();self.host._reset_history();self.host._open_views();self.host.section_ui.tabs.setCurrentIndex(3)
        self.panel=self.host.panels['gestion'][1].resource_hours
    def tearDown(self):
        self.host.dirty=False;self.host.close()
    def create(self):
        def accept():
            d=self.app.activeModalWidget();d.findChild(QLineEdit,'hours-reference').setText('H1');d.findChild(QLineEdit,'hours-hours').setText('8');d.findChild(QLineEdit,'hours-rate').setText('25')
            combo=d.findChild(QComboBox,'hours-relation');combo.setCurrentIndex(combo.findData('A'));d.accept()
        QTimer.singleShot(0,accept);self.panel.edit(True)
    def test_create_confirm_and_undo(self):
        self.create();self.assertEqual(self.panel.table.rowCount(),1);self.panel.table.setCurrentCell(0,0);self.panel.confirm()
        self.assertEqual(h.validate(self.host.budget)[0]['status'],'posted');self.assertEqual(self.panel.resources.rowCount(),1)
        self.host.undo();self.assertEqual(h.validate(self.host.budget)[0]['status'],'draft');self.assertEqual(self.panel.resources.rowCount(),0)
    def test_cancel_dialog_and_history(self):
        self.create();self.panel.table.setCurrentCell(0,0);self.panel.confirm();self.panel.table.setCurrentCell(0,0)
        def accept():
            d=self.app.activeModalWidget();d.findChild(QLineEdit,'hours-cancellation-reason').setText('Correction');d.accept()
        QTimer.singleShot(0,accept);self.panel.cancel()
        self.assertEqual(h.validate(self.host.budget)[0]['status'],'cancelled');self.assertEqual(self.panel.resources.rowCount(),0)
        self.host.undo();self.assertEqual(h.validate(self.host.budget)[0]['status'],'posted')
    def test_reject_creation_does_not_change_project(self):
        before=dumps(self.host.budget);QTimer.singleShot(0,lambda:self.app.activeModalWidget().reject());self.panel.edit(True)
        self.assertEqual(dumps(self.host.budget),before)

if __name__=='__main__':unittest.main()
