"""Regression coverage for operation-scoped reuse; no timing thresholds."""
import unittest
from dataclasses import replace
from decimal import Decimal
from unittest.mock import patch
from openpresto.budget import Budget, BudgetConcept, BudgetRelation, BudgetError
from openpresto.calculations import BudgetCalculator
from openpresto import management, inventory_control
from test_procurement_tracking import chain


class OptimizationTests(unittest.TestCase):
    def test_inventory_evaluates_ledger_once_and_keeps_current_results(self):
        b = chain()
        for read in (lambda: inventory_control.snapshot(b, '2020-01-31'),
                     lambda: inventory_control.period(b, '2020-01-01', '2020-01-31')):
            expected = read()
            with patch.object(management, 'ledger', wraps=management.ledger) as ledger:
                self.assertEqual(read(), expected)
                self.assertEqual(ledger.call_count, 1)
        management.consume(b, 'MAT', '2020-01-05', '2', 'Site')
        self.assertEqual(inventory_control.snapshot(b, '2020-01-31')['rows'][0][5], 6)

    def test_resource_index_is_rebuilt_after_structure_changes(self):
        b = chain()
        management.validate(b)
        b.concepts['NEW'] = BudgetConcept('NEW')
        b.relations.append(BudgetRelation('MAT', 'NEW', '1', 1, id='new'))
        with self.assertRaises(BudgetError):management.validate(b)
        b.relations.pop()
        management.validate(b)

    def test_batch_matches_uncached_prices_and_observes_later_edits(self):
        b = Budget('R')
        b.concepts = {c.code:c for c in (BudgetConcept('R'), BudgetConcept('A'), BudgetConcept('B'), BudgetConcept('M', base_price='1.234'))}
        for i,(parent,child) in enumerate((('R','A'),('R','B'),('A','M'),('B','M'))):
            b.add_relation(BudgetRelation(parent, child, '2.345', i+1, id=str(i)))
        calc = BudgetCalculator(b)
        expected = [calc.relation(r.id) for r in b.relations]
        with calc.batch():
            with calc.batch():self.assertEqual([calc.relation(r.id) for r in b.relations], expected)
            self.assertEqual([calc.relation(r.id) for r in b.relations], expected)
        b.concepts['M'] = replace(b.concepts['M'], base_price=Decimal('9'))
        with calc.batch():self.assertEqual(calc.total(), BudgetCalculator(b).total())
        self.assertNotEqual(calc.relation('2'), expected[2])

    def test_batch_cycles_still_fail_and_cleanup_after_exception(self):
        b = Budget('R');b.concepts = {'R':BudgetConcept('R')}
        b.relations = [BudgetRelation('R','R','1',1,id='cycle')]
        calc = BudgetCalculator(b)
        with self.assertRaises(BudgetError):
            with calc.batch():calc.total()
        b.relations.clear()
        with calc.batch():self.assertEqual(calc.total(), 0)

    def test_render_formatter_preserves_text_and_decimal_precision(self):
        from openpresto.number_format import formatter
        value=Decimal('1234.5600')
        self.assertEqual(formatter(',')(value),'1234,5600')
        self.assertEqual(formatter('.')(value),'1234.5600')
        self.assertEqual(formatter(',')('A.B'),'A.B')


if __name__ == '__main__':unittest.main()
