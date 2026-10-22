import os,unittest,time
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QLineEdit,QPlainTextEdit
from openpresto.mdi_workspace import PrestoWorkspace
from openpresto import technical_documents as docs
from openpresto.pzh_importer import _import
from test_technical_documents import fixture

class TechnicalDocumentPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setOrganizationName('OpenPrestoTests');cls.app.setApplicationName('TechnicalDocuments')
    def setUp(self):
        self.host=PrestoWorkspace();self.host.budget=_import(fixture(),'own.pzh').budget;self.host._reset_history();self.host._open_views();self.host.section_ui.tabs.setCurrentIndex(3);self.panel=self.host.panels['gestion'][1].technical_documents
    def tearDown(self):self.panel.pool.waitForDone(5000);self.host.dirty=False;self.host.close()
    def test_async_source_preview_and_native_copy(self):
        deadline=time.monotonic()+5
        while time.monotonic()<deadline and self.panel.source_text.toPlainText()!='Own reference text':self.panel.pool.waitForDone(100);self.app.processEvents()
        self.assertEqual(self.panel.source_table.rowCount(),1);self.assertEqual(self.panel.source_text.toPlainText(),'Own reference text')
        self.panel.tabs.setCurrentIndex(1);self.panel.source_table.setCurrentCell(0,0);self.panel.copy();self.assertEqual(docs.validate(self.host.budget)[0]['text'],'Own reference text');self.host.undo();self.assertEqual(docs.validate(self.host.budget),[])
    def test_manual_editor_uses_history(self):
        def accept():
            d=self.app.activeModalWidget();d.findChild(QLineEdit,'technical-reference').setText('DOC');d.findChild(QLineEdit,'technical-title').setText('Title');d.findChild(QPlainTextEdit,'technical-text').setPlainText('Manual text');d.accept()
        QTimer.singleShot(0,accept);self.panel.edit(True);self.assertEqual(docs.validate(self.host.budget)[0]['text'],'Manual text');self.assertEqual(self.panel.text.toPlainText(),'Manual text')
    def test_export_original_and_cancel_do_not_modify_project(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from openpresto.storage import dumps
        from openpresto.pzh_entity_texts import catalogue
        docs.copy_source(self.host.budget,catalogue(self.host.budget)[0]['code']);self.panel.render();self.panel.tabs.setCurrentIndex(0);before=dumps(self.host.budget)
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'original.txt'
            with patch('openpresto.technical_documents_panel.QFileDialog.getSaveFileName',return_value=(str(target),'')):self.panel.export_original()
            self.assertEqual(target.read_bytes(),b'Own reference text')
        with patch('openpresto.technical_documents_panel.QFileDialog.getSaveFileName',return_value=('','')):self.panel.export_original()
        self.assertEqual(dumps(self.host.budget),before)

if __name__=='__main__':unittest.main()
