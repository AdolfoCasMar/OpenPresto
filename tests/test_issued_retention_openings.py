"""Customer retention openings from our own synthetic binary fixture."""
import json
import unittest
from decimal import Decimal
from unittest.mock import patch
from openpresto import issued_management as sales,issued_retention_openings as r,management
from openpresto.pzh_importer import _import
from openpresto.pzh_archive import pzh_source_bytes
from openpresto.storage import dumps,loads,to_dict,StorageError
from openpresto.commands import ProjectSession
from openpresto.budget import BudgetError
from openpresto.treasury import snapshot
from test_retention_openings import fixture,imported as received


def imported(post=True):
    b=_import(fixture(issued=True),'own-issued-retentions.pzh',native_modules=True).budget
    identifier=sales.validate(b)['documents'][0]['id']
    if post:sales.set_status(b,identifier,'posted')
    return b,identifier


class IssuedRetentionTests(unittest.TestCase):
    def test_import_preserves_source_and_does_not_create_cash_or_purchases(self):
        b,rid=imported(False);data=r.validate(b)[rid]
        self.assertEqual(data['source']['guarantee'],'3.0');self.assertEqual(data['source']['fiscal'],'2.0');self.assertIsNone(data['opening'])
        self.assertEqual(to_dict(b)['version'],39);copy=loads(dumps(b));self.assertEqual(r.validate(copy),r.validate(b));self.assertEqual(pzh_source_bytes(copy),fixture(issued=True))
        self.assertEqual(sales.state(b)['receipts'],[]);self.assertEqual(management.state(b)['documents'],[]);self.assertEqual(management.ledger(b),[])
    def test_unreviewed_source_has_unknown_retention_forecast(self):
        b,rid=imported();sales.accept_opening(b,rid,'2020-01-10');view=snapshot(b,'2020-01-31')
        self.assertTrue(any(e['category']=='review' and 'retenciones' in e['detail'] for e in view['events']))
        self.assertFalse(any(e['category']=='actual' for e in view['events']));self.assertEqual(sum(e['amount'] for e in view['events'] if e['category']=='forecast'),75)
    def test_reviewed_kinds_reduce_forecast_without_historical_cash(self):
        b,rid=imported();sales.accept_opening(b,rid,'2020-01-10');r.set_opening(b,rid,'2020-01-10','3','1','One fiscal unit remains');view=snapshot(b,'2020-01-31')
        retained=[e for e in view['events'] if e['category']=='forecast' and 'Retención' in e['detail']]
        self.assertEqual([(e['amount'],e['detail']) for e in retained],[(Decimal(1),'Retención prevista · Fiscal')]);self.assertFalse(any(e['category']=='actual' for e in view['events']))
        sales.record_receipt(b,rid,'2020-02-01','75',receipt_id='new-receipt');view=snapshot(b,'2020-02-01')
        self.assertEqual(sum(e['amount'] for e in view['events'] if e['category']=='actual'),75);self.assertEqual(sum(e['amount'] for e in view['events'] if e['category']=='forecast'),1)
    def test_cut_before_review_does_not_invent_historical_receipts(self):
        b,rid=imported();r.set_opening(b,rid,'2020-01-10','3','2','Reviewed');view=snapshot(b,'2020-01-05')
        self.assertTrue(any(e['category']=='review' and 'retenciones' in e['detail'] for e in view['events']));self.assertFalse(any(e['category']=='actual' for e in view['events']))
    def test_retention_opening_covers_oldest_due_within_its_own_kind(self):
        b,rid=imported();data=sales.state(b);dues=data['source_states'][rid]['dues'];guarantee=next(d for d in dues if d['kind']==1);guarantee['amount']='2.0';guarantee['date']='2020-02-01';dues.append(dict(guarantee,amount='1.0',date='2020-01-15'));sales._save(b,data)
        sales.accept_opening(b,rid,'2020-01-10');r.set_opening(b,rid,'2020-01-10','1','0','Cover oldest guarantee only');view=snapshot(b,'2020-01-31')
        guarantees=[e for e in view['events'] if e['category']=='forecast' and 'Garantía' in e['detail']];fiscal=[e for e in view['events'] if e['category']=='forecast' and 'Fiscal' in e['detail']]
        self.assertEqual([(e['date'],e['amount']) for e in guarantees],[('2020-02-01',Decimal(2))]);self.assertEqual(sum(e['amount'] for e in fiscal),2)
    def test_invalid_openings_are_atomic(self):
        b,rid=imported();before=dumps(b)
        for day,g,f,note in (('2019-12-31','0','0','old'),('2020-01-10','4','0','over'),('2020-01-10','0','3','over'),('2020-01-10','0.001','0','precision'),('2020-01-10','-1','0','negative'),('2020-01-10','1','0','')):
            with self.subTest(case=(day,g,f)),self.assertRaises(BudgetError):r.set_opening(b,rid,day,g,f,note)
            self.assertEqual(dumps(b),before)
    def test_cancellation_and_invoice_edit_cannot_invalidate_opening(self):
        b,rid=imported(False);r.set_opening(b,rid,'2020-01-10','3','2','Reviewed');before=dumps(b);doc=sales.state(b)['documents'][0]
        with self.assertRaises(BudgetError):sales.set_status(b,rid,'cancelled')
        self.assertEqual(dumps(b),before)
        with self.assertRaises(BudgetError):sales.set_document(b,doc['kind'],doc['reference'],doc['customer_id'],doc['date'],doc['lines'],tax_percent='10',retention_percent='1',document_id=rid)
        self.assertEqual(dumps(b),before)
    def test_clear_undo_redo_and_recopy_preserve_native_review(self):
        b,rid=imported();session=ProjectSession(b);session.execute('issued.retention.opening.set',dict(document_id=rid,date='2020-01-10',guarantee='2.5',fiscal='1',note='Own review'))
        before=dumps(session.budget);sales.copy_source(session.budget,1);self.assertEqual(dumps(session.budget),before)
        session.execute('issued.retention.opening.clear',dict(document_id=rid));self.assertIsNone(r.opening_balances(session.budget)[rid]);session.undo();self.assertEqual(r.opening_balances(session.budget)[rid]['guarantee'],Decimal('2.5'));session.redo();self.assertIsNone(r.opening_balances(session.budget)[rid])
    def test_tampered_source_is_rejected_on_load(self):
        b,rid=imported();data=r.state(b);data[rid]['source']['guarantee']='999';b.project_metadata[r.KEY]=json.dumps(data)
        with self.assertRaises(StorageError):loads(json.dumps(to_dict_without_validation(b)))
    def test_customer_edit_isolated_from_received_retention_graph(self):
        b,rid=received();before=management.state(b);sales.set_customer(b,'Own customer',customer_id='customer');self.assertEqual(management.state(b),before)
        from openpresto.retention_openings import validate
        self.assertIn(rid,validate(b));self.assertEqual(sales.state(b)['customers'][0]['name'],'Own customer')
    def test_legacy_project_can_review_without_reimporting(self):
        b,rid=imported();b.project_metadata.pop(r.KEY);self.assertEqual(r.report_rows(b)[0][9],'Revisar apertura');r.set_opening(b,rid,'2020-01-10','3','2','Reviewed legacy import');self.assertEqual(to_dict(b)['version'],39);self.assertEqual(r.opening_balances(b)[rid]['fiscal'],2)
    def test_unreconciled_legacy_source_is_reported_without_blocking_the_panel(self):
        b,rid=imported(False);b.project_metadata.pop(r.KEY);data=sales.state(b);data['source_states'][rid]['dues'][-1]['amount']='99';b.project_metadata[sales.KEY]=json.dumps(data);before=dumps(b)
        self.assertEqual(r.report_rows(b)[0][9],'Revisar origen')
        with self.assertRaises(BudgetError):r.set_opening(b,rid,'2020-01-10','0','0','Cannot review a malformed schedule')
        self.assertEqual(dumps(b),before)


