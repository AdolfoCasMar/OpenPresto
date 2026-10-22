import json,unittest
from decimal import Decimal
from openpresto import agenda,planning,concept_keywords,project_assets,pzh_assets,management,issued_management
from openpresto.pzh_importer import _import
from openpresto.pzh_archive import pzh_source_bytes
from openpresto.storage import dumps,loads,to_dict,StorageError
from openpresto.commands import ProjectSession
from openpresto.budget import BudgetError
from pzh_auxiliary_cases import fixture


def imported():return _import(fixture(),'own-auxiliary.pzh',native_modules=True).budget


class AuxiliaryModuleTests(unittest.TestCase):
    def test_search_terms_are_native_and_never_new_concept_ids(self):
        b=imported();data=concept_keywords.validate(b);self.assertEqual(data['ITEM']['terms'],['hiddenword','secondword']);self.assertEqual(data['ITEM']['source']['records'],3);self.assertNotIn('hiddenword',b.concepts);self.assertEqual(pzh_source_bytes(b),fixture())
    def test_keyword_edit_undo_and_repeat_import_preserve_edits(self):
        s=ProjectSession(imported());original=s.budget.total();s.execute('concept.keywords.set',dict(code='ITEM',terms=['own edited term']));before=dumps(s.budget);concept_keywords.copy_source(s.budget);self.assertEqual(dumps(s.budget),before);self.assertEqual(s.budget.total(),original);s.undo();self.assertEqual(concept_keywords.validate(s.budget)['ITEM']['terms'],['hiddenword','secondword']);s.redo();self.assertEqual(concept_keywords.validate(s.budget)['ITEM']['terms'],['own edited term'])
    def test_keyword_duplicates_and_unknown_codes_rejected_atomically(self):
        b=imported();before=dumps(b)
        for code,words in (('ITEM',['word','WORD']),('ITEM',['']),('missing',['word'])):
            with self.assertRaises(BudgetError):concept_keywords.set_terms(b,code,words)
            self.assertEqual(dumps(b),before)
    def test_duplicate_and_remove_concept_keep_keyword_links_consistent(self):
        from openpresto.hierarchy_services import duplicate_concept,remove_unused_concepts,remove_relations
        b=imported();copy=duplicate_concept(b,'ITEM','OWN-COPY');self.assertEqual(concept_keywords.validate(copy)['OWN-COPY']['terms'],['hiddenword','secondword']);self.assertIsNone(concept_keywords.validate(copy)['OWN-COPY']['source']);copy=remove_relations(copy,[r.id for r in copy.relations if r.parent_code=='OWN-COPY']);removed=remove_unused_concepts(copy,['OWN-COPY']);self.assertNotIn('OWN-COPY',concept_keywords.validate(removed));self.assertIn('ITEM',concept_keywords.validate(removed))
    def test_indexed_notes_images_and_drawings_remain_lazy_and_recoverable(self):
        b=imported();rows=project_assets.validate(b);self.assertEqual({r['source']['table'] for r in rows},{3,12,20,21,22});self.assertTrue(all(r['text'] is None for r in rows));self.assertEqual(pzh_assets.read(b,12,'14620')['text'],'Own uncompressed note');self.assertEqual(pzh_assets.read(b,21,'ITEM')['format'],'bmp');drawing=pzh_assets.read(b,22,'ITEM');self.assertEqual(drawing['format'],'wmf');self.assertEqual(drawing['payload'][:8],b'WRAPTEST');self.assertEqual(drawing['export'],drawing['payload'][8:])
    def test_attachment_edit_keeps_original_and_copies_do_not_overwrite(self):
        s=ProjectSession(imported());rid=next(r['id'] for r in project_assets.validate(s.budget) if r['source']['table']==3);raw=project_assets.read(s.budget,rid)['original']['payload'];s.execute('assets.set',dict(asset_id=rid,title='Own title',note='Reviewed',text='Own native text'));before=dumps(s.budget);project_assets.copy_source(s.budget);self.assertEqual(dumps(s.budget),before);self.assertEqual(project_assets.read(s.budget,rid)['original']['payload'],raw);self.assertEqual(project_assets.read(s.budget,rid)['text'],'Own native text');s.undo();self.assertEqual(project_assets.read(s.budget,rid)['text'],'Own specification');s.redo();self.assertEqual(project_assets.read(s.budget,rid)['text'],'Own native text')
    def test_binary_attachment_does_not_accept_invented_text_conversion(self):
        b=imported();rid=next(r['id'] for r in project_assets.validate(b) if r['source']['table']==21);before=dumps(b)
        with self.assertRaises(BudgetError):project_assets.set_asset(b,rid,'Image','','Not a text document')
        self.assertEqual(dumps(b),before)
    def test_agenda_dates_holidays_and_cached_amounts_are_separate(self):
        b=imported();rows=agenda.validate(b);self.assertEqual(rows[0]['date'],'2020-01-06');self.assertIs(rows[0]['holiday'],True);self.assertEqual(rows[0]['note'],'Own holiday');self.assertEqual(Decimal(agenda.source_total_rows(b)[0][2]),250);self.assertEqual(planning.state(b)['holidays'],[]);self.assertEqual(management.ledger(b),[]);self.assertEqual(issued_management.state(b)['receipts'],[])
    def test_reviewed_holiday_addition_is_explicit_and_undoable(self):
        s=ProjectSession(imported())
        planning.configure_calendar(s.budget,[0,1,2,3,4],['2020-01-01']);s=ProjectSession(s.budget);s.execute('agenda.holidays.add',{});self.assertEqual(planning.state(s.budget)['holidays'],['2020-01-01','2020-01-06']);s.undo();self.assertEqual(planning.state(s.budget)['holidays'],['2020-01-01']);s.redo();self.assertEqual(planning.state(s.budget)['holidays'],['2020-01-01','2020-01-06'])
    def test_agenda_edit_does_not_fabricate_cash_or_rewrite_source_figures(self):
        b=imported();old=agenda.source_total_rows(b);agenda.set_day(b,'2020-01-06',False,'Own edited note');agenda.copy_source(b);self.assertIs(agenda.validate(b)[0]['holiday'],False);self.assertEqual(agenda.source_total_rows(b),old);self.assertEqual(management.ledger(b),[])
    def test_holiday_that_would_invalidate_an_activity_is_rolled_back(self):
        b=imported();rid=b.relations[0].id;planning.set_task(b,rid,'2020-01-06','2020-01-06','1');before=dumps(b)
        with self.assertRaises(BudgetError):agenda.add_holidays_to_plan(b)
        self.assertEqual(dumps(b),before)
    def test_native_roundtrip_preserves_source_and_metadata(self):
        b=imported();self.assertEqual(to_dict(b)['version'],44);copy=loads(dumps(b));self.assertEqual(project_assets.validate(copy),project_assets.validate(b));self.assertEqual(agenda.validate(copy),agenda.validate(b));self.assertEqual(concept_keywords.validate(copy),concept_keywords.validate(b));self.assertEqual(pzh_source_bytes(copy),fixture())
    def test_attachment_index_tamper_rejected(self):
        b=imported();rows=project_assets.validate(b);rows[0]['source']['offset']+=1;b.project_metadata[project_assets.KEY]=json.dumps(rows)
        with self.assertRaises(StorageError):dumps(b)
    def test_wmf_extraction_keeps_outer_bytes_and_rejects_broken_records(self):
        b=imported();raw=pzh_assets.read(b,22,'ITEM')['payload'];self.assertEqual(pzh_assets._wmf_stream(raw+b'padding'),raw[8:]);broken=bytearray(raw);broken[26:30]=b'\0'*4;self.assertIsNone(pzh_assets._wmf_stream(bytes(broken)))
    def test_cached_index_cannot_be_mutated_or_hide_corrupted_source(self):
        b=imported();rows=pzh_assets.catalogue(b);rows[0]['code']='tampered';self.assertNotEqual(pzh_assets.catalogue(b)[0]['code'],'tampered');original=b.project_metadata['pzh_source_archive_v1'];archive=json.loads(original);archive['data']='AAAA';b.project_metadata['pzh_source_archive_v1']=json.dumps(archive)
        with self.assertRaises(BudgetError):pzh_assets.catalogue(b)
        b.project_metadata['pzh_source_archive_v1']=original;self.assertNotEqual(pzh_assets.catalogue(b)[0]['code'],'tampered')
