"""Focused economic cases, independent of PZH and desktop dependencies."""
import json
import unittest
from decimal import Decimal as D
from openpresto.budget import Budget, BudgetConcept, BudgetRelation, BudgetError
from openpresto.commands import execute, ProjectSession
from openpresto.storage import dumps, loads
from openpresto import earned_value as evm
from openpresto.economic_indicators import indicators
from openpresto.reports import report_table, report_csv


def project():
    b=Budget()
    for code,nature in (('ROOT','capitulo'),('CH','capitulo'),('A','partida'),('B','partida')):
        b.add_concept(BudgetConcept(code=code,nature=nature,summary=code))
    b.set_root('ROOT');b.add_relation(BudgetRelation('ROOT','CH',id='root'))
    b.add_relation(BudgetRelation('CH','A',id='a'));b.add_relation(BudgetRelation('CH','B',id='b',position=2))
    b=execute(b,'planning.phases.configure',dict(end_dates=['2026-01-31','2026-02-28']))
    for rid,qty,price,half in (('a','10','60','5'),('b','20','20','10')):
        b=execute(b,'planning.phases.task.set',dict(relation_id=rid,objective_quantity=qty,objective_price=price,phases={'1':half,'2':half}))
    return b


def frozen():
    return execute(project(),'earned_value.baseline.freeze',dict(explanation='Base de prueba'))


class EarnedValueTests(unittest.TestCase):
    def test_reference_indicators(self):
        values=indicators('1000','500','400','500')
        expected=dict(CV='-100',SV='-100',CPI='.8',SPI='.8',EAC_CPI='1250',EAC_BASELINE='1100',EAC_COMPOSITE='1437.5',ETC_CPI='750',VAC_CPI='-250',TCPI_BAC='1.2')
        for key,value in expected.items():self.assertEqual(values[key],D(value),key)

    def test_weighted_project_and_no_carry_forward(self):
        b=frozen()
        for rid,qty,cost in (('a','4','100'),('b','8','400')):
            b=execute(b,'earned_value.progress.set',dict(phase=1,relation_id=rid,quantity=qty,actual_cost=cost))
        first,second=evm.curve_rows(b)
        self.assertEqual((first['BAC'],first['PV'],first['EV'],first['AC'],first['CPI']),(D(1000),D(500),D(400),D(500),D('.8')))
        self.assertEqual(second['PV'],D(1000));self.assertIsNone(second['EV']);self.assertIsNone(second['AC'])
        self.assertEqual(first['known_ev'],2)
        headers,rows=report_table(b,'valor_ganado');self.assertTrue(all(len(row)==len(headers) for row in rows));self.assertIn('EAC',report_csv(b,'valor_ganado'))

    def test_partial_data_unknown_independently(self):
        b=execute(frozen(),'earned_value.progress.set',dict(phase=1,relation_id='a',quantity='0',actual_cost='0'))
        row=evm.curve_rows(b)[0];self.assertIsNone(row['EV']);self.assertIsNone(row['AC']);self.assertEqual(row['known_ev'],1)
        b=execute(b,'earned_value.progress.set',dict(phase=1,relation_id='b',actual_cost='0'))
        row=evm.curve_rows(b)[0];self.assertEqual(row['AC'],0);self.assertIsNone(row['EV']);self.assertIsNone(row['CPI'])
        self.assertIsNone(indicators('1000','0','0','0')['SPI'])
        self.assertIsNone(indicators('1000','0','0','0')['EAC_CPI'])

    def test_baseline_is_frozen_and_duplicate_rejected(self):
        b=frozen();before=evm.curve_rows(b)
        b=execute(b,'planning.phases.task.set',dict(relation_id='a',objective_quantity='10',objective_price='999',phases={'1':'1','2':'9'}))
        self.assertEqual(evm.curve_rows(b),before)
        with self.assertRaises(BudgetError):execute(b,'earned_value.baseline.freeze')

    def test_invalid_progress_is_atomic(self):
        b=frozen();before=dumps(b)
        for params in (dict(phase=1,relation_id='a',quantity='11'),dict(phase=1,relation_id='a',quantity='NaN'),dict(phase=True,relation_id='a'),dict(phase=3,relation_id='a'),dict(phase=1,relation_id='a',actual_cost='-1')):
            with self.assertRaises(BudgetError):execute(b,'earned_value.progress.set',params)
            self.assertEqual(dumps(b),before)
        rows=[dict(relation_id='a',quantity='1',actual_cost='20',note='')]*2
        with self.assertRaises(BudgetError):execute(b,'earned_value.period.set',dict(phase=1,rows=rows))
        self.assertEqual(dumps(b),before)

    def test_incomplete_or_negative_baseline_rejected(self):
        b=execute(project(),'planning.phases.task.set',dict(relation_id='a',objective_quantity='10',objective_price='60',phases={'1':'5','2':'4'}))
        with self.assertRaises(BudgetError):execute(b,'earned_value.baseline.freeze')
        b=execute(project(),'planning.phases.task.set',dict(relation_id='a',objective_quantity='10',objective_price='60',phases={'1':'11','2':'-1'}))
        with self.assertRaises(BudgetError):execute(b,'earned_value.baseline.freeze')

    def test_period_replacement_roundtrip_and_history(self):
        session=ProjectSession(frozen());before=dumps(session.budget)
        rows=[dict(relation_id='a',quantity='4',actual_cost='100',note='Medido'),dict(relation_id='b',quantity='8',actual_cost='400',note='Revisado')]
        session.execute('earned_value.period.set',dict(phase=1,rows=rows))
        after=dumps(session.budget);self.assertEqual(json.loads(after)['version'],24)
        self.assertEqual(evm.state(loads(after)),evm.state(session.budget))
        session.undo();self.assertEqual(dumps(session.budget),before)
        session.redo();self.assertEqual(dumps(session.budget),after)
        session.execute('earned_value.period.set',dict(phase=1,rows=[]));self.assertIsNone(evm.curve_rows(session.budget)[0]['AC'])


if __name__=='__main__':unittest.main()
