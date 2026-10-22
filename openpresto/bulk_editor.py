"""Edición masiva explícita de conceptos seleccionados."""
from dataclasses import replace
from decimal import Decimal
from PySide6.QtWidgets import QInputDialog
from .budget import BudgetError, _decimal


def edit_selection(host):
    rows = sorted({index.row() for index in host.prices.selectedIndexes() if not host.prices.isRowHidden(index.row())})
    codes = {host._visible_relations[row].child_code for row in rows if row < len(host._visible_relations)}
    if not codes:
        host._error('Selecciona filas en Precios')
        return
    fields = {'Unidad': 'unit', 'Resumen': 'summary', 'Naturaleza': 'nature', 'Precio básico': 'base_price'}
    label, ok = QInputDialog.getItem(host, 'Editar selección', 'Campo para todos los conceptos seleccionados:', list(fields), 0, False)
    if not ok:
        return
    value, ok = QInputDialog.getText(host, 'Editar selección', 'Nuevo valor (aplica a todas las apariciones):')
    if not ok:
        return
    field = fields[label]
    host._execute('budget.concepts.edit', codes=sorted(codes), field=field,
        value=value.replace(',', '.') if field == 'base_price' else value)
