import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from openpresto.history_snapshots import capture_snapshot, restore_snapshot, Snapshot
from openpresto.storage import dumps, loads, load_budget, save_budget, StorageError
from openpresto.commands import ProjectSession
from openpresto.pzh_importer import _import
from openpresto.pzh_archive import pzh_source_bytes
from test_production import project
from test_technical_documents import fixture


class HistorySnapshotTests(unittest.TestCase):
    def test_large_strings_are_shared_but_mutable_graph_is_independent(self):
        budget = project()
        text = 'Private original text. ' * 10000
        budget.project_metadata['large-original'] = text
        snapshot = capture_snapshot(budget)
        clone = restore_snapshot(snapshot)
        self.assertIs(clone.project_metadata['large-original'], text)
        self.assertLess(len(snapshot.payload), len(dumps(budget)) // 10)
        clone.project_metadata['new'] = 'independent'
        from openpresto.budget_editing import edit_concept
        edit_concept(clone, 'A', {'summary':'Independent'})
        self.assertNotIn('new', budget.project_metadata)
        self.assertNotEqual(clone.concepts['A'].summary, budget.concepts['A'].summary)
        self.assertEqual(dumps(restore_snapshot(snapshot)), dumps(budget))
        self.assertNotIn('Private', repr(snapshot))

    def test_command_undo_redo_retains_original_and_shares_unchanged_text(self):
        budget = project()
        text = 'Immutable text ' * 10000
        budget.project_metadata['large-original'] = text
        session = ProjectSession(budget)
        for title in ('First', 'Second'):
            session.execute('budget.concept.edit', {'code':'A', 'changes':{'summary':title}})
            self.assertIs(session.budget.project_metadata['large-original'], text)
        self.assertTrue(all(isinstance(s, Snapshot) for s in session._undo))
        self.assertTrue(all(any(value is text for _, value in s.bindings) for s in session._undo))
        session.undo(); self.assertEqual(session.budget.concepts['A'].summary, 'First')
        session.redo(); self.assertEqual(session.budget.concepts['A'].summary, 'Second')
        before = len(session._undo)
        session.execute('budget.concept.edit', {'code':'A', 'changes':{'summary':'Second'}})
        self.assertEqual(len(session._undo), before)

    def test_changed_large_string_does_not_modify_prior_frame(self):
        budget = project(); budget.project_metadata['large'] = 'a' * 20000
        old = capture_snapshot(budget)
        budget.project_metadata['large'] = 'b' * 20000
        new = capture_snapshot(budget)
        self.assertNotEqual(old, new)
        self.assertEqual(restore_snapshot(old).project_metadata['large'], 'a' * 20000)
        self.assertEqual(restore_snapshot(new).project_metadata['large'], 'b' * 20000)
        self.assertEqual(restore_snapshot(dumps(budget)).project_metadata['large'], 'b' * 20000)

    def test_pzh_original_survives_internal_snapshot_and_portable_file(self):
        raw = fixture(); budget = _import(raw, 'own.pzh').budget
        restored = restore_snapshot(capture_snapshot(budget))
        self.assertEqual(pzh_source_bytes(restored), raw)
        self.assertEqual(pzh_source_bytes(loads(dumps(restored))), raw)

    def test_native_files_above_old_limit_and_bounded_failure(self):
        budget = project()
        budget.project_metadata['large-original'] = 'x' * (26 * 1024 * 1024)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'large.json'
            save_budget(budget, path)
            self.assertEqual(load_budget(path).project_metadata['large-original'], budget.project_metadata['large-original'])
            with patch('openpresto.storage.MAX_FILE_BYTES', 1024):
                with self.assertRaises(StorageError):
                    load_budget(path)
                with self.assertRaises(StorageError):
                    save_budget(budget, path)
            self.assertEqual(load_budget(path).concepts['A'].summary, 'Wall')

    def test_hierarchy_and_measurement_operations_share_immutable_source(self):
        from openpresto.budget import BudgetMeasurement
        from openpresto.measurement_operations import move_native_line,remove_lines
        from openpresto.hierarchy_services import duplicate_concept,remove_unused_concepts
        b=project();text='Preserved original ' * 10000;b.project_metadata['large-original']=text
        b.add_measurement(BudgetMeasurement('A',n_lines='1',id='m1'));b.add_measurement(BudgetMeasurement('A',n_lines='2',id='m2'))
        moved=move_native_line(b,'m1',1);self.assertIs(moved.project_metadata['large-original'],text);self.assertEqual([m.id for m in b.measurements],['m1','m2'])
        removed=remove_lines(moved,[('native','m1')]);self.assertIs(removed.project_metadata['large-original'],text);self.assertEqual(len(moved.measurements),2)
        copied=duplicate_concept(b,'A','COPY');self.assertIs(copied.project_metadata['large-original'],text);self.assertNotIn('COPY',b.concepts)
        cleaned=remove_unused_concepts(copied,['COPY']);self.assertIs(cleaned.project_metadata['large-original'],text);self.assertIn('COPY',copied.concepts)


class DesktopHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setOrganizationName('OpenPrestoTests')
        cls.app.setApplicationName('SharedHistory')

    def test_save_revision_and_rebased_history_remain_portable(self):
        from openpresto.mdi_workspace import PrestoWorkspace
        host = PrestoWorkspace()
        try:
            host.budget = project()
            host.budget.project_metadata['large'] = 'source ' * 10000
            host._reset_history()
            host._execute('budget.concept.edit', code='A', changes={'summary':'Edited'})
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'project.json'
                host.path = path
                self.assertTrue(host.save())
                self.assertIsInstance(host._snapshot, Snapshot)
                self.assertEqual(host._file_revision[1], hashlib.sha256(path.read_bytes()).hexdigest())
                self.assertEqual(load_budget(path).concepts['A'].summary, 'Edited')
                host.undo(); self.assertEqual(host.budget.concepts['A'].summary, 'Wall')
                host.redo(); self.assertEqual(host.budget.concepts['A'].summary, 'Edited')
                target = Path(folder) / 'copy.json'
                with patch('openpresto.editor.QFileDialog.getSaveFileName', return_value=(str(target), '')):
                    self.assertTrue(host.save_as())
                host.undo(); self.assertEqual(host.budget.concepts['A'].summary, 'Wall')
                self.assertEqual(load_budget(target).project_metadata['large'], 'source ' * 10000)
        finally:
            host.dirty = False
            host.close()