def to_dict_without_validation(budget):
    with patch('openpresto.storage._validate_extensions'):return to_dict(budget)


class IssuedRetentionPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])
    def test_real_issued_tab_dialog_and_undo(self):
        from PySide6.QtWidgets import QDialog,QLineEdit
        from openpresto.mdi_workspace import PrestoWorkspace
        from openpresto.issued_panel import IssuedPanel
        h=PrestoWorkspace()
        try:
            h.budget,rid=imported(False);h._reset_history();h._open_views();h.section_ui.ribbon.show_view('gestion:9');panel=h.findChild(IssuedPanel);self.assertIsNotNone(panel);retentions=panel.retention_openings;self.assertEqual(len(retentions.rows),1)
            def accept(dialog):
                self.assertEqual(dialog.findChild(QLineEdit,'retention-date').text(),'');dialog.findChild(QLineEdit,'retention-date').setText('2020-01-10');dialog.findChild(QLineEdit,'retention-guarantee').setText('2,5');dialog.findChild(QLineEdit,'retention-note').setText('Own review');return QDialog.DialogCode.Accepted
            with patch('openpresto.retention_openings_panel.QDialog.exec',new=accept):retentions.edit()
            self.assertEqual(r.opening_balances(h.budget)[rid]['guarantee'],Decimal('2.5'));self.assertEqual(len(h._undo),1);h.undo();self.assertIsNone(r.opening_balances(h.budget)[rid]);h.redo();self.assertEqual(r.opening_balances(h.budget)[rid]['guarantee'],Decimal('2.5'))
        finally:h.dirty=False;h.close()
