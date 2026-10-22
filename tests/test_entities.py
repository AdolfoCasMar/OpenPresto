"""Native entities preserve provenance and remain separate from financial parties."""
import copy
import json
import unittest
from openpresto.budget import Budget,BudgetError
from openpresto import entities,management,issued_management
from openpresto.commands import ProjectSession
from openpresto.pzh_importer import _import
from openpresto.pzh_operations import state as source_state
from openpresto.pzh_archive import pzh_source_bytes
from openpresto.storage import dumps,loads,to_dict,StorageError
from openpresto.reports import report_table
from test_pzh_control import control_fixture


class EntitiesTests(unittest.TestCase):
    def test_copy_includes_unreferenced_entity_and_professional_properties(self):
        raw=control_fixture();b=_import(raw,'synthetic.pzh',native_modules=True).budget
        rows=entities.validate(b);self.assertEqual(len(rows),1);row=rows[0]
        self.assertEqual((row['title'],row['college'],row['registration']),('Title','College','Registration'))
        self.assertEqual(row['source_fields']['32'],'1250.5')
        self.assertEqual(row['source_fields'],source_state(b)['entities'][0]['fields'])
        self.assertEqual(management.state(b)['suppliers'],[])
        self.assertEqual(issued_management.state(b)['customers'],[])
        self.assertEqual(to_dict(b)['version'],28)
        self.assertEqual(entities.validate(loads(dumps(b))),rows);self.assertEqual(pzh_source_bytes(b),raw)

    def test_edit_and_repeat_copy_preserve_source_and_native_changes(self):
        raw=control_fixture();b=_import(raw,'synthetic.pzh').budget;entities.copy_pzh(b)
        old=copy.deepcopy(entities.validate(b)[0]);source=source_state(b)
        entities.set_entity(b,{'name':'Reviewed contact','email':'person@example.invalid','role':13},old['id'])
        before=dumps(b);entities.copy_pzh(b);self.assertEqual(dumps(b),before)
        self.assertEqual(entities.validate(b)[0]['source_fields'],old['source_fields'])
        self.assertEqual(source_state(b),source);self.assertEqual(pzh_source_bytes(b),raw)

    def test_bad_native_edit_is_atomic(self):
        b=Budget();entities.set_entity(b,{'code':'E1','name':'Example'})
        rid=entities.validate(b)[0]['id'];before=dumps(b)
        for values in ({'code':''},{'role':True},{'role':256},{'source_fields':{}},{'email':None}):
            with self.subTest(values=values):
                with self.assertRaises(BudgetError):entities.set_entity(b,values,rid)
                self.assertEqual(dumps(b),before)
        with self.assertRaises(BudgetError):entities.set_entity(b,{'name':'missing'},'absent')

    def test_source_properties_cannot_be_changed_through_commands(self):
        b=Budget();session=ProjectSession(b);before=dumps(session.budget)
        with self.assertRaises(BudgetError):session.execute('entities.set',dict(values={'code':'E1','source_id':1}))
        self.assertEqual(dumps(session.budget),before)

    def test_native_command_history_and_report(self):
        session=ProjectSession(Budget());session.execute('entities.set',dict(values={'code':'E1','name':'Party','tax_id':'Example'}))
        rows=entities.validate(session.budget);self.assertEqual(len(rows),1)
        headers,report=report_table(session.budget,'entidades');self.assertEqual(len(headers),len(report[0]));self.assertIn('Party',report[0])
        session.undo();self.assertEqual(entities.validate(session.budget),[])
        session.redo();self.assertEqual(entities.validate(session.budget),rows)

    def test_invalid_persisted_entity_is_rejected(self):
        b=Budget();entities.set_entity(b,{'code':'E1'})
        document=to_dict(b)
        def corrupt(value):
            if isinstance(value,dict):
                for key,item in value.items():
                    if key==entities.KEY:
                        rows=json.loads(item);rows[0]['role']=True;value[key]=json.dumps(rows);return True
                    if corrupt(item):return True
            elif isinstance(value,list):
                for item in value:
                    if corrupt(item):return True
            return False
        self.assertTrue(corrupt(document))
        with self.assertRaises(StorageError):loads(json.dumps(document))

    def test_search_matches_contact_properties_and_keeps_roles_explicit(self):
        b=Budget();entities.set_entity(b,{'code':'E1','name':'Laboratorio','email':'CONTACT@example.invalid','city':'Salamanca','role':17})
        entities.set_entity(b,{'code':'E2','name':'Otra entidad','role':0})
        self.assertEqual(len(entities.find(b,'contact@',17)),1)
        self.assertEqual(len(entities.find(b,'salamanca')),1)
        self.assertEqual(entities.find(b,'salamanca',0),[])
        with self.assertRaises(BudgetError):entities.find(b,role=True)

    def test_source_copy_requires_an_archived_source(self):
        with self.assertRaises(BudgetError):entities.copy_pzh(Budget())


if __name__=='__main__':unittest.main()
