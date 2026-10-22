import os,unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from openpresto import rich_documents as rich,project_assets
from openpresto.pzh_text import rtf_rich_runs,rtf_plain_text,PZHTextError
from openpresto.budget import BudgetError
from openpresto.storage import dumps,loads,to_dict
from openpresto.commands import ProjectSession
from test_pzh_auxiliary_modules import imported


class ColourRTFTests(unittest.TestCase):
    def test_import_nested_colours_alignment_and_plain_reset(self):
        data=br'{\rtf1{\colortbl ;\red255\green0\blue0;\red0\green0\blue255;}\qc\cf1 Red {\cf2 Blue} Red\plain Auto\par\pard Left}'
        runs=rtf_rich_runs(data)
        self.assertEqual(rich.plain_text(runs),'Red Blue RedAuto\nLeft')
        self.assertEqual(runs[0]['color'],'#ff0000');self.assertEqual(runs[1]['color'],'#0000ff')
        self.assertEqual(runs[2]['color'],'#ff0000');self.assertNotIn('color',runs[3])
        self.assertEqual(runs[3]['alignment'],'center');self.assertNotIn('alignment',runs[-1])
        self.assertEqual(rtf_plain_text(data),rich.plain_text(runs))

    def test_export_roundtrip_and_html_do_not_include_resources(self):
        first=rich.from_plain('Título ñ 😀\n')[0];first.update(color='#245a9b',alignment='center',bold=True)
        second=rich.from_plain('Segundo <script>\n')[0];second.update(color='#b32d35',alignment='right')
        last=rich.from_plain('Normal')[0];runs=[first,second,last]
        self.assertEqual(rtf_rich_runs(rich.to_rtf(runs)),runs)
        html=rich.to_html(runs);self.assertIn('color:#245a9b',html);self.assertIn('text-align:center',html)
        self.assertIn('&lt;script&gt;',html);self.assertNotIn('<script>',html)

    def test_unknown_colour_and_invalid_native_styles_rejected(self):
        for field,value in (('color','red'),('color','#ABCDEF'),('color','url(x)'),('color',None),('alignment','rtl'),('alignment',[])):
            runs=rich.from_plain('x');runs[0][field]=value
            with self.subTest(field=field,value=value),self.assertRaises(BudgetError):rich.validate(runs)
        for data in (br'{\rtf1{\colortbl ;\red999;}\cf1 X}',br'{\rtf1\cf42 X}'):
            with self.assertRaises(PZHTextError):rtf_rich_runs(data)

    def test_hidden_object_colours_do_not_leak_into_visible_document(self):
        data=br'{\rtf1{\colortbl ;\red0\green10\blue20;}\cf1 Visible{\object{\colortbl ;\red255;}hidden}}'
        runs=rtf_rich_runs(data);self.assertEqual(rich.plain_text(runs),'Visible');self.assertEqual(runs[0]['color'],'#000a14')

    def test_extended_document_save_reopen_and_undo_preserve_original(self):
        budget=imported();asset=next(r for r in project_assets.validate(budget) if r['source']['table']==12)
        original=project_assets.read(budget,asset['id'])['original']['payload'];session=ProjectSession(budget)
        runs=rich.from_plain('Own coloured text');runs[0].update(color='#245a9b',alignment='justify')
        session.execute('assets.richtext.set',dict(asset_id=asset['id'],runs=runs))
        self.assertEqual(to_dict(session.budget)['version'],48)
        reopened=loads(dumps(session.budget));self.assertEqual(project_assets.read(reopened,asset['id'])['rich_text'],runs)
        self.assertEqual(project_assets.read(reopened,asset['id'])['original']['payload'],original)
        session.undo();self.assertNotIn('rich_text',project_assets.read(session.budget,asset['id']))
        session.redo();self.assertEqual(project_assets.read(session.budget,asset['id'])['rich_text'],runs)


class ColourEditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])

    def test_colour_and_alignment_controls_preserve_text_and_auto_reset(self):
        from openpresto.rich_text_editor import RichTextDialog,set_runs,get_runs
        from PySide6.QtGui import QTextCursor
        dialog=RichTextDialog(rich.from_plain('First\nSecond'))
        try:
            cursor=dialog.editor.textCursor();cursor.select(QTextCursor.SelectionType.Document);dialog.editor.setTextCursor(cursor)
            dialog.color.setCurrentIndex(dialog.color.findData('#245a9b'))
            dialog.alignment.setCurrentIndex(dialog.alignment.findData('center'))
            runs=dialog.runs();self.assertTrue(all(r.get('color')=='#245a9b' and r.get('alignment')=='center' for r in runs))
            self.assertEqual(rich.plain_text(runs),'First\nSecond')
            self.assertEqual(rtf_rich_runs(rich.to_rtf(runs)),runs)
            dialog.color.setCurrentIndex(0);dialog.alignment.setCurrentIndex(0)
            self.assertTrue(all('color' not in r and 'alignment' not in r for r in dialog.runs()))
            set_runs(dialog.editor,runs);self.assertEqual(get_runs(dialog.editor),runs)
        finally:dialog.close();dialog.deleteLater();self.app.processEvents()


if __name__=='__main__':unittest.main()
