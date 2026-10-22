"""Modelo independiente de presupuestos jerárquicos de OpenPresto.

Los importes se calculan con Decimal, sin redondeos implícitos. La política
específica de redondeo de obra se incorporará en el módulo de cálculos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from uuid import uuid4


class BudgetError(ValueError):
    """Operación inválida sobre un presupuesto."""


def special_price_kind(code: str) -> str | None:
    """Recognize documented special price codes; never value them as resources."""
    if '%' in code:
        return 'porcentaje'
    if code.startswith(('Ʃ', 'Σ', '∑')):
        return 'subtotal'
    return None


def require_plain_price_code(code: str) -> None:
    kind = special_price_kind(code)
    if kind:
        raise BudgetError(f'El concepto {code} requiere cálculo de {kind} aún no implementado; no se calcula como un componente ordinario.')


def _decimal(value: Decimal | int | str, name: str) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise BudgetError(f"{name} debe ser Decimal, int o str (no float/bool)")
    try:
        result = Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise BudgetError(f"{name} no es un número válido") from exc
    if not result.is_finite():
        raise BudgetError(f"{name} debe ser finito")
    return result


@dataclass(frozen=True)
class BudgetConcept:
    code: str
    unit: str = ""
    summary: str = ""
    nature: str = ""
    base_price: Decimal = Decimal("0")
    text: str = ""
    measurement_decimals: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.code,str) or not self.code.strip() or '\x00' in self.code:
            raise BudgetError("El código del concepto debe ser texto no vacío sin bytes nulos")
        if any(not isinstance(getattr(self,name),str) for name in ('unit','summary','nature','text')):
            raise BudgetError("Unidad, resumen, naturaleza y texto deben ser cadenas")
        object.__setattr__(self, "base_price", _decimal(self.base_price, "base_price"))
        if self.measurement_decimals is not None and (type(self.measurement_decimals) is not int
                or not 0 <= self.measurement_decimals <= 12):
            raise BudgetError('La precisión de medición debe ser un entero de 0 a 12 o None')


@dataclass(frozen=True)
class BudgetRelation:
    parent_code: str
    child_code: str
    quantity: Decimal = Decimal("1")
    position: int = 1
    id: str = field(default_factory=lambda: uuid4().hex)

    factor: Decimal = Decimal('1')

    def __post_init__(self) -> None:
        if any(not isinstance(value,str) or not value.strip() for value in (self.parent_code,self.child_code,self.id)):
            raise BudgetError('Códigos e identificador de relación deben ser texto no vacío')
        object.__setattr__(self, "quantity", _decimal(self.quantity, "quantity"))
        object.__setattr__(self, "factor", _decimal(self.factor, "factor"))
        if not isinstance(self.position, int) or isinstance(self.position, bool) or self.position < 1:
            raise BudgetError("La posición debe ser un entero positivo")
        if not self.id:
            raise BudgetError("El identificador de relación no puede estar vacío")


@dataclass(frozen=True)
class BudgetMeasurement:
    relation_id: str
    comment: str = ""
    n_lines: Decimal = Decimal("1")
    length: Decimal | None = None
    width: Decimal | None = None
    height: Decimal | None = None
    id: str = field(default_factory=lambda: uuid4().hex)
    formula: str = ''
    annulled_dimensions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.relation_id,str) or not self.relation_id:
            raise BudgetError("La medición necesita un identificador de relación textual")
        if not isinstance(self.id,str) or not self.id or not isinstance(self.comment,str):
            raise BudgetError('Identificador y comentario de medición deben ser texto')
        if self.n_lines is None:
            raise BudgetError('El número de unidades de medición no puede ser nulo')
        for name in ("n_lines", "length", "width", "height"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _decimal(value, name))
        if not self.id:
            raise BudgetError("El identificador de medición no puede estar vacío")
        if not isinstance(self.formula, str):
            raise BudgetError('La fórmula debe ser texto')
        allowed = ('n_lines', 'length', 'width', 'height')
        if (not isinstance(self.annulled_dimensions, tuple)
                or any(name not in allowed for name in self.annulled_dimensions)
                or len(set(self.annulled_dimensions)) != len(self.annulled_dimensions)):
            raise BudgetError('Dimensiones anuladas no válidas')
        if self.formula.strip():
            self.partial()

    def partial(self, decimals: int | None = None) -> Decimal:
        if decimals is not None and (type(decimals) is not int or not 0 <= decimals <= 12):
            raise BudgetError('Precisión de medición no válida')
        if self.formula.strip():
            from .modern_formulas import evaluate_modern_formula
            values = []
            for name in ('n_lines', 'length', 'width', 'height'):
                value = getattr(self, name)
                if name in self.annulled_dimensions:
                    value = Decimal('1')
                elif value is not None and name != 'n_lines' and decimals is not None:
                    value = value.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
                values.append(value)
            result = evaluate_modern_formula(self.formula, *values)
            return result if decimals is None else result.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
        result = Decimal('1')
        for name in ('n_lines', 'length', 'width', 'height'):
            dimension = getattr(self, name)
            if name not in self.annulled_dimensions:
                if dimension is not None and name != 'n_lines' and decimals is not None:
                    dimension = dimension.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
                result *= Decimal("1") if dimension is None else dimension
        return result if decimals is None else result.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)


class Budget:
    """Presupuesto acíclico con una raíz explícita.

    Las mediciones sustituyen la cantidad manual de una relación si hay líneas
    asociadas. Si no las hay, se utiliza ``relation.quantity``.
    """

    def __init__(self, root_code: str | None = None) -> None:
        self.project_metadata = {}
        self.documents = []
        self.bc3_measurements = {}
        self.source_records = ()
        self.import_warnings = ()
        self.root_quantity_decimals = None
        self.bc3_zero_dimensions_as_blank = False
        self.certified_quantities = {}
        self.certification_schedule = None
        self.phase_certified_quantities = {}
        self.percentage_profile = None
        self.indirect_config = None
        self.locked_prices = {}
        self.root_code = root_code
        self.concepts: dict[str, BudgetConcept] = {}
        self.relations: list[BudgetRelation] = []
        self.measurements: list[BudgetMeasurement] = []
        self._relations_by_id: dict[str, BudgetRelation] = {}
        self._measurements_by_id: set[str] = set()

    def add_concept(self, concept: BudgetConcept) -> None:
        if concept.code in self.concepts:
            raise BudgetError(f"Código duplicado: {concept.code}")
        self.concepts[concept.code] = concept

    def set_root(self, code: str) -> None:
        if code not in self.concepts:
            raise BudgetError(f"No existe el concepto raíz: {code}")
        self.root_code = code

    def add_relation(self, relation: BudgetRelation) -> None:
        if relation.id in self._relations_by_id:
            raise BudgetError(f"Identificador de relación duplicado: {relation.id}")
        if relation.parent_code not in self.concepts or relation.child_code not in self.concepts:
            raise BudgetError("Los conceptos superior e inferior deben existir")
        if relation.parent_code == relation.child_code:
            raise BudgetError("Un concepto no puede descomponerse en sí mismo")
        if any(r.parent_code == relation.parent_code and r.position == relation.position
               for r in self.relations):
            raise BudgetError("Posición repetida dentro de la descomposición")
        # Un nuevo arco padre->hijo forma ciclo si el hijo ya alcanza al padre.
        pending = [relation.child_code]
        visited: set[str] = set()
        while pending:
            code = pending.pop()
            if code == relation.parent_code:
                raise BudgetError("La relación introduciría un ciclo")
            if code in visited:
                continue
            visited.add(code)
            pending.extend(r.child_code for r in self.relations if r.parent_code == code)
        self.relations.append(relation)
        self._relations_by_id[relation.id] = relation

    def add_measurement(self, measurement: BudgetMeasurement) -> None:
        if measurement.relation_id not in self._relations_by_id:
            raise BudgetError(f"Relación desconocida: {measurement.relation_id}")
        if measurement.relation_id in self.bc3_measurements:
            raise BudgetError("Edita las líneas BC3 de esta relación; no mezcles motores de medición")
        if measurement.id in self._measurements_by_id:
            raise BudgetError(f"Identificador de medición duplicado: {measurement.id}")
        self.measurement_partial(measurement)
        self.measurements.append(measurement)
        self._measurements_by_id.add(measurement.id)

    def measurement_partial(self, measurement: BudgetMeasurement) -> Decimal:
        if self.project_metadata.get('measurement_kind:' + measurement.id) in ('1', '2'):
            return Decimal('0')
        relation = self._relation(measurement.relation_id)
        return measurement.partial(self.concepts[relation.child_code].measurement_decimals)

    def has_certification(self, relation_id: str) -> bool:
        return relation_id in self.certified_quantities or any(
            relation_id in rows for rows in self.phase_certified_quantities.values())

    def relation_quantity(self, relation_id: str) -> Decimal:
        if (self.percentage_profile is not None or self.project_metadata.get('engine') == 'native-v1') and '%' in self._relation(relation_id).child_code:
            from .calculations import calculator_for
            return calculator_for(self).quantity(relation_id)
        relation = self._relation(relation_id)
        if relation_id in self.bc3_measurements:
            record = self.bc3_measurements[relation_id]
            if record.calculated_quantity is None:
                raise BudgetError("Medición BC3 sin cálculo válido")
            if record.lines:
                return record.calculated_quantity
        rows = [m for m in self.measurements if m.relation_id == relation_id]
        return sum((self.measurement_partial(m) for m in rows), Decimal("0")) if rows else relation.quantity

    def concept_price(self, code: str) -> Decimal:
        if (self.percentage_profile is not None or self.indirect_config is not None or self.locked_prices
                or any(key in self.project_metadata for key in
                       ('quantity_decimals','price_decimals','amount_decimals','economic_rounding','engine'))):
            from .calculations import calculator_for
            return calculator_for(self).price(code)
        if code not in self.concepts:
            raise BudgetError(f"Concepto desconocido: {code}")
        return self._concept_price(code, set())

    def _concept_price(self, code: str, visiting: set[str]) -> Decimal:
        require_plain_price_code(code)
        if code in visiting:
            raise BudgetError("Ciclo encontrado durante el cálculo")
        children = [r for r in self.relations if r.parent_code == code]
        if not children:
            return self.concepts[code].base_price
        visiting.add(code)
        try:
            return sum((r.factor * self.relation_quantity(r.id) * self._concept_price(r.child_code, visiting)
                        for r in children), Decimal("0"))
        finally:
            visiting.remove(code)

    def relation_amount(self, relation_id: str) -> Decimal:
        if (self.percentage_profile is not None or self.indirect_config is not None or self.locked_prices
                or any(key in self.project_metadata for key in
                       ('quantity_decimals','price_decimals','amount_decimals','economic_rounding','engine'))):
            from .calculations import calculator_for
            return calculator_for(self).relation(relation_id).amount
        relation = self._relation(relation_id)
        return relation.factor * self.relation_quantity(relation_id) * self.concept_price(relation.child_code)

    def total(self) -> Decimal:
        if (self.percentage_profile is not None or self.indirect_config is not None or self.locked_prices
                or any(key in self.project_metadata for key in
                       ('quantity_decimals','price_decimals','amount_decimals','economic_rounding','engine'))):
            from .calculations import calculator_for
            return calculator_for(self).total()
        if self.root_code is None:
            raise BudgetError("Es necesario establecer el concepto raíz")
        return self.concept_price(self.root_code)

    def _relation(self, relation_id: str) -> BudgetRelation:
        try:
            return self._relations_by_id[relation_id]
        except KeyError as exc:
            raise BudgetError(f"Relación desconocida: {relation_id}") from exc
