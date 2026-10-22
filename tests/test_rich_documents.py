import copy,os,unittest,tempfile,time
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from openpresto import rich_documents as rich,project_assets
from openpresto.pzh_text import rtf_rich_runs,rtf_plain_text
from openpresto.budget import BudgetError
from openpresto.commands import ProjectSession
from openpresto.storage import dumps,loads,to_dict
from test_pzh_auxiliary_modules import imported


class RichDocumentTests(unittest.TestCase):
    def test_nested_rtf_styles_and_reset(self):
        runs=rtf_rich_runs(br'{\rtf1 plain {\b bold {\i both} bold}\fs30 big\plain reset}')
        self.assertEqual(rich.plain_text(runs),'plain bold both boldbigreset')
        both=next(r for r in runs if r['text']=='both');self.assertTrue(both['bold']);self.assertTrue(both['italic'])
        self.assertEqual(runs[-2]['size'],15);self.assertFalse(runs[-1]['bold']);self.assertEqual(runs[-1]['size'],12)
    def test_rtf_export_unicode_escapes_and_styles_round_trip(self):
        runs=rich.from_plain('Presupuesto ñ 😀 {x} \\ primera\nsegunda\tfin')
        runs[0].update(bold=True,italic=True,underline=True,strike=True,size=13.5)
        encoded=rich.to_rtf(runs);self.assertEqual(rtf_rich_runs(encoded),runs);self.assertEqual(rtf_plain_text(encoded),runs[0]['text'])
    def test_opaque_objects_are_not_text_or_executed(self):
        runs=rtf_rich_runs(br'{\rtf1 Visible{\object hidden}{\pict hidden}{\*\unknown hidden}\b yes}')
        self.assertEqual(rich.plain_text(runs),'Visibleyes');self.assertTrue(runs[-1]['bold'])
    def test_invalid_runs_rejected(self):
        for value in (None,{},[{}],rich.from_plain('x')+['bad']):
            with self.assertRaises(BudgetError):rich.validate(value)
        for key,value in (('size',True),('size',float('nan')),('size',12.1),('bold',1),('text','\ud800')):
            runs=rich.from_plain('x');runs[0][key]=value
            with self.assertRaises(BudgetError):rich.validate(runs)
    def test_native_save_reopen_original_and_undo(self):
        budget=imported();asset=next(r for r in project_assets.validate(budget) if r['source']['table']==12);identifier=asset['id'];original=project_assets.read(budget,identifier)['original']['payload'];session=ProjectSession(budget);runs=rich.from_plain('Own edited text');runs[0]['underline']=True
        session.execute('assets.richtext.set',dict(asset_id=identifier,runs=runs));self.assertEqual(to_dict(session.budget)['version'],47)
        reopened=loads(dumps(session.budget));self.assertEqual(project_assets.read(reopened,identifier)['rich_text'],runs);self.assertEqual(project_assets.read(reopened,identifier)['original']['payload'],original)
        session.undo();self.assertNotIn('rich_text',project_assets.read(session.budget,identifier));session.redo();self.assertEqual(project_assets.read(session.budget,identifier)['text'],'Own edited text')
    def test_plain_edit_clears_format_and_binary_target_is_atomic(self):
        b=imported();assets=project_assets.validate(b);text=assets[0]['id'];project_assets.set_rich_text(b,text,rich.from_plain('formatted'));project_assets.set_asset(b,text,'Own title','note','plain');self.assertNotIn('rich_text',project_assets.read(b,text))
        binary=next(r['id'] for r in assets if r['source']['table']==21);before=dumps(b)
        with self.assertRaises(BudgetError):project_assets.set_rich_text(b,binary,rich.from_plain('bad'))
        self.assertEqual(dumps(b),before)
    def test_mismatched_plain_projection_rejected(self):
        b=imported();data=project_assets.validate(b);data[0].update(text='other',rich_text=rich.from_plain('different'))
        with self.assertRaises(BudgetError):project_assets.validate(b,data)


class RichEditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([]);cls.app.setOrganizationName('OpenPrestoTests');cls.app.setApplicationName('RichEditor')
    def test_editor_toolbar_unicode_paragraphs_and_roundtrip(self):
        from openpresto.rich_text_editor import RichTextDialog,set_runs,get_runs
        from PySide6.QtGui import QTextCursor
        runs=rich.from_plain('One 😀\n\nTwo\n');dialog=RichTextDialog(runs);self.assertEqual(rich.plain_text(get_runs(dialog.editor)),runs[0]['text'])
        cursor=dialog.editor.textCursor();cursor.select(QTextCursor.SelectionType.Document);dialog.editor.setTextCursor(cursor);dialog.styles['bold'].click();dialog.size.setValue(14.5)
        self.assertTrue(all(r['bold'] for r in dialog.runs()));self.assertTrue(all(r['size']==14.5 for r in dialog.runs()));self.assertEqual(rtf_plain_text(rich.to_rtf(dialog.runs())),runs[0]['text'].strip('\r\n'));dialog.close()
    def test_real_asset_dialog_single_undo_and_edited_rtf_export(self):
        from openpresto.mdi_workspace import PrestoWorkspace
        from openpresto.rich_text_editor import set_runs
        from PySide6.QtWidgets import QDialog
        host=PrestoWorkspace();host.budget=imported();host._reset_history();host._open_views();host.section_ui.tabs.setCurrentIndex(3);panel=host.panels['gestion'][1].technical_documents.assets
        try:
            index=next(i for i,r in enumerate(project_assets.validate(host.budget)) if r['source']['table']==12);panel.table.setCurrentCell(index,1);panel.select()
            def ready():
                end=time.monotonic()+5
                while panel.current is None and time.monotonic()<end:panel.pool.waitForDone(100);self.app.processEvents()
                self.assertIsNotNone(panel.current)
            ready();identifier=panel.current['id'];runs=rich.from_plain('Own revised note');runs[0]['bold']=True
            def accept(dialog):set_runs(dialog.editor,runs);return QDialog.DialogCode.Accepted
            with patch('openpresto.project_assets_panel.RichTextDialog.exec',new=accept):panel.edit_rich()
            self.assertEqual(len(host._undo),1);self.assertEqual(project_assets.read(host.budget,identifier)['rich_text'],runs);ready()
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'edited.rtf'
                with patch('openpresto.project_assets_panel.QFileDialog.getSaveFileName',return_value=(str(path),'')):panel.export_rich()
                self.assertEqual(rtf_rich_runs(path.read_bytes()),runs)
            host.undo();self.assertNotIn('rich_text',project_assets.read(host.budget,identifier))
        finally:
            panel.pool.waitForDone(5000);self.app.processEvents();host.dirty=False;host.close()
