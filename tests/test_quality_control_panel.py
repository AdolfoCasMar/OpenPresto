import os,unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QLineEdit,QTableWidget
from openpresto.mdi_workspace import PrestoWorkspace
from openpresto import quality_control as q
from openpresto.storage import dumps
from test_production import project

class QualityControlPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setOrganizationName('OpenPrestoTests');cls.app.setApplicationName('QualityControlPanel')
    def setUp(self):
        self.host=PrestoWorkspace();self.host.budget=project();self.host._reset_history();self.host._open_views();self.host.section_ui.tabs.setCurrentIndex(3);self.panel=self.host.panels['gestion'][1].quality_control
    def tearDown(self):self.host.dirty=False;self.host.close()
    def test_create_review_and_undo(self):
        def accept():
            d=self.app.activeModalWidget()
            for key,value in [('reference','QC-1'),('title','Wall check'),('inspector','Inspector')]:d.findChild(QLineEdit,'quality-'+key).setText(value)
            table=d.findChild(QTableWidget,'quality-checks');table.cellWidget(0,0).setText('Visual criterion');table.cellWidget(0,1).setCurrentIndex(1);d.accept()
        QTimer.singleShot(0,accept);self.panel.edit(True);self.assertEqual(self.panel.table.rowCount(),1);self.panel.table.setCurrentCell(0,0)
        QTimer.singleShot(0,lambda:self.app.activeModalWidget().accept());self.panel.finish('reviewed');self.assertEqual(q.verdict(q.validate(self.host.budget)[0]),'Conforme')
        self.host.undo();self.assertEqual(q.validate(self.host.budget)[0]['status'],'draft')
    def test_cancel_creation_preserves_project(self):
        before=dumps(self.host.budget);QTimer.singleShot(0,lambda:self.app.activeModalWidget().reject());self.panel.edit(True);self.assertEqual(dumps(self.host.budget),before)

if __name__=='__main__':unittest.main()
