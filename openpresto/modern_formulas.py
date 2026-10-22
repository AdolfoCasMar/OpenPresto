"""Independent measurement formulas documented in the recent manual, p.63.

This is a native measurement evaluator, not the BC3 2002 expression profile.
It never executes Python expressions. Section tables and field transfers are
not substituted with guessed constants.
"""
import ast
from decimal import Decimal, localcontext, DecimalException

from .budget import BudgetError, _decimal


class ModernFormulaError(BudgetError):
    pass


PI = Decimal('3.14159265359')  # Manual's P constant, kept distinct from trig pi.
TRIG_PI = Decimal('3.1415926535897932384626433832795028841971693993751')


def _trig(angle):
    angle = angle.remainder_near(Decimal(360))
    cardinal = {Decimal(0): (Decimal(0), Decimal(1)), Decimal(90): (Decimal(1), Decimal(0)),
                Decimal(-90): (Decimal(-1), Decimal(0)), Decimal(180): (Decimal(0), Decimal(-1)),
                Decimal(-180): (Decimal(0), Decimal(-1))}
    if angle in cardinal:
        return cardinal[angle]
    x = angle * TRIG_PI / 180
    sine = sine_term = x
    cosine = cosine_term = Decimal(1)
    for i in range(1, 100):
        sine_term *= -x*x / ((2*i)*(2*i+1))
        cosine_term *= -x*x / ((2*i-1)*(2*i))
        sine += sine_term
        cosine += cosine_term
        if max(abs(sine_term), abs(cosine_term)) < Decimal('1e-42'):
            return sine, cosine
    raise ModernFormulaError('No converge la función trigonométrica')


def _compute(node, variables, source):
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return _decimal(ast.get_source_segment(source, node), 'constante')
    if isinstance(node, ast.Name):
        key = node.id.lower()
        if key in variables:
            return variables[key]
        if key == 'p':
            return PI
        raise ModernFormulaError('Variable de fórmula no admitida')
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _compute(node.operand, variables, source)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp):
        left = _compute(node.left, variables, source)
        right = _compute(node.right, variables, source)
        if isinstance(node.op, ast.Add): return left + right
        if isinstance(node.op, ast.Sub): return left - right
        if isinstance(node.op, ast.Mult): return left * right
        if isinstance(node.op, ast.Div):
            if right == 0: raise ModernFormulaError('División entre cero')
            return left / right
        if isinstance(node.op, ast.Pow):
            if abs(right) > 64: raise ModernFormulaError('Exponente fuera del límite admitido (64)')
            return left ** right
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and len(node.args) == 1 and not node.keywords:
        name = node.func.id.upper()
        if name not in ('ABS', 'SQRT', 'SIN', 'COS', 'TAN'):
            raise ModernFormulaError('Función no implementada; no se sustituyen perfiles por constantes')
        value = _compute(node.args[0], variables, source)
        if name == 'ABS': return abs(value)
        if name == 'SQRT': return value.sqrt()
        sine, cosine = _trig(value)
        if name == 'SIN': return sine
        if name == 'COS': return cosine
        if cosine == 0: raise ModernFormulaError('Tangente no definida para este ángulo')
        return sine / cosine
    raise ModernFormulaError('Operación de fórmula no admitida')


def evaluate_modern_formula(expression, n=1, length=None, width=None, height=None):
    """Evaluate formula, then multiply dimensions not explicitly referenced.

    Function names and A/B/C/D/P are case insensitive. Trig angles use degrees.
    Precision is 40 decimal digits; RedParc and dimension annulment are separate
    contracts, not silently imposed on legacy native measurements here.
    """
    if not isinstance(expression, str) or not expression.strip() or len(expression) > 256:
        raise ModernFormulaError('Fórmula vacía o demasiado larga')
    source = expression.strip().replace('^', '**')
    try:
        tree = ast.parse(source, mode='eval')
    except (SyntaxError, RecursionError) as exc:
        raise ModernFormulaError('Sintaxis de fórmula no válida') from exc
    nodes = list(ast.walk(tree))
    if len(nodes) > 100:
        raise ModernFormulaError('Fórmula demasiado compleja')
    variables = dict(zip('abcd', (_decimal(1 if value is None else value, 'dimensión')
                                  for value in (n, length, width, height))))
    used = {node.id.lower() for node in nodes if isinstance(node, ast.Name) and node.id.lower() in variables}
    try:
        with localcontext() as context:
            context.prec = 40
            context.Emax = 1000
            context.Emin = -1000
            result = _compute(tree.body, variables, source)
            for key, value in variables.items():
                if key not in used:
                    result *= value
            if not result.is_finite():
                raise ModernFormulaError('Resultado no finito')
            return +result
    except (DecimalException, RecursionError, ValueError) as exc:
        if isinstance(exc, ModernFormulaError): raise
        raise ModernFormulaError('Error numérico en la fórmula') from exc
