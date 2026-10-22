"""Synthetic PZH issued invoices, proformas and financial isolation."""
import struct
import unittest
from datetime import date
from decimal import Decimal
from openpresto.pzh_importer import _import
from openpresto.pzh_archive import pzh_source_bytes
from openpresto import issued_management as sales, management
from openpresto.pzh_native_modules import results
from openpresto.commands import ProjectSession
from openpresto.storage import dumps,loads,to_dict
from openpresto.budget import BudgetError
from test_pzh_percentages import fixture


def issued_fixture(*, issued=True, proforma=False, wrong_base=False):
    raw=fixture()
    def code(text):return text.encode().ljust(13,b' ')
    def f(tag,fmt,value):return bytes([tag])+struct.pack('<'+fmt,value)
    def record(body,overhead,identifier=1):return struct.pack('<II',len(body),identifier)+bytes(overhead-8)+body
    serial=(date(2020,1,1)-date(1979,12,31)).days
    entity=record(code('CLIENT')+b'\x03Synthetic client\0',8)
    doc=record(struct.pack('<H',serial)+code('INV')+code('CLIENT')+f(2,'B',3)+f(4,'B',int(issued))+f(5,'B',int(proforma))+f(7,'d',30)+f(10,'d',999 if wrong_base else 100)+f(13,'d',10)+f(14,'d',5)+f(16,'d',75),20)
    supply=record(b''.join(code(s) for s in ('INV','CLIENT','ITEM','','','',''))+f(11,'d',1)+f(14,'d',100),32)
    dues=[]
    for identifier,paid,amount in ((1,True,30),(2,False,75)):
        body=struct.pack('<H',serial+identifier)+code('INV')+code('CLIENT')+f(1,'B',0)+f(2,'B',int(paid))+f(4,'d',amount)
        dues.append(record(body,16,identifier))
    new={10:(1,entity),13:(1,doc),14:(1,supply),15:(2,b''.join(dues))}
    # HEADER_BYTES is the public header boundary; use it instead of relying on file offsets.
    from openpresto.pzh_importer import HEADER_BYTES
    boundary=HEADER_BYTES+4+struct.unpack_from('<I',raw,HEADER_BYTES)[0]
    output=bytearray(raw[:boundary])
    for table in range(24):
        count,start,end=struct.unpack_from('<III',raw,0x22+table*88)
        count,payload=new.get(table,(count,raw[start:end]))
        begin=len(output);output+=payload
        struct.pack_into('<III',output,0x22+table*88,count,begin,len(output))
    return bytes(output)


class IssuedPZHTests(unittest.TestCase):
    def imported(self,**options):return _import(issued_fixture(**options),'synthetic.pzh',native_modules=True).budget

    def test_invoice_is_native_draft_and_separate_from_purchases(self):
        b=self.imported();data=sales.validate(b);doc=data['documents'][0]
        self.assertEqual(doc['status'],'draft')
        self.assertEqual(sales.amounts(b,doc),(Decimal('100.00'),Decimal('10.00'),Decimal('5.00'),Decimal('105.00')))
        self.assertEqual(management.state(b)['documents'],[])
        self.assertEqual(management.ledger(b),[])
        self.assertEqual(data['receipts'],[])
        self.assertEqual(data['source_states'][doc['id']]['paid'],'30.0')
        self.assertEqual(to_dict(b)['version'],28)
        self.assertEqual(sales.state(loads(dumps(b))),data)
        self.assertEqual(pzh_source_bytes(b),issued_fixture())

    def test_source_copy_does_not_overwrite_native_edit(self):
        b=self.imported();doc=sales.state(b)['documents'][0]
        sales.set_document(b,kind=doc['kind'],reference='Changed',customer_id=doc['customer_id'],date=doc['date'],lines=doc['lines'],document_id=doc['id'])
        before=dumps(b);sales.copy_source(b,1)
        self.assertEqual(dumps(b),before)

    def test_opening_is_explicit_and_cannot_double_collect(self):
        b=self.imported();rid=sales.state(b)['documents'][0]['id']
        sales.set_status(b,rid,'posted')
        with self.assertRaisesRegex(BudgetError,'apertura'):sales.record_receipt(b,rid,'2020-02-01','75')
        sales.accept_opening(b,rid,'2020-01-31')
        sales.record_receipt(b,rid,'2020-02-01','75',receipt_id='receipt')
        self.assertEqual(sales.document_rows(b)[0][12],Decimal('0.00'))
        before=dumps(b)
        with self.assertRaises(BudgetError):sales.record_receipt(b,rid,'2020-02-02','1')
        self.assertEqual(dumps(b),before)
        with self.assertRaises(BudgetError):sales.set_status(b,rid,'cancelled')
        self.assertEqual(dumps(b),before)

    def test_proformas_cannot_collect_and_received_proformas_convert(self):
        b=self.imported(proforma=True);doc=sales.state(b)['documents'][0]
        self.assertEqual(doc['kind'],'proforma')
        sales.set_status(b,doc['id'],'posted')
        with self.assertRaises(BudgetError):sales.record_receipt(b,doc['id'],'2020-02-01','1')
        received=self.imported(issued=False,proforma=True)
        self.assertEqual(management.state(received)['documents'][0]['kind'],'proforma')
        self.assertEqual(sales.state(received)['documents'],[])

    def test_failed_copy_keeps_budget_and_source_and_reports_pending(self):
        raw=issued_fixture(wrong_base=True);b=_import(raw,'synthetic.pzh',native_modules=True).budget
        self.assertEqual(sales.state(b)['documents'],[])
        self.assertEqual(next(r for r in results(b) if r['module']=='Gestión emitida')['status'],'pending')
        self.assertEqual(pzh_source_bytes(b),raw)

    def test_conversion_failure_rolls_back_only_affected_job(self):
        from unittest.mock import patch
        from openpresto.pzh_native_modules import convert_supported
        b=_import(issued_fixture(),'synthetic.pzh').budget
        def broken(budget,source_id):
            budget.project_metadata['broken_partial_state']='must disappear'
            raise BudgetError('synthetic conversion failure')
        with patch('openpresto.issued_management.copy_source',side_effect=broken):
            convert_supported(b)
        self.assertNotIn('broken_partial_state',b.project_metadata)
        self.assertEqual(next(r for r in results(b) if r['module']=='Gestión emitida')['status'],'pending')
        self.assertEqual(sales.state(b)['documents'],[])
        self.assertEqual(pzh_source_bytes(b),issued_fixture())

    def test_opening_can_be_corrected_only_after_receipts_are_cancelled(self):
        b=self.imported();rid=sales.state(b)['documents'][0]['id']
        sales.set_status(b,rid,'posted');sales.accept_opening(b,rid,'2020-01-31')
        sales.record_receipt(b,rid,'2020-02-01','10',receipt_id='r')
        with self.assertRaises(BudgetError):sales.cancel_opening(b,rid)
        sales.cancel_receipt(b,'r');sales.cancel_opening(b,rid)
        self.assertEqual(sales.state(b)['openings'],{})
        self.assertEqual(sales.state(b)['receipts'],[])

    def test_native_command_is_undoable_and_redoable(self):
        b=_import(issued_fixture(),'synthetic.pzh').budget;session=ProjectSession(b)
        session.execute('pzh.issued.copy',{'source_id':1})
        self.assertEqual(len(sales.state(session.budget)['documents']),1)
        session.undo();self.assertEqual(sales.state(session.budget)['documents'],[])
        session.redo();self.assertEqual(len(sales.state(session.budget)['documents']),1)


if __name__=='__main__':unittest.main()
