"""Inspect BC3 ~M measurement lines without changing the imported Budget.

Preserves six-field rows and applies the tested 2002 line rounding profile.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from pathlib import Path


class MeasurementParseError(ValueError):
    """Invalid measurement record or unsupported safe formula."""


@dataclass(frozen=True)
class BC3MeasurementLine:
    kind: str
    description: str
    a: str
    b: str
    c: str
    d: str
    partial: Decimal | None
    warning: str = ""
    applied_formula: str = ""


@dataclass(frozen=True)
class BC3MeasurementRecord:
    reference: str
    phase: str
    declared_quantity: Decimal | None
    lines: tuple[BC3MeasurementLine, ...]
    calculated_quantity: Decimal | None
    warnings: tuple[str, ...]
    raw_body: str
    zero_dimensions_as_blank: bool = False
    native_formulas: bool = False


def _decimal(text: str, default: Decimal = Decimal('1')) -> Decimal:
    if not text.strip():
        return default
    try:
        value = Decimal(text.strip())
    except InvalidOperation as exc:
        raise MeasurementParseError(f"Número no válido: {text!r}") from exc
    if not value.is_finite():
        raise MeasurementParseError("Número no finito")
    return value


def _compute(node: ast.AST, variables: dict[str, Decimal], source: str, *, extended=False) -> Decimal:
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return _decimal(ast.get_source_segment(source, node) or str(node.value))
    if isinstance(node, ast.Name) and node.id.lower() in variables:
        return variables[node.id.lower()]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        number = _compute(node.operand, variables, source, extended=extended)
        return number if isinstance(node.op, ast.UAdd) else -number
    if isinstance(node, ast.BinOp):
        left = _compute(node.left, variables, source, extended=extended)
        right = _compute(node.right, variables, source, extended=extended)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if extended and isinstance(node.op,ast.Pow):
            if abs(right) > 64:
                raise MeasurementParseError('Exponente fuera del límite admitido (64)')
            return left ** right
        if isinstance(node.op, ast.Div):
            if right == 0:
                raise MeasurementParseError("División entre cero")
            return left / right
    raise MeasurementParseError("Operación de fórmula no admitida")


def evaluate_formula(expression: str, a: str = '', b: str = '',
                     c: str = '', d: str = '', *, extended=False) -> Decimal:
    """Arithmetic-only expression using variables a,b,c,d; never eval()."""
    if len(expression) > 256:
        raise MeasurementParseError("Fórmula demasiado larga")
    vars_ = dict(zip('abcd', (_decimal(a), _decimal(b), _decimal(c), _decimal(d))))
    if extended:
        vars_['p'] = Decimal('3.1415926')
    try:
        expression = expression.strip().replace('^','**') if extended else expression.strip()
        tree = ast.parse(expression, mode='eval')
    except (SyntaxError,RecursionError) as exc:
        raise MeasurementParseError("Sintaxis de fórmula no válida") from exc
    if len(list(ast.walk(tree))) > 100:
        raise MeasurementParseError("Fórmula demasiado compleja")
    try:
        if extended:
            with localcontext() as context:
                context.prec=40
                context.Emax=1000
                context.Emin=-1000
                value = _compute(tree.body,vars_,expression,extended=True)
        else:
            value = _compute(tree.body, vars_, expression)
    except (ArithmeticError, RecursionError) as exc:
        raise MeasurementParseError("Error al calcular fórmula") from exc
    if not value.is_finite():
        raise MeasurementParseError("Resultado no finito")
    return value


def parse_measurement(body: str, *, zero_dimensions_as_blank: bool = False, native_formulas: bool = False) -> BC3MeasurementRecord:
    """Parse ~M using per-line HALF_UP, partial and accumulated subtotals."""
    fields = body.rstrip('\r\n').split('|')
    if len(fields) < 4:
        raise MeasurementParseError("Registro ~M incompleto")
    reference, phase, declared_text, raw_lines = fields[:4]
    declared = _decimal(declared_text) if declared_text.strip() else None
    if raw_lines:
        tokens = raw_lines.split('\\')
        if tokens[-1] != '':
            raise MeasurementParseError("Falta separador final en ~M")
        tokens.pop()  # final delimiter only; other blank slots are meaningful
    else:
        tokens = []
    if len(tokens) % 6:
        raise MeasurementParseError("Número incorrecto de campos en las líneas ~M")
    lines = []
    warnings = []
    total = Decimal('0')
    subtotal = Decimal('0')
    valid_total = True
    valid_subtotal = True
    active_formula = None
    for i in range(0, len(tokens), 6):
        kind, description, a, b, c, d = tokens[i:i+6]
        warning = ''
        applied_formula = ''
        part = None
        try:
            if kind == '' and native_formulas and active_formula and any(v.strip() for v in (a,b,c,d)):
                applied_formula = active_formula
                part = evaluate_formula(active_formula,a,b,c,d,extended=True)
            elif kind == '':
                dimensions = [(_decimal(v) if not zero_dimensions_as_blank or not v.strip()
                               or _decimal(v) != 0 else Decimal('1')) for v in (b, c, d)]
                part = (_decimal(a) * dimensions[0] * dimensions[1] * dimensions[2]
                        if any(v.strip() for v in (a, b, c, d)) else Decimal('0'))
            elif kind == '3':
                part = evaluate_formula(description,a,b,c,d,extended=native_formulas)
                if native_formulas:
                    applied_formula = description
                    expression_tree = ast.parse(description.strip().replace('^','**'),mode='eval')
                    active_formula = description if any(isinstance(node,ast.Name) and node.id.lower() in ('a','b','c','d') for node in ast.walk(expression_tree)) else None
            elif kind == '1':
                part = subtotal if valid_subtotal else None
            elif kind == '2':
                part = total if valid_total else None
            else:
                raise MeasurementParseError(f"Tipo de medición no admitido: {kind!r}")
            if part is not None:
                part = part.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except (MeasurementParseError, ArithmeticError) as exc:
            warning = str(exc)
            valid_total = valid_subtotal = False
        if warning:
            warnings.append(f"Línea {i//6+1}: {warning}")
        if part is not None and kind in ('', '3'):
            total += part
            subtotal += part
        if kind in ('1', '2'):
            subtotal = Decimal('0')
            valid_subtotal = True
        lines.append(BC3MeasurementLine(kind, description, a, b, c, d, part, warning, applied_formula))
    return BC3MeasurementRecord(reference, phase, declared, tuple(lines),
                                total if valid_total else None,
                                tuple(warnings), body, zero_dimensions_as_blank, native_formulas)


def rebuild_record(record, lines):
    """Recalculate edited six-field rows, retaining reference and position."""
    tokens = []
    for row in lines:
        values = (row.kind, row.description, row.a, row.b, row.c, row.d)
        if any(any(c in v for c in ('|', '~', '\\', '\n', '\r')) for v in values):
            raise MeasurementParseError("Separadores BC3 no permitidos en una celda")
        tokens.extend(values)
    raw = '\\'.join(tokens) + ('\\' if tokens else '')
    result = parse_measurement('|'.join((record.reference, record.phase, '', raw)),
                               zero_dimensions_as_blank=record.zero_dimensions_as_blank,
                               native_formulas=record.native_formulas)
    if result.warnings:
        raise MeasurementParseError('; '.join(result.warnings))
    return result



def inspect_import(result) -> tuple[BC3MeasurementRecord, ...]:
    """Inspect original ~M records preserved by ImportResult.raw_records."""
    return tuple(parse_measurement(body, zero_dimensions_as_blank=result.budget.bc3_zero_dimensions_as_blank)
                 for kind, body in result.raw_records
                 if kind == 'M')
