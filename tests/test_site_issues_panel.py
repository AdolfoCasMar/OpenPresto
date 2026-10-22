import os,unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QTimer,QDate
from PySide6.QtWidgets import QApplication,QLineEdit,QComboBox,QPlainTextEdit
from openpresto.mdi_workspace import PrestoWorkspace
from openpresto import site_issues as issues
from openpresto.storage import dumps
from test_production import project

class SiteIssuesPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setOrganizationName('OpenPrestoTests');cls.app.setApplicationName('SiteIssuesPanel')
    def setUp(self):
        self.host=PrestoWorkspace();self.host.budget=project();self.host._reset_history();self.host._open_views();self.host.section_ui.tabs.setCurrentIndex(3);self.panel=self.host.panels['gestion'][1].site_issues
    def tearDown(self):self.host.dirty=False;self.host.close()
    def create(self):
        def accept():
            d=self.app.activeModalWidget();d.findChild(QLineEdit,'issue-reference').setText('I-1');d.findChild(QLineEdit,'issue-title').setText('Crack');d.accept()
        QTimer.singleShot(0,accept);self.panel.edit(True)
    def test_create_resolve_and_undo(self):
        self.create();self.assertEqual(self.panel.table.rowCount(),1);self.panel.table.setCurrentCell(0,0)
        def accept():
            d=self.app.activeModalWidget();combo=d.findChild(QComboBox,'issue-status');combo.setCurrentIndex(combo.findData('resolved'));d.findChild(QPlainTextEdit,'issue-event-note').setPlainText('Checked');d.accept()
        QTimer.singleShot(0,accept);self.panel.transition();self.assertEqual(issues.validate(self.host.budget)[0]['status'],'resolved');self.assertEqual(self.panel.history.rowCount(),2)
        self.host.undo();self.assertEqual(issues.validate(self.host.budget)[0]['status'],'open')
    def test_filter_pending_and_reject_creation(self):
        before=dumps(self.host.budget);QTimer.singleShot(0,lambda:self.app.activeModalWidget().reject());self.panel.edit(True);self.assertEqual(before,dumps(self.host.budget))
        self.create();self.panel.overdue.setChecked(True);self.assertEqual(self.panel.table.rowCount(),0);self.panel.overdue.setChecked(False);self.panel.pending.setChecked(True);self.assertEqual(self.panel.table.rowCount(),1)

if __name__=='__main__':unittest.main()
