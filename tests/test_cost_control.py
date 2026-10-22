"""Price comparisons never add document stages or confuse invoices with cash."""
from decimal import Decimal,localcontext
import unittest
from openpresto.budget import BudgetRelation,BudgetError
from openpresto import management as purchases,issued_management as sales,management_advanced as payments
from openpresto.cost_control import snapshot,summary_rows,concept_rows,document_rows
from openpresto.storage import dumps,loads
from test_treasury import budget,invoice


def project():
    b=budget();b.add_relation(BudgetRelation('ROOT','MAT',Decimal(1),1,'r'));return b


class CostControlTests(unittest.TestCase):
    def test_current_price_compares_the_same_invoiced_quantity(self):
        b=project();invoice(b,status='draft');d=purchases.state(b)['documents'][0]
        purchases.set_document(b,kind='invoice',reference='inv',supplier_id='sup',date=d['date'],lines=[dict(d['lines'][0],quantity='2',unit_price='120')],document_id='inv',status='posted')
        before=dumps(b);v=snapshot(b,'2020-01-31');r=concept_rows(v)[0]
        self.assertEqual(v['budget'],Decimal(100));self.assertEqual(r[3:9],(Decimal(2),Decimal(240),Decimal(240),Decimal(200),Decimal(40),Decimal('20.00')))
        self.assertEqual(dumps(b),before);self.assertEqual(snapshot(loads(before),'2020-01-31'),v)

    def test_order_delivery_invoice_are_distinct_stages(self):
        b=project();line=dict(code='MAT',quantity='1',unit_price='100',source_document=None,source_index=None)
        purchases.set_document(b,'order','O','sup','2020-01-01',[line],status='posted',document_id='o')
        purchases.set_document(b,'delivery','D','sup','2020-01-02',[dict(line,source_document='o',source_index=0)],status='posted',document_id='d')
        purchases.set_document(b,'invoice','I','sup','2020-01-03',[dict(line,unit_price='120',source_document='d',source_index=0)],status='posted',document_id='i')
        v=snapshot(b,'2020-01-31');self.assertEqual(v['totals']['purchase_invoice'],Decimal(120))
        self.assertEqual(v['totals']['purchase_order'],Decimal(100));self.assertEqual(v['totals']['purchase_delivery'],Decimal(100))
        self.assertEqual(concept_rows(v)[0][4],Decimal(120));self.assertEqual(len(document_rows(v)),3)

    def test_global_amount_is_visible_without_an_invented_comparable_quantity(self):
        b=project();line=dict(code='MAT',quantity=None,unit_price='150',source_document=None,source_index=None,stock=False)
        purchases.set_document(b,'invoice','GLOBAL','sup','2020-01-01',[line],status='posted')
        v=snapshot(b,'2020-01-31');r=concept_rows(v)[0]
        self.assertEqual(r[4],Decimal(150));self.assertEqual(r[3],'');self.assertEqual(r[6:9],('','',''));self.assertEqual(r[9],1)
        self.assertEqual(v['unknown_lines'],1);self.assertEqual(dict(summary_rows(v))['Referencia actual para esas cantidades'],'')

    def test_current_reference_changes_without_rewriting_the_invoice(self):
        b=project();invoice(b);first=snapshot(b,'2020-01-31')
        from dataclasses import replace
        b.concepts['MAT']=replace(b.concepts['MAT'],base_price=Decimal(90))
        second=snapshot(b,'2020-01-31');self.assertEqual(first['totals'],second['totals'])
        self.assertEqual(concept_rows(second)[0][7],Decimal(10));self.assertEqual(concept_rows(second)[0][8],Decimal('11.11'))

    def test_zero_reference_does_not_create_an_infinite_percentage(self):
        b=project();invoice(b)
        from dataclasses import replace
        b.concepts['MAT']=replace(b.concepts['MAT'],base_price=Decimal(0))
        r=concept_rows(snapshot(b,'2020-01-31'))[0];self.assertEqual(r[7],Decimal(100));self.assertEqual(r[8],'')

    def test_cash_and_invoice_bases_are_separate(self):
        b=project();invoice(b);invoice(b,issued=True,identity='sale')
        payments.record_payment(b,'sup','P1','2020-01-15',[dict(document_id='inv',amount='20')]);sales.record_receipt(b,'sale','2020-01-20','30')
        v=snapshot(b,'2020-01-31');self.assertEqual(v['cash_out'],Decimal(20));self.assertEqual(v['cash_in'],Decimal(30))
        self.assertEqual(v['totals']['purchase_invoice'],Decimal(100));self.assertEqual(v['totals']['sale_invoice'],Decimal(100))

    def test_cut_excludes_later_documents_and_counts_drafts_and_proformas(self):
        b=project();invoice(b,status='draft');invoice(b,kind='proforma',identity='p')
        v=snapshot(b,'2020-01-31');self.assertEqual(v['excluded_drafts'],1);self.assertEqual(v['excluded_proformas'],1);self.assertEqual(v['documents'],[])
        self.assertEqual(snapshot(b,'2019-12-31')['excluded_drafts'],0)
        with self.assertRaises(BudgetError):snapshot(b,'2020-02-31')

    def test_total_rounding_is_preserved_for_comparable_lines(self):
        b=project();lines=[dict(code='MAT',quantity='0.005',unit_price='1',source_document=None,source_index=None),dict(code='MAT',quantity='0.005',unit_price='1',source_document=None,source_index=None)]
        purchases.set_document(b,'invoice','ROUND','sup','2020-01-01',lines,status='posted',rounding='total')
        v=snapshot(b,'2020-01-31');self.assertEqual(v['totals']['purchase_invoice'],Decimal('.01'));self.assertEqual(v['comparable_reference'],Decimal(1))
        with localcontext() as c:
            c.prec=6;self.assertEqual(concept_rows(v)[0][7],Decimal('-.99'))


if __name__=='__main__':unittest.main()
