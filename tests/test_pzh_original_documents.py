import base64,hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from openpresto import technical_documents as docs,pzh_entity_texts
from openpresto.pzh_importer import _import
from openpresto.storage import dumps,loads,to_dict,StorageError
from openpresto.commands import ProjectSession
from openpresto.budget import BudgetError
from test_technical_documents import fixture


class OriginalDocumentTests(unittest.TestCase):
    def copied(self):
        b=_import(fixture(rtf=True),'own-rtf.pzh').budget;code=pzh_entity_texts.catalogue(b)[0]['code'];docs.copy_source(b,code);return b,code,docs.validate(b)[0]['id']
    def test_original_rtf_survives_edit_and_native_roundtrip(self):
        b,code,rid=self.copied();raw=pzh_entity_texts.read_payload(b,code)['payload'];self.assertTrue(raw.startswith(b'{\\rtf'));self.assertEqual(docs.original_payload(b,rid),raw);docs.set_document(b,'EDIT','Changed','Native edited text',rid)
        saved=loads(dumps(b));self.assertEqual(to_dict(b)['version'],40);self.assertEqual(docs.original_payload(saved,rid),raw);self.assertEqual(docs.validate(saved)[0]['text'],'Native edited text')
    def test_legacy_attachment_preserves_edits_and_is_undoable(self):
        b,code,rid=self.copied();rows=docs.validate(b);rows[0].pop('source_payload');rows[0]['text']='Legacy native edit';docs._save(b,rows);self.assertEqual(to_dict(b)['version'],35);s=ProjectSession(b)
        s.execute('technical.document.attach_original',dict(document_id=rid));self.assertEqual(docs.validate(s.budget)[0]['text'],'Legacy native edit');self.assertTrue(docs.original_payload(s.budget,rid).startswith(b'{\\rtf'));s.undo();self.assertNotIn('source_payload',docs.validate(s.budget)[0]);s.redo();self.assertEqual(docs.validate(s.budget)[0]['text'],'Legacy native edit')
    def test_recopy_upgrades_legacy_copy_without_overwriting_native_text(self):
        b,code,rid=self.copied();rows=docs.validate(b);rows[0].pop('source_payload');rows[0]['text']='Own edits';docs._save(b,rows);docs.copy_source(b,code);self.assertEqual(len(docs.validate(b)),1);self.assertEqual(docs.validate(b)[0]['text'],'Own edits');self.assertTrue(docs.original_payload(b,rid))
    def test_bad_hash_size_encoding_and_original_format_are_rejected(self):
        b,code,rid=self.copied();original=docs.validate(b)
        for key,value in (('sha256','0'*64),('bytes',True),('bytes',999),('data','!invalid!'),('format','text-cp1252')):
            rows=json.loads(json.dumps(original));rows[0]['source_payload'][key]=value
            with self.subTest(key=key),self.assertRaises(BudgetError):docs._save(b,rows)
            self.assertEqual(docs.validate(b),original)
    def test_rtf_binary_groups_are_preserved_without_execution_or_text_invention(self):
        raw=b'{\\rtf1 visible{\\*\\objdata 0102ff}{\\pict abcdef}}';b=_import(fixture(text_payload=raw),'own-embedded-rtf.pzh').budget;code=pzh_entity_texts.catalogue(b)[0]['code'];docs.copy_source(b,code);rid=docs.validate(b)[0]['id'];self.assertEqual(docs.original_payload(loads(dumps(b)),rid),raw);self.assertEqual(docs.validate(b)[0]['text'],'visible')
    def test_original_cannot_be_attached_to_manual_text(self):
        b,_,_=self.copied();docs.set_document(b,'MANUAL','Title','Text');rid=docs.validate(b)[-1]['id'];before=dumps(b)
        with self.assertRaises(BudgetError):docs.attach_original(b,rid)
        self.assertEqual(dumps(b),before)


class CompletionReportTests(unittest.TestCase):
    def test_seven_blocks_are_explicit_read_only_and_never_claim_complete(self):
        from openpresto.pzh_completion import report_rows
        b=_import(fixture(),'own.pzh',native_modules=True).budget;before=dumps(b);rows=report_rows(b);self.assertEqual(len(rows),7);self.assertTrue(all(row[1] not in ('Completo','Compatible') for row in rows));self.assertEqual(dumps(b),before)
    def test_real_conversion_job_categories_retain_pending_reasons(self):
        from openpresto.pzh_completion import report_rows
        from openpresto.pzh_native_modules import KEY
        b=_import(fixture(),'own.pzh').budget;b.project_metadata[KEY]=json.dumps([dict(module='Mediciones presupuestarias',item='Phase1',status='pending',detail='Unknown line kind'),dict(module='Contratos y ofertas',item='Quote1',status='pending',detail='Missing template')]);rows=report_rows(b);self.assertIn('Unknown line kind',rows[1][2]);self.assertIn('Missing template',rows[3][2])
    def test_rootless_project_does_not_invent_file_coverage(self):
        from openpresto.budget import Budget
        from openpresto.reports import report_table
        headers,rows=report_table(Budget(),'pzh_completion');self.assertEqual(rows[0][1],'Sin archivo de referencia')
