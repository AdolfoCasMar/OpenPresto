"""Explicit document-line links prevent duplicate fulfilment and guessed matching."""
from decimal import Decimal
import unittest
from openpresto import management
from openpresto.procurement_tracking import snapshot,order_rows,delivery_rows
from openpresto.storage import dumps,loads
from openpresto.budget import BudgetError
from test_cost_control import project


def document(b,kind,reference,quantity,origin=None,index=None,date='2020-01-01',status='posted'):
    line=dict(code='MAT',quantity=str(quantity) if quantity is not None else None,unit_price='100',source_document=origin,source_index=index)
    if quantity is None:line['stock']=False
    management.set_document(b,kind,reference,'sup',date,[line],status=status,document_id=reference)


def chain(via=4,direct=2):
    b=project();document(b,'order','ORDER',10)
    document(b,'delivery','DELIVERY',6,'ORDER',0,'2020-01-02')
    document(b,'invoice','INVOICE',via,'DELIVERY',0,'2020-01-03')
    document(b,'invoice','DIRECT',direct,'ORDER',0,'2020-01-04')
    return b


class ProcurementTrackingTests(unittest.TestCase):
    def test_invoice_against_delivery_does_not_fulfil_order_twice(self):
        b=chain();before=dumps(b);v=snapshot(b,'2020-01-31');r=v['orders'][0]
        self.assertEqual((r['quantity'],r['delivered'],r['direct'],r['billed']),(Decimal(10),Decimal(6),Decimal(2),Decimal(6)))
        self.assertEqual((r['unfulfilled'],r['uninvoiced']),(Decimal(2),Decimal(4)))
        self.assertEqual(v['deliveries'][0]['uninvoiced'],Decimal(2))
        self.assertEqual(dumps(b),before);self.assertEqual(snapshot(loads(before),'2020-01-31'),v)

    def test_cut_excludes_later_links(self):
        b=chain();early=snapshot(b,'2020-01-01')['orders'][0];middle=snapshot(b,'2020-01-03')['orders'][0]
        self.assertEqual(early['unfulfilled'],Decimal(10));self.assertEqual(early['uninvoiced'],Decimal(10))
        self.assertEqual(middle['unfulfilled'],Decimal(4));self.assertEqual(middle['uninvoiced'],Decimal(6))

    def test_complete_rows_are_hidden_only_by_the_pending_filter(self):
        v=snapshot(chain(via=6,direct=4),'2020-01-31')
        self.assertEqual(len(order_rows(v)),1);self.assertEqual(order_rows(v,True),[])
        self.assertEqual(delivery_rows(v,True),[]);self.assertEqual(len(v['links']),3)

    def test_proforma_does_not_consume_order_or_delivery_capacity(self):
        b=chain();before=snapshot(b,'2020-01-31')
        document(b,'proforma','PROFORMA',10,'ORDER',0,'2020-01-05')
        after=snapshot(b,'2020-01-31');self.assertEqual(after['orders'],before['orders']);self.assertEqual(after['deliveries'],before['deliveries'])
        self.assertEqual(after['excluded_proformas'],1)

    def test_unlinked_invoice_is_not_matched_by_resource_code(self):
        b=chain();before=snapshot(b,'2020-01-31');document(b,'invoice','STANDALONE',5,date='2020-01-05')
        after=snapshot(b,'2020-01-31');self.assertEqual(after['orders'],before['orders'])
        row=next(r for r in after['links'] if r[0]=='STANDALONE');self.assertEqual(row[7:9],('',''))

    def test_repeated_resource_lines_follow_the_exact_origin_index(self):
        b=project();line=dict(code='MAT',quantity='4',unit_price='100',source_document=None,source_index=None)
        management.set_document(b,'order','ORDER','sup','2020-01-01',[line,dict(line,quantity='6')],status='posted',document_id='ORDER')
        document(b,'delivery','DELIVERY',3,'ORDER',1,'2020-01-02')
        rows=snapshot(b,'2020-01-31')['orders'];self.assertEqual(rows[0]['unfulfilled'],Decimal(4));self.assertEqual(rows[1]['unfulfilled'],Decimal(3))

    def test_global_order_keeps_unknown_quantity_visible(self):
        b=project();document(b,'order','GLOBAL',None);v=snapshot(b,'2020-01-31');r=v['orders'][0]
        self.assertIsNone(r['quantity']);self.assertIsNone(r['unfulfilled']);self.assertIsNone(r['uninvoiced'])
        self.assertEqual(order_rows(v,True)[0][6],'');self.assertEqual(order_rows(v,True)[0][10],'')

    def test_drafts_and_current_cancellations_do_not_reduce_pending_quantities(self):
        b=chain();management.set_document_status(b,'DIRECT','cancelled')
        r=snapshot(b,'2020-01-31')['orders'][0];self.assertEqual(r['unfulfilled'],Decimal(4));self.assertEqual(r['uninvoiced'],Decimal(6))
        document(b,'delivery','DRAFT',1,'ORDER',0,'2020-01-06',status='draft')
        v=snapshot(b,'2020-01-31');self.assertEqual(v['excluded_drafts'],1);self.assertEqual(v['orders'][0],r)
        with self.assertRaises(BudgetError):snapshot(b,'2020-02-31')


if __name__=='__main__':unittest.main()
