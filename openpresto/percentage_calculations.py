"""Explicit Presto 8.8 BC3 percentage view with cumulative preceding bases.

BC3 yield encodes the rate as a fraction; the displayed native quantity is
the matching preceding amounts divided by 100. No source values are rewritten.
This view is not the default calculator or an assertion of general BC3 parity.
"""
from decimal import Decimal
from dataclasses import replace

from .budget import BudgetError, special_price_kind, _decimal
from .calculations import BudgetCalculator, RelationAmount


class Presto88PercentageCalculator(BudgetCalculator):
    """Opt-in view for the observed prefix, order and cumulative-base contract."""

    def total(self):
        if self.budget.root_code is not None and special_price_kind(self.budget.root_code):
            raise BudgetError('Un precio especial no puede actuar como raíz de este perfil')
        return super().total()

    def _components(self, parent_code, visiting):
        children = sorted(
            (r for r in self.budget.relations if r.parent_code == parent_code),
            key=lambda r: r.position,
        )
        percentages = [r for r in children if special_price_kind(r.child_code) == 'porcentaje']
        if not percentages:
            raise BudgetError('La descomposición no contiene porcentajes')
        if len({r.position for r in children}) != len(children):
            raise BudgetError('El porcentaje requiere posiciones de relación inequívocas')
        if len({r.child_code.split('%', 1)[0] for r in percentages}) > 1:
            raise BudgetError('Combinación de distintos prefijos pendiente de contraste')
        for percentage in percentages:
            if percentage.child_code.startswith(('Ʃ', 'Σ', '∑')):
                raise BudgetError('Subtotal porcentual pendiente de contraste')
            if percentage.factor != 1:
                raise BudgetError('Factor de porcentaje pendiente de contraste')
            if any(r.parent_code == percentage.child_code for r in self.budget.relations):
                raise BudgetError('Porcentaje descompuesto pendiente de contraste')
            if (percentage.id in self.budget.bc3_measurements
                    or any(m.relation_id == percentage.id for m in self.budget.measurements)):
                raise BudgetError('Medición de porcentaje pendiente de contraste')
        rows = []
        for relation in children:
            if special_price_kind(relation.child_code) == 'porcentaje':
                prefix = relation.child_code.split('%', 1)[0]
                if relation.child_code.count('%') != 1:
                    raise BudgetError('Código con varios signos de porcentaje pendiente de contraste')
                if any(previous.child_code.casefold().startswith(prefix.casefold())
                       and not previous.child_code.startswith(prefix) for previous, _ in rows):
                    raise BudgetError('Coincidencia de prefijos con distinta caja pendiente de contraste')
                base = sum((row.amount for previous, row in rows
                            if previous.child_code.startswith(prefix)), Decimal('0'))
                quantity = self.policy.quantity(base / 100)
                price = self.policy.price(relation.quantity * 100)
            else:
                quantity = super().quantity(relation.id)
                price = self._price(relation.child_code, visiting)
            row = RelationAmount(relation.id, quantity, price,
                                 self.policy.amount(relation.factor * quantity * price))
            rows.append((relation, row))
        return rows

    def _price(self, code, visiting):
        if special_price_kind(code) == 'porcentaje':
            if any(r.parent_code == code for r in self.budget.relations):
                raise BudgetError('Porcentaje descompuesto pendiente de contraste')
            rates = {self.policy.price(r.quantity * 100) for r in self.budget.relations
                     if r.child_code == code}
            if len(rates) > 1:
                raise BudgetError('Un código porcentual con tipos distintos requiere conversión explícita')
            return next(iter(rates)) if rates else self.policy.price(self.budget.concepts[code].base_price)
        children = [r for r in self.budget.relations if r.parent_code == code]
        if not any(special_price_kind(r.child_code) == 'porcentaje' for r in children):
            return super()._price(code, visiting)
        if special_price_kind(code):
            raise BudgetError('Precio especial descompuesto pendiente de contraste')
        if code in visiting:
            raise BudgetError('Ciclo detectado durante el cálculo')
        visiting.add(code)
        try:
            return self.policy.price(sum((row.amount for _, row in
                                          self._components(code, visiting)), Decimal('0')))
        finally:
            visiting.remove(code)

    def relation(self, relation_id):
        relation = self.budget._relation(relation_id)
        if special_price_kind(relation.child_code) != 'porcentaje':
            return super().relation(relation_id)
        return next(row for source, row in self._components(
            relation.parent_code, {relation.parent_code}) if source.id == relation_id)

    def quantity(self, relation_id):
        relation = self.budget._relation(relation_id)
        if special_price_kind(relation.child_code) == 'porcentaje':
            return self.relation(relation_id).quantity
        return super().quantity(relation_id)


def validate_project_percentages(budget):
    """Validate all components, including disconnected decompositions."""
    calculator = Presto88PercentageCalculator(budget)
    for code in budget.concepts:
        calculator.price(code)
    for relation in budget.relations:
        calculator.relation(relation.id)
    if budget.root_code is not None:
        calculator.total()


def set_percentage_rate(budget, code, value):
    """Edit the shared type; BC3 continues storing its fractional yield."""
    native = budget.project_metadata.get('engine') == 'native-v1'
    if (not native and budget.percentage_profile != 'presto88_bc3') or special_price_kind(code) != 'porcentaje':
        raise BudgetError('No hay un perfil porcentual activo para este concepto')
    rate = _decimal(value, 'Tipo porcentual')
    if not native and (rate < 0 or rate != rate.quantize(Decimal('.01'))):
        raise BudgetError('El tipo contrastado admite valores positivos o cero, con dos decimales')
    updated = [replace(r, quantity=rate / 100) if r.child_code == code else r
               for r in budget.relations]
    budget.relations = updated
    budget._relations_by_id = {r.id: r for r in updated}
    budget.concepts[code] = replace(budget.concepts[code], base_price=rate)
