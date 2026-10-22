"""Entity text extensions and non-financial control records are distinct types."""
import struct
import unittest
from openpresto.pzh_importer import _import,_Reader,_fields,PZHImportError,HEADER_BYTES
from openpresto.pzh_operations import state,rejected_records
from openpresto.pzh_native_modules import control_records,results
from openpresto.pzh_archive import pzh_source_bytes
from openpresto.commands import ProjectSession
from openpresto import management,issued_management
from openpresto.storage import dumps,loads,to_dict
from test_pzh_issued import issued_fixture

RAW_PROPERTY=bytes.fromhex('000000000000f8f7')


def control_fixture(kind=5, certified=1250.5):
    raw=issued_fixture();reader=_Reader(raw)
    def record(body,overhead):return struct.pack('<II',len(body),1)+bytes(overhead-8)+body
    entity=next(reader.records(10,8))[2]
    entity+=b'\x20'+struct.pack('<d',certified)+b'\x25Title\0\x26College\0\x27Registration\0'
    doc=bytearray(next(reader.records(13,20))[2]);doc[29]=kind;doc[33]=2
    doc[35:43]=RAW_PROPERTY
    replacements={10:(1,record(entity,8)),13:(1,record(bytes(doc),20)),14:(0,b''),15:(0,b'')}
    boundary=HEADER_BYTES+4+struct.unpack_from('<I',raw,HEADER_BYTES)[0]
    output=bytearray(raw[:boundary])
    for t in range(24):
        count,start,end=reader.tables[t]
        count,payload=replacements.get(t,(count,raw[start:end]));begin=len(output);output+=payload
        struct.pack_into('<III',output,0x22+t*88,count,begin,len(output))
    return bytes(output)


class PZHControlTests(unittest.TestCase):
    def test_text_entity_extensions_are_preserved_without_numeric_coercion(self):
        raw=control_fixture();b=_import(raw,'synthetic.pzh').budget
        fields=state(b)['entities'][0]['fields']
        self.assertEqual(fields['32'],'1250.5')
        self.assertEqual([fields[str(k)] for k in (37,38,39)],['Title','College','Registration'])
        self.assertEqual(state(loads(dumps(b)))['entities'][0]['fields'],fields)
        self.assertEqual(rejected_records(b),[])
        self.assertEqual(pzh_source_bytes(b),raw)

    def test_entity_certified_amount_does_not_consume_following_text_fields(self):
        for amount in (0, -15.25, 1000000.125):
            with self.subTest(amount=amount):
                b=_import(control_fixture(certified=amount),'synthetic.pzh').budget
                fields=state(b)['entities'][0]['fields']
                self.assertEqual(float(fields['32']),amount)
                self.assertEqual(fields['37'],'Title')
                self.assertEqual(rejected_records(b),[])

    def test_invalid_entity_certified_amount_is_not_accepted_as_text(self):
        for amount in (float('nan'),float('inf')):
            with self.subTest(amount=amount):
                b=_import(control_fixture(certified=amount),'synthetic.pzh').budget
                self.assertEqual(state(b)['entities'],[])
                self.assertEqual(len(rejected_records(b)),1)

    def test_control_property_is_opaque_not_a_financial_amount(self):
        b=_import(control_fixture(),'synthetic.pzh',native_modules=True).budget
        source=state(b)['documents'][0]
        self.assertEqual(source['kind'],5)
        self.assertIsNone(source['amount']);self.assertIsNone(source['invoice_base'])
        self.assertFalse(source['proforma'])
        record=control_records(b)[0]
        self.assertEqual(record['state'],2)
        self.assertEqual(record['source_fields']['7'],RAW_PROPERTY.hex())
        self.assertEqual(management.state(b)['documents'],[])
        self.assertEqual(issued_management.state(b)['documents'],[])
        self.assertEqual(management.ledger(b),[])
        from openpresto.pzh_native_management import rows as purchase_candidates
        self.assertEqual(purchase_candidates(b),[])
        self.assertEqual(issued_management.source_rows(b),[])
        self.assertEqual(next(r for r in results(b) if r['module']=='Registros de control')['status'],'available')
        self.assertEqual(to_dict(b)['version'],28)
        self.assertEqual(control_records(loads(dumps(b))),control_records(b))

    def test_control_property_cannot_bypass_real_invoice_numeric_validation(self):
        b=_import(control_fixture(kind=3),'synthetic.pzh').budget
        self.assertEqual(state(b)['documents'],[])
        self.assertEqual(len(rejected_records(b)),1)

    def test_raw_property_keeps_bounds_check(self):
        with self.assertRaises(PZHImportError):_fields(b'\x07\x00',{7:'raw8'},'synthetic')

    def test_record_edit_is_undoable_without_changing_source_properties(self):
        raw=control_fixture();b=_import(raw,'synthetic.pzh',native_modules=True).budget
        row=control_records(b)[0];session=ProjectSession(b)
        session.execute('pzh.record.set',dict(record_id=row['id'],state=3,note='Reviewed'))
        self.assertEqual(control_records(session.budget)[0]['state'],3)
        self.assertEqual(control_records(session.budget)[0]['source_fields'],row['source_fields'])
        session.undo();self.assertEqual(control_records(session.budget)[0]['state'],2)
        session.redo();self.assertEqual(control_records(session.budget)[0]['note'],'Reviewed')
        self.assertEqual(pzh_source_bytes(session.budget),raw)


if __name__=='__main__':unittest.main()
