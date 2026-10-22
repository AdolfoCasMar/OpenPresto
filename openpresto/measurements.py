"""Consultas y resúmenes de mediciones de OpenPresto.

Las líneas y su cálculo básico viven en budget.py. Este módulo ofrece
desgloses y subtotales sin duplicar el modelo ni modificar el presupuesto.
No interpreta fórmulas, fases ni reglas especiales de Presto 8.8.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .budget import Budget, BudgetError, BudgetMeasurement


@dataclass(frozen=True)
class MeasurementEntry:
    """Resultado de una línea de medición, con su signo original."""

    id: str
    comment: str
    partial: Decimal


@dataclass(frozen=True)
class MeasurementSummary:
    """Desglose de una relación; cantidad efectiva sin redondeo."""

    relation_id: str
    entries: tuple[MeasurementEntry, ...]
    positives: Decimal
    deductions: Decimal
    quantity: Decimal
    uses_measurements: bool

    @property
    def zero_lines(self) -> int:
        return sum(entry.partial == 0 for entry in self.entries)


def line_partial(line: BudgetMeasurement) -> Decimal:
    """N × longitud × anchura × altura; None equivale a 1, cero a 0."""
    if not isinstance(line, BudgetMeasurement):
        raise TypeError("Se esperaba un BudgetMeasurement")
    return line.partial()


def summarize_relation(budget: Budget, relation_id: str) -> MeasurementSummary:
    """Resume una relación por su identificador, sin alterar sus datos.

    Si existen líneas, sustituyen a la cantidad manual, incluso cuando
    su suma sea cero. Las deducciones se expresan con signo negativo.
    """
    if not isinstance(budget, Budget):
        raise TypeError("Se esperaba un Budget")
    relation = budget._relation(relation_id)
    lines = tuple(
        MeasurementEntry(m.id, m.comment, budget.measurement_partial(m))
        for m in budget.measurements
        if m.relation_id == relation_id
    )
    if relation_id in budget.bc3_measurements:
        record = budget.bc3_measurements[relation_id]
        lines = tuple(MeasurementEntry(f"{relation_id}:{index}", row.description, row.partial)
                      for index, row in enumerate(record.lines)
                      if row.kind in ('', '3') and row.partial is not None)
    positives = sum((entry.partial for entry in lines if entry.partial > 0),
                    Decimal("0"))
    deductions = sum((entry.partial for entry in lines if entry.partial < 0),
                     Decimal("0"))
    uses_measurements = bool(lines) or bool(budget.bc3_measurements.get(relation_id) and budget.bc3_measurements[relation_id].lines)
    quantity = budget.relation_quantity(relation_id)
    return MeasurementSummary(
        relation_id=relation_id,
        entries=lines,
        positives=positives,
        deductions=deductions,
        quantity=quantity,
        uses_measurements=uses_measurements,
    )


def summarize_budget(budget: Budget) -> tuple[MeasurementSummary, ...]:
    """Resume cada relación una sola vez, en el orden del presupuesto.

    No suma las relaciones entre sí: hacerlo daría cantidades con
    unidades distintas y duplicaría niveles de la descomposición.
    """
    if not isinstance(budget, Budget):
        raise TypeError("Se esperaba un Budget")
    return tuple(summarize_relation(budget, relation.id)
                 for relation in budget.relations)
