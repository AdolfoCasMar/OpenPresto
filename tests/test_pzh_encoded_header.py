"""Own synthetic cyclic-header fixtures; original source bytes stay untouched."""
import struct,unittest,re
from openpresto.pzh_importer import _Reader,_import,HEADER_BYTES,PZHImportError
from openpresto.pzh_archive import pzh_source_bytes
from openpresto.storage import dumps,loads
from test_pzh_control import control_fixture


def encode(raw,key=b'13579'):
    length=struct.unpack_from('<I',raw,HEADER_BYTES)[0];boundary=HEADER_BYTES+4+length
    def part(value):return bytes((c+key[i%5])%256 for i,c in enumerate(value))
    result=bytearray(raw[:24]+part(raw[24:HEADER_BYTES])+part(raw[HEADER_BYTES:HEADER_BYTES+4])+part(raw[HEADER_BYTES+4:boundary])+raw[boundary:])
    struct.pack_into('<I',result,20,1);return bytes(result)


def without_phases(raw,reference_only=False):
    reader=_Reader(raw);pattern=b''.join(bytes([t])+b'.' for t in range(0xef,0xf8));config=re.sub(pattern,b'',reader.config,flags=re.DOTALL)
    out=bytearray(raw[:HEADER_BYTES]);out+=struct.pack('<I',len(config))+config
    for table in range(24):
        count,start,end=reader.tables[table];payload=raw[start:end]
        if reference_only:
            if table==0:
                offset,identity,body=next(reader.records(0,8));payload=struct.pack('<II',len(body),identity)+body;count=1
            elif table!=10:count=0;payload=b''
        begin=len(out);out+=payload;struct.pack_into('<III',out,34+table*88,count,begin,len(out))
    return bytes(out)


class EncodedHeaderTests(unittest.TestCase):
    def test_synthetic_variant_has_identical_domain_values_and_exact_source(self):
        plain=control_fixture();coded=encode(plain);p=_import(plain,'own.pzh',native_modules=True).budget;c=_import(coded,'own-coded.pzh',native_modules=True).budget
        self.assertEqual(p.concepts,c.concepts);self.assertEqual(p.relations,c.relations);self.assertEqual(p.total(),c.total());self.assertEqual(_Reader(coded).config,_Reader(plain).config)
        self.assertEqual(pzh_source_bytes(c),coded);self.assertEqual(pzh_source_bytes(loads(dumps(c))),coded)
    def test_each_header_block_restarts_cycle(self):
        raw=control_fixture()
        for key in (b'00000',b'24680',b'98765'):
            reader=_Reader(encode(raw,key));self.assertTrue(reader.encoded_header);self.assertEqual(reader.tables,_Reader(raw).tables)
    def test_invalid_signature_truncation_and_pointer_rejected(self):
        raw=bytearray(encode(control_fixture()));raw[64]=0
        with self.assertRaises(PZHImportError):_Reader(bytes(raw))
        raw=encode(control_fixture())
        with self.assertRaises(PZHImportError):_Reader(raw[:HEADER_BYTES])
        plain=bytearray(control_fixture());struct.pack_into('<I',plain,38,len(plain)+100)
        with self.assertRaises(PZHImportError):_Reader(encode(bytes(plain)))
    def test_phase_less_reference_profile_does_not_invent_approval(self):
        raw=encode(without_phases(control_fixture(),True));reader=_Reader(raw)
        self.assertTrue(reader.reference_only);self.assertIsNone(reader.approved_phase);self.assertIsNone(reader.certification_phase)
        b=_import(raw,'own-reference.pzh',native_modules=True).budget
        self.assertEqual(b.project_metadata['pzh_reference_only'],'1');self.assertEqual(b.relations,[]);self.assertEqual(pzh_source_bytes(b),raw)
    def test_phase_less_economic_graph_is_still_rejected(self):
        for raw in (without_phases(control_fixture()),encode(without_phases(control_fixture()))):
            with self.assertRaises(PZHImportError):_Reader(raw)
    def test_plain_fixture_remains_unmodified(self):
        raw=control_fixture();reader=_Reader(raw);self.assertFalse(reader.encoded_header);self.assertEqual(reader.data,raw)

if __name__=='__main__':unittest.main()
