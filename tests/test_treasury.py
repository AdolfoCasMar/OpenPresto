"""Cash projection separates actual records, openings and undated forecasts."""
import unittest
from decimal import Decimal,localcontext
from openpresto.budget import Budget,BudgetConcept,BudgetError
from openpresto import management as purchases,issued_management as sales,management_advanced as payments,management_schedule as schedules
from openpresto.treasury import snapshot,month_rows,detail_rows
from openpresto.storage import dumps,loads
from openpresto.pzh_importer import _import
from test_pzh_issued import issued_fixture


def budget():
    b=Budget();b.add_concept(BudgetConcept('ROOT'));b.add_concept(BudgetConcept('MAT',nature='material',base_price=Decimal(100)));b.set_root('ROOT')
    purchases.set_supplier(b,'Supplier',supplier_id='sup');sales.set_customer(b,'Customer',customer_id='cust')
    return b


def invoice(b,issued=False,kind='invoice',due='2020-03-01',status='posted',identity='inv'):
    values=dict(kind=kind,reference=identity,date='2020-01-01',due_date=due,status=status,lines=[dict(code='MAT',quantity='1',unit_price='100',source_document=None,source_index=None)],tax_percent='10',retention_percent='5',document_id=identity)
    if issued:sales.set_document(b,customer_id='cust',**values)
    else:purchases.set_document(b,supplier_id='sup',**values)


def scheduled(b):
    invoice(b)
    schedules.set_schedule(b,'inv',[dict(id='a',date='2020-02-01',kind='normal',amount='40'),dict(id='b',date='2020-03-01',kind='normal',amount='65'),dict(id='g',date='2020-04-01',kind='guarantee',amount='5')])


