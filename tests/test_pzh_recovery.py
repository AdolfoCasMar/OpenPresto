"""Partial source recovery never makes incomplete accounting data native."""
import json
import struct
import unittest
from unittest.mock import patch
from openpresto.budget import Budget, BudgetError
from openpresto.pzh_importer import PZHImportError, _Reader, HEADER_BYTES
from openpresto.pzh_operations import import_operations, state, validate, rejected_records, table
from openpresto.pzh_native_management import _proposal, contract_proposal, copy_dues
from openpresto.storage import dumps, loads
from test_pzh_percentages import fixture


class Records:
    def __init__(self, structural=False, short_phase=False):
        self.structural=structural
        self.short_phase=short_phase

    def records(self, table, overhead):
        if table==18 and self.short_phase:
            yield 0,0,b'X'
        if table!=10:return
        prefix=b'SUPPLIER'.ljust(13,b' ')
        yield 0,1,prefix+b'\x03Synthetic supplier\x00'
        yield 0,2,prefix+b'\x0f'+struct.pack('<d',float('nan'))
        yield 0,3,b'SUPPLIER2'.ljust(13,b' ')+b'\x03Second supplier\x00'
        if self.structural:raise PZHImportError('broken record boundary')


class PZHRecoveryTests(unittest.TestCase):
    def test_bad_record_preserves_other_records_and_exact_reason(self):
        b=Budget()
        notes=import_operations(b,Records(),{}, {}, {},modules={'management'})
        self.assertEqual([r['id'] for r in state(b)['entities']],[1,3])
        self.assertEqual(state(b)['unsupported'],[10])
        self.assertEqual(rejected_records(b)[0]['record'],2)
        self.assertIn('número',rejected_records(b)[0]['reason'])
        self.assertTrue(any('PARCIAL' in n for n in notes))
        loaded=loads(dumps(b))
        self.assertEqual(table(loaded,'pzh_rejected')[1][0][:2],(10,2))

    def test_structurally_broken_table_remains_atomic(self):
        b=Budget()
        import_operations(b,Records(structural=True),{}, {}, {},modules={'management'})
        self.assertEqual(state(b)['entities'],[])
        self.assertEqual(state(b)['unsupported'],[10])

    def test_repeated_conversion_does_not_duplicate_rejections(self):
        b=Budget()
        for _ in range(2):import_operations(b,Records(),{}, {}, {},modules={'management'},merge=True)
        self.assertEqual(len(rejected_records(b)),1)
        self.assertEqual(len(state(b)['entities']),2)

    def test_incomplete_document_or_supply_tables_cannot_be_native(self):
        for table_id in (13,14):
            data={'unsupported':[table_id]}
            with self.assertRaisesRegex(BudgetError,'incompletas'):_proposal(Budget(),1,data)
            with self.assertRaisesRegex(BudgetError,'incompletas'):contract_proposal(Budget(),1,data)
        b=Budget()
        import_operations(b,Records(),{}, {}, {},modules={'management'})
        data=state(b);data['unsupported']=[15]
        b.project_metadata['pzh_operations_v1']=json.dumps(data)
        with self.assertRaisesRegex(BudgetError,'incompletas'):copy_dues(b,1)

    def test_short_planning_key_raises_domain_error(self):
        with self.assertRaisesRegex(PZHImportError,'incompleta'):
            import_operations(Budget(),Records(short_phase=True),{}, {}, {},modules={'planning'})

    def test_rejection_inventory_is_validated_on_load(self):
        b=Budget()
        import_operations(b,Records(),{}, {}, {},modules={'management'})
        b.project_metadata['pzh_operations_rejected']='[{"table":10}]'
        with self.assertRaises(BudgetError):validate(b)

    def test_record_header_cannot_be_read_from_next_table(self):
        raw=bytearray(fixture())
        count,start,end=struct.unpack_from('<III',raw,0x22)
        struct.pack_into('<III',raw,0x22,count,start,start+4)
        reader=_Reader(bytes(raw))
        with self.assertRaisesRegex(PZHImportError,'Cabecera de registro'):
            list(reader.records(0,8))


if __name__=='__main__':unittest.main()
