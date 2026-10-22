import os,unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication
from openpresto.mdi_workspace import PrestoWorkspace
from openpresto.storage import dumps
from test_productivity import sample

class ProductivityPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setOrganizationName('OpenPrestoTests');cls.app.setApplicationName('ProductivityPanel')
    def setUp(self):
        self.host=PrestoWorkspace();self.host.budget=sample();self.host._reset_history();self.host._open_views();self.host.section_ui.tabs.setCurrentIndex(3);self.panel=self.host.panels['gestion'][1].productivity
    def tearDown(self):self.host.dirty=False;self.host.close()
    def test_interval_refresh_is_read_only(self):
        before=dumps(self.host.budget);self.panel.start.setDate(QDate(2026,10,1));self.panel.end.setDate(QDate(2026,10,31));self.assertEqual(self.panel.work.rowCount(),1);self.assertEqual(self.panel.work.item(0,7).text(),'3.200000')
        self.panel.start.setDate(QDate(2026,10,2));self.assertEqual(self.panel.work.rowCount(),0);self.assertEqual(dumps(self.host.budget),before)
    def test_invalid_interval_clears_tables(self):
        self.panel.start.setDate(QDate(2026,11,1));self.panel.end.setDate(QDate(2026,10,31));self.assertEqual(self.panel.work.rowCount(),0);self.assertIn('inicio',self.panel.status.text())

if __name__=='__main__':unittest.main()
