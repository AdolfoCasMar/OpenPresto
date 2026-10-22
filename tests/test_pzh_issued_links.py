"""Issued document chains retain their actual source links and financial isolation."""
import struct
import unittest
from unittest.mock import patch
from openpresto.pzh_importer import _Reader,_import,HEADER_BYTES
from openpresto import issued_management as sales,management
from openpresto.pzh_native_modules import results
from openpresto.pzh_archive import pzh_source_bytes
from openpresto.storage import dumps,loads,to_dict
from openpresto.budget import BudgetError
from test_pzh_issued import issued_fixture


def linked_fixture(mixed=False,proforma=False,issued=True):
    raw=issued_fixture();reader=_Reader(raw)
    def code(s):return s.encode().ljust(13,b' ')
    def f(tag,fmt,value):return bytes([tag])+struct.pack('<'+fmt,value)
    def record(body,overhead,identifier):return struct.pack('<II',len(body),identifier)+bytes(overhead-8)+body
    invoice=bytearray(next(reader.records(13,20))[2]);invoice[31]=int(issued);invoice[33]=int(proforma);invoice=bytes(invoice);day=struct.unpack_from('<H',invoice)[0]
    docs=[]
    for identifier,kind,ref in ((2,1,'ORD'),(3,2,'DEL')):
        body=struct.pack('<H',day-3+kind)+code(ref)+code('CLIENT')+f(2,'B',kind)+f(4,'B',int(issued and not mixed))+f(5,'B',0)+f(7+kind,'d',100)
        docs.append(record(body,20,identifier))
    docs.append(record(invoice,20,1))
    supply=next(reader.records(14,32))[2]
    supply=supply[:26]+code('M01')+code('ORD')+code('DEL')+supply[65:]
    replacements={13:(3,b''.join(docs)),14:(1,record(supply,32,1))}
    boundary=HEADER_BYTES+4+struct.unpack_from('<I',raw,HEADER_BYTES)[0]
    output=bytearray(raw[:boundary])
    for t in range(24):
        count,start,end=reader.tables[t];count,payload=replacements.get(t,(count,raw[start:end]))
        begin=len(output);output+=payload;struct.pack_into('<III',output,0x22+t*88,count,begin,len(output))
    return bytes(output)


class IssuedLinksTests(unittest.TestCase):
    def imported(self):return _import(linked_fixture(),'synthetic.pzh').budget

    def test_invoice_copies_order_delivery_and_links_without_stock_or_receipts(self):
        raw=linked_fixture();b=_import(raw,'synthetic.pzh',native_modules=True).budget
        docs=sales.validate(b)['documents'];self.assertEqual([d['kind'] for d in docs],['order','delivery','invoice'])
        self.assertEqual(docs[1]['lines'][0]['source_document'],docs[0]['id'])
        self.assertEqual(docs[2]['lines'][0]['source_document'],docs[1]['id'])
        self.assertTrue(all(d['status']=='draft' and d['lines'][0]['stock'] is False for d in docs))
        self.assertEqual(sales.state(b)['receipts'],[]);self.assertEqual(management.ledger(b),[])
        self.assertTrue(all(r['status']=='available' for r in results(b)))
        self.assertEqual(sales.state(loads(dumps(b))),sales.state(b));self.assertEqual(pzh_source_bytes(b),raw)
        for d in docs:sales.set_status(b,d['id'],'posted')
        self.assertEqual(management.state(b)['documents'],[])
        self.assertEqual(sales.state(b)['receipts'],[])

    def test_linked_proforma_keeps_origin_without_consuming_invoice_capacity(self):
        for issued in (True,False):
            with self.subTest(issued=issued):
                raw=linked_fixture(proforma=True,issued=issued)
                b=_import(raw,'synthetic.pzh',native_modules=True).budget
                engine=sales if issued else management
                docs=engine.validate(b)['documents']
                self.assertEqual([d['kind'] for d in docs],['order','delivery','proforma'])
                order,delivery,proforma=docs
                self.assertEqual(proforma['lines'][0]['source_document'],delivery['id'])
                self.assertEqual(to_dict(b)['version'],28)
                self.assertEqual(engine.state(loads(dumps(b))),engine.state(b))
                for d in docs:engine.set_status(b,d['id'],'posted') if issued else management.set_document_status(b,d['id'],'posted')
                if issued:
                    with self.assertRaises(BudgetError):sales.record_receipt(b,proforma['id'],'2020-02-01','1')
                    shadow=sales._shadow(b,sales.state(b))
                    self.assertEqual(len(management.remaining_source_lines(shadow,delivery['id'])),1)
                    sales.set_document(b,kind='invoice',reference='REAL',customer_id=proforma['customer_id'],date=proforma['date'],lines=proforma['lines'],document_id='actual')
                    sales.set_status(b,'actual','posted')
                    self.assertEqual(management.ledger(b),[])
                else:
                    before=management.ledger(b)
                    self.assertEqual(len(before),1)
                    self.assertEqual(len(management.remaining_source_lines(b,delivery['id'])),1)
                    management.set_document(b,kind='invoice',reference='REAL',supplier_id=proforma['supplier_id'],date=proforma['date'],lines=proforma['lines'],document_id='actual')
                    management.set_document_status(b,'actual','posted')
                    self.assertEqual(management.ledger(b),before)
                shadow=sales._shadow(b,sales.state(b)) if issued else b
                self.assertEqual(management.remaining_source_lines(shadow,delivery['id']),[])
                self.assertEqual(pzh_source_bytes(b),raw)

    def test_repeat_copy_preserves_native_edits(self):
        b=self.imported();sales.copy_source(b,1);before=dumps(b)
        sales.copy_source(b,1);self.assertEqual(dumps(b),before)

    def test_failure_after_parents_is_atomic(self):
        b=self.imported();before=dumps(b);original=sales._copy_source_single
        def fail(budget,source_id,draft,customer):
            if source_id==1:raise BudgetError('invoice conversion failed')
            return original(budget,source_id,draft,customer)
        with patch.object(sales,'_copy_source_single',side_effect=fail):
            with self.assertRaises(BudgetError):sales.copy_source(b,1)
        self.assertEqual(dumps(b),before)

    def test_modified_parent_is_not_overwritten_or_linked_by_position(self):
        b=self.imported();sales.copy_source(b,2);doc=sales.state(b)['documents'][0]
        lines=[dict(doc['lines'][0],unit_price='200')]
        sales.set_document(b,kind=doc['kind'],reference=doc['reference'],customer_id=doc['customer_id'],date=doc['date'],lines=lines,document_id=doc['id'])
        before=dumps(b)
        with self.assertRaisesRegex(BudgetError,'modificado'):sales.copy_source(b,1)
        self.assertEqual(dumps(b),before)

    def test_purchase_antecedents_cannot_be_used_in_sales(self):
        b=_import(linked_fixture(mixed=True),'synthetic.pzh').budget;before=dumps(b)
        with self.assertRaisesRegex(BudgetError,'circuito emitido'):sales.copy_source(b,1)
        self.assertEqual(dumps(b),before)


if __name__=='__main__':unittest.main()
