import unittest,struct,json
from openpresto import technical_documents as docs,pzh_entity_texts as source
from openpresto.pzh_importer import _Reader,_import,HEADER_BYTES
from openpresto.pzh_archive import pzh_source_bytes
from openpresto.storage import dumps,loads,to_dict,StorageError
from openpresto.commands import ProjectSession
from openpresto.budget import BudgetError
from test_pzh_control import control_fixture
from test_pzh_encoded_header import encode


def fixture(rtf=False,text_payload=None):
    raw=control_fixture();reader=_Reader(raw);boundary=HEADER_BYTES+4+len(reader.config);out=bytearray(raw[:boundary]);code=next(reader.records(10,8))[2][:13]
    text=bytes((123,92))+b'rtf1 Hello'+bytes((92,))+b'par World}' if rtf else b'Own reference text'
    if text_payload is not None:text=text_payload
    payload=struct.pack('<IIBII',17+len(text),0,1,len(text),len(text))+text
    for table in range(24):
        count,start,end=reader.tables[table];body=raw[start:end]
        if table==23:count=1;body=payload
        begin=len(out);out+=body;struct.pack_into('<III',out,34+table*88,count,begin,len(out))
        if table==23:out+=code+struct.pack('<I',begin)
    return encode(bytes(out))


class TechnicalDocumentTests(unittest.TestCase):
    def test_explicit_index_plain_text_and_original_preservation(self):
        raw=fixture();b=_import(raw,'own.pzh',native_modules=True).budget;entries=source.catalogue(b)
        self.assertEqual(len(entries),1);self.assertEqual(source.read(b,entries[0]['code'])['text'],'Own reference text');self.assertEqual(pzh_source_bytes(b),raw)
        docs.copy_source(b,entries[0]['code']);self.assertEqual(to_dict(b)['version'],43);self.assertEqual(docs.validate(b)[0]['text'],'Own reference text')
        self.assertEqual(docs.validate(loads(dumps(b))),docs.validate(b))
    def test_rtf_projection_is_plain_text(self):
        b=_import(fixture(True),'own.pzh').budget;text=source.read(b,source.catalogue(b)[0]['code'])['text'];self.assertIn('Hello',text);self.assertIn('World',text);self.assertNotIn('rtf1',text)
    def test_repeated_copy_preserves_native_edits_and_provenance(self):
        b=_import(fixture(),'own.pzh').budget;code=source.catalogue(b)[0]['code'];docs.copy_source(b,code);old=docs.validate(b)[0];docs.set_document(b,'EDITED','Title','Changed',old['id']);docs.copy_source(b,code)
        self.assertEqual(len(docs.validate(b)),1);self.assertEqual(docs.validate(b)[0]['text'],'Changed');self.assertEqual(docs.validate(b)[0]['source'],old['source'])
    def test_copy_failure_and_duplicate_reference_are_atomic(self):
        b=_import(fixture(),'own.pzh').budget;before=dumps(b)
        with self.assertRaises(BudgetError):docs.copy_source(b,'missing')
        self.assertEqual(dumps(b),before);docs.set_document(b,'MANUAL','Title','Text');before=dumps(b)
        with self.assertRaises(BudgetError):docs.set_document(b,' manual ','Title','Other')
        self.assertEqual(dumps(b),before)
    def test_copy_command_history_and_remove_undo(self):
        b=_import(fixture(),'own.pzh').budget;code=source.catalogue(b)[0]['code'];s=ProjectSession(b);s.execute('technical.document.copy_pzh',dict(code=code));identity=docs.validate(s.budget)[0]['id'];s.execute('technical.document.remove',dict(document_id=identity));self.assertEqual(docs.validate(s.budget),[]);s.undo();self.assertEqual(docs.validate(s.budget)[0]['id'],identity)
    def test_invalid_index_rejected_without_invented_association(self):
        raw=bytearray(fixture());reader=_Reader(bytes(raw));index=reader.tables[23][2];struct.pack_into('<I',raw,index+13,0)
        b=_import(bytes(raw),'bad-index.pzh').budget
        with self.assertRaises(BudgetError):source.catalogue(b)
    def test_corrupt_native_source_and_large_text_rejected(self):
        b=_import(fixture(),'own.pzh').budget;docs.copy_source(b,source.catalogue(b)[0]['code']);data=docs.validate(b);data[0]['source']['sha256']='bad';b.project_metadata[docs.KEY]=json.dumps(data)
        with self.assertRaises(StorageError):dumps(b)
    def test_document_report_does_not_require_an_economic_root(self):
        from openpresto.budget import Budget
        from openpresto.reports import report_html
        b=Budget();docs.set_document(b,'DOC','Title','Line one'+chr(10)+'Line two');html=report_html(b,'documentos_tecnicos_contenido');self.assertIn('Line two',html);self.assertIn('pre-wrap',html);self.assertIn('Sin raíz presupuestaria',html)
    def test_reports_do_not_mutate_budget(self):
        from openpresto.reports import report_table
        b=_import(fixture(),'own.pzh').budget;docs.set_document(b,'DOC','Title','Content');before=dumps(b);self.assertEqual(report_table(b,'documentos_tecnicos_contenido')[1],[('DOC','Title','Content')]);self.assertEqual(dumps(b),before)

if __name__=='__main__':unittest.main()
