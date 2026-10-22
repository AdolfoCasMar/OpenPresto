import struct,unittest
from openpresto.pzh_assets import _wmf_stream,_wmf_eof_repair,read
from openpresto.pzh_importer import _Reader,_import
from pzh_auxiliary_cases import fixture


def damaged():
    record=struct.pack('<IHhh',5,0x214,10,20)
    return b'OWNWRAP!'+struct.pack('<HHHIHIH',1,9,0x300,17,0,5,0)+record+b'\0'*6


class WMFRecoveryTests(unittest.TestCase):
    def test_repair_only_terminal_size_preserves_geometry_and_envelope(self):
        raw=damaged();self.assertIsNone(_wmf_stream(raw));repair=_wmf_eof_repair(raw)
        self.assertIsNotNone(repair);self.assertEqual(repair['offset'],36);self.assertEqual(repair['data'][:28],raw[8:36]);self.assertEqual(raw[-6:],b'\0'*6)
        self.assertEqual(_wmf_stream(b'OWNWRAP!'+repair['data']),repair['data']);self.assertIsNone(_wmf_eof_repair(b'OWNWRAP!'+repair['data']))
    def test_bounded_padding_and_invalid_records_are_not_guessed(self):
        raw=damaged();self.assertIsNotNone(_wmf_eof_repair(raw+b'\0\0'))
        for bad in (raw[:-1],raw+b'x',raw+b'\0'*18,raw[:26]+b'\0'*4+raw[30:],raw[:14]+struct.pack('<I',999999)+raw[18:]):
            self.assertIsNone(_wmf_eof_repair(bad))
    def test_import_labels_damaged_stream_but_never_silently_replaces_it(self):
        raw=bytearray(fixture());reader=_Reader(raw);start=reader.tables[22][1];at=start+17+8+18;struct.pack_into('<I',raw,at,0)
        budget=_import(bytes(raw),'own-damaged.pzh',native_modules=True).budget;data=read(budget,22,'ITEM')
        self.assertEqual(data['format'],'wmf-damaged');self.assertEqual(data['export'],data['payload']);self.assertEqual(data['payload'][-6:],b'\0'*6);self.assertEqual(data['repair']['data'][-6:],struct.pack('<IH',3,0))