class TreasuryTests(unittest.TestCase):
    def test_actual_flows_and_forecasts_are_separate_and_paid_amounts_are_not_repeated(self):
        b=budget();scheduled(b);invoice(b,issued=True,identity='sale')
        payments.record_payment(b,'sup','P1','2020-01-15',[dict(document_id='inv',amount='20')],payment_id='p')
        sales.record_receipt(b,'sale','2020-01-20','50')
        before=dumps(b);view=snapshot(b,'2020-01-31');rows={r[0]:r for r in month_rows(view)}
        self.assertEqual(rows['2020-01'][1:4],(Decimal(50),Decimal(20),Decimal(30)))
        self.assertEqual(rows['2020-02'][5],Decimal(20));self.assertEqual(rows['2020-03'][4:7],(Decimal(55),Decimal(65),Decimal(-10)))
        self.assertEqual(rows['2020-04'][5],Decimal(5))
        self.assertEqual(rows['Sin fecha'][4],Decimal(5))
        self.assertEqual(dumps(b),before);self.assertEqual(snapshot(loads(before),'2020-01-31'),view)
        self.assertTrue(all(len(row)==8 for row in detail_rows(view)))

    def test_opening_reduces_pending_without_becoming_a_cash_payment(self):
        b=budget();scheduled(b);schedules.set_opening(b,'inv','2020-01-10','30','Reviewed opening')
        view=snapshot(b,'2020-01-31');self.assertFalse(any(r['category']=='actual' for r in view['events']))
        regular=[r for r in view['events'] if r['detail'].startswith('Vencimiento')]
        self.assertEqual(sum(r['amount'] for r in regular),Decimal(75))
        prior=snapshot(b,'2020-01-05');self.assertTrue(any(r['amount'] is None for r in prior['events']))

    def test_unreviewed_pzh_opening_is_not_assumed_to_be_zero(self):
        b=_import(issued_fixture(),'synthetic.pzh').budget;sales.copy_source(b,1)
        rid=sales.state(b)['documents'][0]['id'];sales.set_status(b,rid,'posted')
        view=snapshot(b,'2020-01-31');self.assertTrue(any(r['category']=='review' and r['amount'] is None for r in view['events']))
        self.assertFalse(any(r['category']=='actual' for r in view['events']))
        sales.accept_opening(b,rid,'2020-01-31');view=snapshot(b,'2020-01-31')
        self.assertFalse(any(r['category']=='review' for r in view['events']))
        self.assertEqual(sum(r['amount'] for r in view['events']),Decimal(80))

    def test_cancelled_payment_follows_its_explicit_cancellation_date(self):
        b=budget();scheduled(b)
        payments.record_payment(b,'sup','P1','2020-01-15',[dict(document_id='inv',amount='20')],payment_id='p')
        payments.cancel_payment(b,'p','2020-01-25','Cancelled record')
        self.assertEqual(sum(r['amount'] for r in snapshot(b,'2020-01-20')['events'] if r['category']=='actual'),Decimal(20))
        self.assertFalse(any(r['category']=='actual' for r in snapshot(b,'2020-01-31')['events']))

    def test_proformas_are_explicit_optional_forecasts(self):
        b=budget();invoice(b,kind='proforma')
        self.assertEqual(snapshot(b,'2020-01-31')['events'],[])
        view=snapshot(b,'2020-01-31',True);self.assertEqual(sum(r['amount'] for r in view['events']),Decimal(110))
        self.assertFalse(any(r['category']=='actual' for r in view['events']))

    def test_real_payment_to_proforma_is_visible_even_when_forecast_is_disabled(self):
        b=budget();invoice(b,kind='proforma')
        payments.record_payment(b,'sup','P1','2020-01-15',[dict(document_id='inv',amount='20')])
        events=snapshot(b,'2020-01-31')['events']
        self.assertEqual(len(events),1);self.assertEqual(events[0]['category'],'actual');self.assertEqual(events[0]['amount'],Decimal(20))

    def test_changed_invoice_does_not_keep_an_unreconciled_source_calendar(self):
        b=_import(issued_fixture(),'synthetic.pzh').budget;sales.copy_source(b,1);doc=sales.state(b)['documents'][0]
        lines=[dict(doc['lines'][0],unit_price='200')]
        sales.set_document(b,kind=doc['kind'],reference=doc['reference'],customer_id=doc['customer_id'],date=doc['date'],lines=lines,tax_percent=doc['tax_percent'],retention_percent=doc['retention_percent'],document_id=doc['id'])
        sales.set_status(b,doc['id'],'posted');sales.accept_opening(b,doc['id'],'2020-01-31')
        events=snapshot(b,'2020-01-31')['events']
        self.assertTrue(any(r['category']=='review' and 'concilia' in r['detail'] for r in events))
        self.assertTrue(any(r[-1]>0 and r[-2]=='' for r in month_rows(snapshot(b,'2020-01-31'))))

    def test_missing_dates_are_preserved_as_unscheduled(self):
        b=budget();invoice(b,due=None)
        view=snapshot(b,'2020-01-31');self.assertTrue(all(r['date'] is None for r in view['events']))
        self.assertEqual(month_rows(view)[0][0],'Sin fecha');self.assertEqual(month_rows(view)[0][5],Decimal(110))

    def test_draft_and_future_documents_and_future_payments_are_not_actual_cash(self):
        b=budget();invoice(b,status='draft');self.assertEqual(snapshot(b,'2020-01-31')['events'],[])
        purchases.set_document_status(b,'inv','posted')
        payments.record_payment(b,'sup','P1','2020-02-15',[dict(document_id='inv',amount='20')])
        self.assertFalse(any(r['category']=='actual' for r in snapshot(b,'2020-01-31')['events']))
        self.assertEqual(snapshot(b,'2019-12-31')['events'],[])

    def test_overdue_flags_do_not_turn_forecasts_into_payments(self):
        b=budget();invoice(b,due='2020-01-15')
        events=snapshot(b,'2020-01-31')['events'];dated=[r for r in events if r['date']]
        self.assertTrue(all(r['overdue'] for r in dated));self.assertTrue(all(r['category']=='forecast' for r in events))

    def test_monthly_totals_do_not_depend_on_callers_decimal_precision(self):
        view={'events':[dict(date='2020-01-01',category='actual',direction='in',amount=Decimal('10000000000000.01')),dict(date='2020-01-02',category='actual',direction='in',amount=Decimal('.02'))]}
        with localcontext() as context:
            context.prec=6
            self.assertEqual(month_rows(view)[0][1],Decimal('10000000000000.03'))

    def test_invalid_cut_and_proforma_option_are_rejected(self):
        for day in ('2020-02-31','20200101',None):
            with self.assertRaises(BudgetError):snapshot(budget(),day)
        with self.assertRaises(BudgetError):snapshot(budget(),'2020-01-31',1)


if __name__=='__main__':unittest.main()
