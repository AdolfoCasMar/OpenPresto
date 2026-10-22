import struct,unittest,json
from decimal import Decimal
from datetime import date
from openpresto.pzh_importer import _import,_Reader,HEADER_BYTES
from openpresto.pzh_archive import pzh_source_bytes
from openpresto.pzh_native_modules import results
from openpresto import management as m,management_schedule as schedules,management_advanced as payments,retention_openings as r
from openpresto.treasury import snapshot
from openpresto.storage import dumps,loads,to_dict,StorageError
from openpresto.commands import ProjectSession
from openpresto.budget import BudgetError
from test_pzh_issued import issued_fixture


def fixture(*,issued=False):
    raw=issued_fixture(issued=issued);reader=_Reader(raw)
    def code(s):return s.encode().ljust(13,b' ')
    def f(tag,fmt,v):return bytes([tag])+struct.pack('<'+fmt,v)
    serial=(date(2020,1,1)-date(1979,12,31)).days
    payload=b''
    for identifier,kind,paid,amount in ((1,0,True,30),(2,0,False,75),(3,1,True,3),(4,2,True,2)):
        body=struct.pack('<H',serial+identifier)+code('INV')+code('CLIENT')+f(1,'B',kind)+f(2,'B',int(paid))+f(4,'d',amount);payload+=struct.pack('<II',len(body),identifier)+bytes(8)+body
    boundary=HEADER_BYTES+4+struct.unpack_from('<I',raw,HEADER_BYTES)[0];out=bytearray(raw[:boundary])
    for t in range(24):
        count,start,end=reader.tables[t];part=payload if t==15 else raw[start:end];count=4 if t==15 else count;begin=len(out);out+=part;struct.pack_into('<III',out,0x22+t*88,count,begin,len(out))
    return bytes(out)


def imported(post=True):
    b=_import(fixture(),'own-paid-retentions.pzh',native_modules=True).budget;doc=m.validate(b)['documents'][0];identifier=doc['id']
    if post:m.set_document_status(b,identifier,'posted')
    return b,identifier


class RetentionOpeningTests(unittest.TestCase):
    def test_pzh_paid_retentions_become_reviewable_without_dates_or_cash(self):
        b,identifier=imported(False);data=r.validate(b)[identifier];self.assertIsNone(data['opening']);self.assertEqual(Decimal(data['source']['guarantee']),3);self.assertEqual(Decimal(data['source']['fiscal']),2);self.assertEqual(payments.state(b)['payments'],[]);self.assertEqual(m.ledger(b),[]);self.assertEqual(to_dict(b)['version'],38);self.assertEqual(pzh_source_bytes(loads(dumps(b))),fixture());self.assertFalse(any(row['status']=='pending' for row in results(b)))
    def test_unreviewed_retentions_are_unknown_not_full_unpaid_forecasts(self):
        b,identifier=imported();schedules.set_opening(b,identifier,'2020-01-10','30','Review normal balance');view=snapshot(b,'2020-01-31');self.assertTrue(any(e['category']=='review' and 'retenciones' in e['detail'] for e in view['events']));self.assertFalse(any(e['category']=='actual' for e in view['events']));self.assertFalse(any(e['category']=='forecast' and 'Retención' in e['detail'] for e in view['events']));self.assertTrue(any('retenciones' in row[2] and row[3]=='' for row in schedules.forecast_rows(b)))
    def test_reviewed_opening_reduces_both_retention_kinds_without_cash(self):
        b,identifier=imported();schedules.set_opening(b,identifier,'2020-01-10','30','Review normal balance');r.set_opening(b,identifier,'2020-01-10','3','1','One fiscal unit remains');view=snapshot(b,'2020-01-31');retained=[e for e in view['events'] if e['category']=='forecast' and 'Retención' in e['detail']];self.assertEqual(sum(e['amount'] for e in retained),1);self.assertTrue(all('Fiscal' in e['detail'] for e in retained));self.assertFalse(any(e['category']=='actual' for e in view['events']));self.assertEqual(sum(row[3] for row in schedules.forecast_rows(b)),76);self.assertEqual(payments.state(b)['payments'],[])
    def test_cut_before_opening_is_not_reconstructed(self):
        b,identifier=imported();r.set_opening(b,identifier,'2020-01-10','3','2','Reviewed');view=snapshot(b,'2020-01-05');self.assertTrue(any(e['category']=='review' and 'retenciones' in e['detail'] for e in view['events']));self.assertFalse(any(e['category']=='actual' for e in view['events']))
    def test_invalid_date_amount_precision_and_missing_note_are_atomic(self):
        b,identifier=imported();before=dumps(b)
        for day,guarantee,fiscal,note in (('2019-12-31','0','0','bad date'),('2020-01-10','4','0','too much'),('2020-01-10','0','3','too much'),('2020-01-10','0.001','0','precision'),('2020-01-10','-1','0','negative'),('2020-01-10','1','0','')):
            with self.subTest(case=(day,guarantee,fiscal)),self.assertRaises(BudgetError):r.set_opening(b,identifier,day,guarantee,fiscal,note)
            self.assertEqual(dumps(b),before)
    def test_clear_and_undo_redo_preserve_source_and_financial_isolation(self):
        b,identifier=imported();total=b.total();session=ProjectSession(b);session.execute('management.retention.opening.set',dict(document_id=identifier,date='2020-01-10',guarantee='3',fiscal='2',note='Reviewed'));source=r.validate(session.budget)[identifier]['source'];session.execute('management.retention.opening.clear',dict(document_id=identifier));self.assertIsNone(r.validate(session.budget)[identifier]['opening']);self.assertEqual(r.validate(session.budget)[identifier]['source'],source);session.undo();self.assertEqual(r.opening_balances(session.budget)[identifier]['fiscal'],2);session.redo();self.assertIsNone(r.opening_balances(session.budget)[identifier]);self.assertEqual(session.budget.total(),total);self.assertEqual(payments.state(session.budget)['payments'],[])
    def test_tampered_native_module_is_rejected_on_load(self):
        b,identifier=imported();data=to_dict(b)
        def corrupt(node):
            if isinstance(node,dict):
                if 'metadata' in node and r.KEY in node['metadata']:
                    state=json.loads(node['metadata'][r.KEY]);state[identifier]['source']['guarantee']='999';node['metadata'][r.KEY]=json.dumps(state);return True
                return any(corrupt(v) for v in node.values())
            return False
        self.assertTrue(corrupt(data))
        with self.assertRaises(StorageError):loads(json.dumps(data))

    def test_native_invoice_without_source_has_reviewable_opening(self):
        from test_treasury import budget,scheduled
        b=budget();scheduled(b);self.assertNotIn(r.KEY,b.project_metadata);old_version=to_dict(b)['version'];r.set_opening(b,'inv','2020-01-10','2.50','0','Own opening');self.assertIsNone(r.validate(b)['inv']['source']);self.assertEqual(to_dict(b)['version'],38);self.assertNotEqual(old_version,38);self.assertFalse(any(e['category']=='actual' for e in snapshot(b,'2020-01-31')['events']))
    def test_changing_schedule_cannot_leave_retention_opening_overallocated(self):
        from test_treasury import budget,scheduled
        b=budget();scheduled(b);r.set_opening(b,'inv','2020-01-10','2.5','0','Reviewed');before=dumps(b);dues=schedules.state(b)['inv']['dues'];dues[-1]['kind']='fiscal'
        with self.assertRaises(BudgetError):schedules.set_schedule(b,'inv',dues)
        self.assertEqual(dumps(b),before)
    def test_cancellation_with_positive_opening_is_rejected_atomically(self):
        b,identifier=imported();r.set_opening(b,identifier,'2020-01-10','3','2','Reviewed');before=dumps(b)
        with self.assertRaises(BudgetError):m.set_document_status(b,identifier,'cancelled')
        self.assertEqual(dumps(b),before)
    def test_recopy_does_not_overwrite_review(self):
        from openpresto.pzh_native_management import copy_dues
        b,identifier=imported();r.set_opening(b,identifier,'2020-01-10','1','0','Own review');before=dumps(b);copy_dues(b,1);self.assertEqual(dumps(b),before)


class RetentionOpeningPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([]);cls.app.setOrganizationName('OpenPrestoTests');cls.app.setApplicationName('RetentionOpeningPanel')
    def setUp(self):
        from openpresto.mdi_workspace import PrestoWorkspace
        self.h=PrestoWorkspace();self.h.budget,self.identifier=imported(False);self.h._reset_history();self.h._open_views();self.h.section_ui.ribbon.show_view('gestion:retention_openings');self.panel=self.h.panels['gestion'][1].retention_openings
    def tearDown(self):self.h.dirty=False;self.h.close()
    def test_named_route_dialog_decimal_comma_and_undo_redo(self):
        from PySide6.QtWidgets import QDialog,QLineEdit
        from unittest.mock import patch
        h=self.h;self.assertIs(h.panels['gestion'][1].tabs.currentWidget(),self.panel);self.assertEqual(len(self.panel.rows),1)
        def accept(dialog):
            self.assertEqual(dialog.findChild(QLineEdit,'retention-date').text(),'');dialog.findChild(QLineEdit,'retention-date').setText('2020-01-10');dialog.findChild(QLineEdit,'retention-guarantee').setText('2,5');dialog.findChild(QLineEdit,'retention-note').setText('Own review');return QDialog.DialogCode.Accepted
        with patch('openpresto.retention_openings_panel.QDialog.exec',new=accept):self.panel.edit()
        self.assertEqual(r.opening_balances(h.budget)[self.identifier]['guarantee'],Decimal('2.5'));self.assertEqual(len(h._undo),1);h.undo();self.assertIsNone(r.opening_balances(h.budget)[self.identifier]);h.redo();self.assertEqual(r.opening_balances(h.budget)[self.identifier]['guarantee'],Decimal('2.5'))
    def test_cancel_and_invalid_missing_date_keep_project_unchanged(self):
        from PySide6.QtWidgets import QDialog
        from unittest.mock import patch
        h=self.h;before=dumps(h.budget)
        with patch('openpresto.retention_openings_panel.QDialog.exec',return_value=QDialog.DialogCode.Rejected):self.panel.edit()
        self.assertEqual(dumps(h.budget),before)
        with patch('openpresto.retention_openings_panel.QDialog.exec',return_value=QDialog.DialogCode.Accepted),patch.object(h,'_error') as error:self.panel.edit();error.assert_called_once()
        self.assertEqual(json.loads(dumps(h.budget)),json.loads(before));self.assertEqual(len(h._undo),0)
