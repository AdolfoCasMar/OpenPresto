import unittest
from datetime import date,timedelta
from decimal import Decimal,localcontext
from openpresto import management,issued_management,management_advanced,management_schedule
from openpresto.receivables_aging import snapshot,HEADERS,DETAIL_HEADERS
from openpresto.storage import dumps,loads
from openpresto.reports import report_table,report_csv
from test_treasury import budget,invoice,scheduled
from test_pzh_issued import issued_fixture
from openpresto.pzh_importer import _import


def plain_invoice(b,identity,due,issued=False,party=None,kind='invoice'):
    kwargs=dict(kind=kind,reference=identity,date='2020-01-01',due_date=due,status='posted',document_id=identity,lines=[dict(code='MAT',quantity='1',unit_price='100',source_document=None,source_index=None)])
    if issued:issued_management.set_document(b,customer_id=party or 'cust',**kwargs)
    else:management.set_document(b,supplier_id=party or 'sup',**kwargs)


class AgingTests(unittest.TestCase):
    def test_bucket_boundaries_and_undated_amounts(self):
        b=budget();cut=date(2020,7,1)
        for i,days in enumerate((0,1,30,31,60,61,90,91,-1)):
            plain_invoice(b,'inv'+str(i),(cut-timedelta(days=days)).isoformat())
        plain_invoice(b,'undated',None)
        view=snapshot(b,cut.isoformat());self.assertEqual(len(view['rows']),1)
        self.assertEqual(view['rows'][0][5:12],tuple(map(Decimal,('200','200','200','200','100','100','1000'))))
        self.assertEqual(view['totals']['out']['overdue'],Decimal(700));self.assertEqual(view['totals']['out']['undated'],Decimal(100))
        undated=next(r for r in view['details'] if r[2]=='undated');self.assertEqual(undated[6:9],('','','Sin fecha'))

    def test_customer_supplier_and_equal_names_are_not_netted_or_merged(self):
        b=budget();management.set_supplier(b,'Supplier',supplier_id='other')
        plain_invoice(b,'one','2020-02-01');plain_invoice(b,'two','2020-02-01',party='other');plain_invoice(b,'sale','2020-02-01',issued=True)
        view=snapshot(b,'2020-02-10');self.assertEqual(len(view['rows']),3)
        self.assertEqual(view['totals']['in']['known'],Decimal(100));self.assertEqual(view['totals']['out']['known'],Decimal(200))
        self.assertEqual({r[1] for r in view['rows'] if r[0]=='Pagar'},{'sup','other'})

    def test_partial_payment_and_opening_cover_oldest_dues_without_new_cash(self):
        b=budget();scheduled(b);management_schedule.set_opening(b,'inv','2020-01-10','10','Own opening')
        management_advanced.record_payment(b,'sup','Own payment','2020-01-15',[dict(document_id='inv',amount='20')])
        view=snapshot(b,'2020-02-15');normal=next(r for r in view['rows'] if r[4]=='Ordinario')
        self.assertEqual(normal[5:12],tuple(map(Decimal,('65','10','0','0','0','0','75'))))
        self.assertEqual(view['totals']['out']['known'],Decimal(80));self.assertTrue(all(r[9]!=Decimal(20) for r in view['details']))

    def test_retention_and_ordinary_balances_remain_separate(self):
        b=budget();invoice(b);view=snapshot(b,'2020-03-02')
        ordinary=next(r for r in view['rows'] if r[4]=='Ordinario');retention=next(r for r in view['rows'] if r[4]=='Retención')
        self.assertEqual(ordinary[6],Decimal(105));self.assertEqual(retention[10],Decimal(5));self.assertEqual(retention[6],Decimal(0))

    def test_optional_proformas_and_actual_receipts_are_not_debt(self):
        b=budget();plain_invoice(b,'inv','2020-02-01',issued=True);plain_invoice(b,'pf','2020-02-01',issued=True,kind='proforma');issued_management.record_receipt(b,'inv','2020-01-15','40')
        self.assertEqual(snapshot(b,'2020-02-10')['totals']['in']['known'],Decimal(60))
        view=snapshot(b,'2020-02-10',True);self.assertEqual(view['totals']['in']['known'],Decimal(160));self.assertEqual({r[3] for r in view['rows']},{'Factura','Proforma'})

    def test_unreviewed_source_balances_are_not_declared_zero(self):
        b=_import(issued_fixture(),'synthetic.pzh').budget;issued_management.copy_source(b,1);identity=issued_management.state(b)['documents'][0]['id'];issued_management.set_status(b,identity,'posted')
        view=snapshot(b,'2020-01-31');self.assertGreater(view['totals']['in']['reviews'],0)
        self.assertTrue(any(r[9]=='' and r[10] for r in view['details']))

    def test_cancelled_payment_and_future_documents_follow_treasury_cut(self):
        b=budget();plain_invoice(b,'inv','2020-02-01')
        management_advanced.record_payment(b,'sup','Own payment','2020-01-15',[dict(document_id='inv',amount='20')],payment_id='p');management_advanced.cancel_payment(b,'p','2020-01-25','Own cancellation')
        self.assertEqual(snapshot(b,'2020-01-20')['totals']['out']['known'],Decimal(80));self.assertEqual(snapshot(b,'2020-01-31')['totals']['out']['known'],Decimal(100));self.assertEqual(snapshot(b,'2019-12-31')['rows'],[])

    def test_readonly_precision_persistence_and_reports(self):
        b=budget();scheduled(b);before=dumps(b);view=snapshot(b,'2020-02-15')
        with localcontext() as context:
            context.prec=3;self.assertEqual(snapshot(b,'2020-02-15'),view)
        self.assertEqual(dumps(b),before);self.assertEqual(snapshot(loads(before),'2020-02-15'),view)
        self.assertEqual(report_table(b,'antiguedad:2020-02-15:resumen'),(HEADERS,view['rows']));self.assertEqual(report_table(b,'antiguedad:2020-02-15:detalle'),(DETAIL_HEADERS,view['details']))
        self.assertIn('Supplier',report_csv(b,'antiguedad:2020-02-15:resumen'))
        for kind in ('antiguedad:2020-01-01','antiguedad:2020-01-01:bad','antiguedad:2020-01-01:resumen:bad'):
            with self.assertRaises(ValueError):report_table(b,kind)
