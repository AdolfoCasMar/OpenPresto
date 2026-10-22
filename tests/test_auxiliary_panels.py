import os,time,tempfile,unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication,QDialog,QLineEdit,QPlainTextEdit,QComboBox
from openpresto.mdi_workspace import PrestoWorkspace
from openpresto import project_assets,agenda,entities
from openpresto.storage import dumps
from test_pzh_auxiliary_modules import imported


class AuxiliaryPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setOrganizationName('OpenPrestoTests');cls.app.setApplicationName('AuxiliaryPanels')
    def setUp(self):
        self.h=PrestoWorkspace();self.h.budget=imported();self.h._reset_history();self.h._open_views();self.h.section_ui.tabs.setCurrentIndex(3);self.panel=self.h.panels['gestion'][1].technical_documents.assets
    def tearDown(self):
        self.panel.pool.waitForDone(5000);self.h.panels['gestion'][1].technical_documents.pool.waitForDone(5000);self.h.dirty=False;self.h.close()
    def ready(self,table):
        i=next(i for i,r in enumerate(project_assets.validate(self.h.budget)) if r['source']['table']==table);self.panel.table.setCurrentCell(i,1);self.panel.select();end=time.monotonic()+4
        while self.panel.current is None and time.monotonic()<end:self.panel.pool.waitForDone(100);self.app.processEvents()
        self.assertIsNotNone(self.panel.current);self.assertEqual(self.panel.current['source']['table'],table)
    def test_image_preview_and_export_keep_project_unchanged(self):
        self.ready(21);self.assertIsNotNone(self.panel.current['image']);self.assertFalse(self.panel.current['image'].isNull());before=dumps(self.h.budget)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'own.bmp'
            with patch('openpresto.project_assets_panel.QFileDialog.getSaveFileName',return_value=(str(path),'')):self.panel.export()
            self.assertEqual(path.read_bytes(),self.panel.current['original']['export'])
        self.assertEqual(dumps(self.h.budget),before)
    def test_native_text_editor_and_undo_keep_original_stream(self):
        self.ready(3);rid=self.panel.current['id'];original=self.panel.current['original']['payload']
        def accept(dialog):
            dialog.findChild(QLineEdit,'asset-title').setText('Edited own title');dialog.findChild(QPlainTextEdit,'asset-text').setPlainText('Edited own text');return QDialog.DialogCode.Accepted
        with patch('openpresto.project_assets_panel.QDialog.exec',new=accept):self.panel.edit()
        self.assertEqual(project_assets.read(self.h.budget,rid)['text'],'Edited own text');self.assertEqual(project_assets.read(self.h.budget,rid)['original']['payload'],original);self.assertEqual(len(self.h._undo),1);self.h.undo();self.assertEqual(project_assets.read(self.h.budget,rid)['text'],'Own specification')
    def test_source_keywords_are_used_in_budget_filter(self):
        self.h.section_ui.tabs.setCurrentIndex(0);self.h.current_code=self.h.budget.root_code;self.h.refresh();self.h.search.setText('hiddenword');matches=[i for i in range(self.h.prices.rowCount()) if self.h.prices.item(i,0).text()=='ITEM'];self.assertTrue(matches);self.assertFalse(self.h.prices.isRowHidden(matches[0]));self.assertNotIn('hiddenword',self.h.budget.concepts)
    def test_agenda_editor_uses_one_undo_and_no_payment(self):
        self.h.section_ui.tabs.setCurrentIndex(2);panel=self.h.panels['planificacion'][1].agenda
        def accept(dialog):
            dialog.findChild(QLineEdit,'agenda-date').setText('2020-02-01');dialog.findChild(QLineEdit,'agenda-note').setText('Own note');dialog.findChild(QComboBox,'agenda-holiday').setCurrentIndex(1);return QDialog.DialogCode.Accepted
        with patch('openpresto.agenda_panel.QDialog.exec',new=accept):panel.edit(True)
        self.assertEqual(len(agenda.validate(self.h.budget)),2);self.assertEqual(len(self.h._undo),1);self.h.undo();self.assertEqual(len(agenda.validate(self.h.budget)),1)
