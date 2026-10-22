import struct,json,unittest
from openpresto import budget_phase_measurements as phases
from openpresto.pzh_importer import _Reader,_import,HEADER_BYTES
from openpresto.pzh_archive import pzh_source_bytes
from openpresto.pzh_native_modules import results
from openpresto.commands import ProjectSession
from openpresto.storage import dumps,loads,to_dict,StorageError
from openpresto.budget import BudgetError
from test_budget_phase_measurements import fixture as phase_fixture


def fixture():
    raw=phase_fixture();reader=_Reader(raw);out=bytearray(raw[:HEADER_BYTES+4+len(reader.config)])
    for table in range(24):
        count,start,end=reader.tables[table];payload=raw[start:end]
        if table==4:
            rows=[]
            for offset,rid,body in reader.records(4,12):
                if rid==1:body=body[:14]+b'MISSING'.ljust(13,b' ')+body[27:]
                order=struct.unpack_from('<I',raw,offset+8)[0];rows.append(struct.pack('<III',len(body),rid,order)+body)
            payload=b''.join(rows)
        begin=len(out);out+=payload;struct.pack_into('<III',out,34+table*88,count,begin,len(out))
    return bytes(out)


class PhaseLinkReviewTests(unittest.TestCase):
    def imported(self):return _import(fixture(),'own-unbound-phase.pzh',native_modules=True).budget
    def test_unbound_line_has_editable_native_copy_and_explicit_pending_result(self):
        b=self.imported();data=phases.state(b);self.assertEqual(len(data['lines']),2);self.assertIsNone(data['lines'][1]['relation_id']);self.assertEqual(data['lines'][1]['source_relation']['child'],'MISSING');self.assertNotIn('MISSING',b.concepts);self.assertEqual(to_dict(b)['version'],46);self.assertEqual(pzh_source_bytes(loads(dumps(b))),fixture());self.assertEqual(next(r for r in results(b) if r['module']=='Mediciones presupuestarias')['status'],'pending')
    def test_unbound_preview_and_application_are_blocked_without_changes(self):
        b=self.imported();before=dumps(b)
        for action in (phases.preview,phases.apply_through):
            with self.assertRaisesRegex(BudgetError,'Vincula'):action(b,2)
            self.assertEqual(dumps(b),before)
        phases.edit_line(b,'1',{'comment':'Own review','n_lines':'3'});self.assertEqual(phases.state(b)['lines'][1]['comment'],'Own review')
    def test_explicit_mapping_apply_and_undo_keep_original_relation_identity(self):
        s=ProjectSession(self.imported());before=s.budget.total();rid=next(r.id for r in s.budget.relations if r.parent_code=='ROOT' and r.child_code=='ITEM');s.execute('budget.phases.line.edit',dict(line_id='1',changes={'n_lines':'3'}));s.execute('budget.phases.line.link',dict(line_id='1',relation_id=rid));self.assertEqual(s.budget.total(),before);self.assertEqual(phases.state(s.budget)['lines'][1]['source_relation']['child'],'MISSING');s.execute('budget.phases.apply',dict(phase=2));self.assertGreater(s.budget.total(),before);s.undo();self.assertEqual(s.budget.total(),before);s.undo();self.assertIsNone(phases.state(s.budget)['lines'][1]['relation_id']);self.assertEqual(pzh_source_bytes(s.budget),fixture())
    def test_missing_target_and_applied_state_tamper_rejected(self):
        b=self.imported();before=dumps(b)
        with self.assertRaises(BudgetError):phases.link_line(b,'1','missing-target')
        self.assertEqual(dumps(b),before);data=phases.state(b);data['active_through']=2;b.project_metadata[phases.KEY]=json.dumps(data)
        with self.assertRaises(StorageError):dumps(b)


class PhaseLinkPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([]);cls.app.setOrganizationName('OpenPrestoTests');cls.app.setApplicationName('PhaseLinkReview')
    def test_no_default_guess_and_explicit_link_is_undoable(self):
        from openpresto.mdi_workspace import PrestoWorkspace
        from unittest.mock import patch
        from PySide6.QtWidgets import QDialog,QComboBox
        h=PrestoWorkspace()
        try:
            h.budget=_import(fixture(),'own.pzh',native_modules=True).budget;h._reset_history();h._open_views();h.section_ui.ribbon.show_view('gestion:budget_phase_measurements');panel=h.panels['gestion'][1].budget_phase_measurements;i=next(i for i,row in enumerate(panel.rows) if row[0]=='1');panel.table.setCurrentCell(i,0);before=dumps(h.budget)
            with patch('openpresto.budget_phase_measurements_panel.QDialog.exec',return_value=QDialog.DialogCode.Accepted),patch.object(h,'_error') as error:panel.link();error.assert_called_once()
            self.assertEqual(json.loads(dumps(h.budget)),json.loads(before));self.assertEqual(len(h._undo),0)
            rid=next(r.id for r in h.budget.relations if r.parent_code=='ROOT' and r.child_code=='ITEM')
            def accept(dialog):
                target=dialog.findChild(QComboBox,'phase-link-target');self.assertIsNone(target.currentData());target.setCurrentIndex(target.findData(rid));return QDialog.DialogCode.Accepted
            with patch('openpresto.budget_phase_measurements_panel.QDialog.exec',new=accept):panel.link()
            self.assertEqual(phases.state(h.budget)['lines'][1]['relation_id'],rid);self.assertEqual(len(h._undo),1);h.undo();self.assertIsNone(phases.state(h.budget)['lines'][1]['relation_id'])
        finally:h.dirty=False;h.close()
