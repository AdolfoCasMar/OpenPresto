"""Importación de ~C/~D/~M de FIEBDC-3/2002 con perfil de medición por línea.

Conserva registros originales. No declara compatibilidad total con BC3 o Presto.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .budget import Budget, BudgetConcept, BudgetRelation, BudgetError, special_price_kind


class BC3ImportError(ValueError):
    """Archivo o estructura BC3 no admisible para esta fase."""


@dataclass(frozen=True)
class ImportResult:
    budget: Budget
    declared_prices: dict[str, Decimal]
    raw_records: tuple[tuple[str, str], ...]
    record_counts: dict[str, int]
    unsupported_counts: dict[str, int]
    warnings: tuple[str, ...]
    root_code: str


def _decimal(value: str, context: str) -> Decimal:
    try:
        number = Decimal(value.strip())
    except InvalidOperation as exc:
        raise BC3ImportError(f"Decimal incorrecto en {context}: {value!r}") from exc
    if not number.is_finite():
        raise BC3ImportError(f"Decimal no finito en {context}")
    return number


def restore_texts(budget):
    """Restaura ~T en el mismo modelo, también al migrar proyectos v2."""
    from .bc3_aliases import source_synonyms, reference_codes
    aliases = reference_codes(budget.concepts, source_synonyms(budget.source_records, budget.concepts))
    for kind, body in budget.source_records:
        if kind == 'T':
            fields = body.split('|')
            if len(fields) >= 2:
                code = aliases.get(fields[0].strip().rstrip('#'))
                if code:
                    budget.concepts[code] = replace(budget.concepts[code], text=fields[1])


def import_bc3(path: str | Path, *, observed_presto88: bool = False, native_economic: bool = False) -> ImportResult:
    """Importa estructura y mediciones compatibles sin alterar el archivo fuente.

    Las mediciones no interpretables se conservan y generan avisos; en esas
    relaciones se mantiene la cantidad ~D, sin inventar un cálculo.
    """
    source = Path(path)
    try:
        with source.open('rb') as stream:
            raw = stream.read(50 * 1024 * 1024 + 1)
    except OSError as exc:
        raise BC3ImportError(f"No se pudo leer {source}: {exc}") from exc
    if not raw or len(raw) > 50 * 1024 * 1024:
        raise BC3ImportError("Archivo vacío o demasiado grande")
    if b"\x00" in raw:
        raise BC3ImportError("El archivo parece binario, no BC3 ANSI")
    from .bc3 import _encoding, BC3Error
    try:
        encoding, encoding_warning = _encoding(raw)
        text = raw.decode(encoding)
    except (BC3Error, UnicodeError) as exc:
        raise BC3ImportError(f"Codificación BC3 no válida: {exc}") from exc
    records = []
    for section in text.split("~"):
        if not section.strip():
            continue
        kind, separator, body = section.partition("|")
        if not separator or len(kind) != 1:
            raise BC3ImportError("Registro BC3 no válido")
        records.append((kind, body.rstrip("\r\n")))
    versions = [body for kind, body in records if kind == "V"]
    if len(versions) != 1 or "FIEBDC-3/2002" not in versions[0]:
        raise BC3ImportError("Esta primera versión solo admite FIEBDC-3/2002")
    indirect_rate = None
    for kind, body in records:
        if kind == 'K':
            fields = body.split('|')
            # The native indirect-cost trial carries economic configuration in
            # this field. Do not silently recalculate it as a direct budget.
            if len(fields) > 1 and fields[1].strip():
                from .bc3_coefficients import economic_coefficients
                try:
                    values = economic_coefficients(fields[1])
                except ValueError as exc:
                    raise BC3ImportError(str(exc)) from exc
                if any(value != 0 for value in values):
                    known_decimals = '\\2\\2\\3\\2\\2\\2\\2\\EUR\\'
                    if (not (observed_presto88 or native_economic) or fields[0] != known_decimals
                            or values[0] < 0 or any(values[1:]) or indirect_rate is not None
                            or any(field.strip() for field in fields[2:])):
                        raise BC3ImportError('Configuración económica ~K no compatible con el perfil contrastado')
                    indirect_rate = values[0]
    declared = {}
    concepts = {}
    decompositions = []
    decomposition_actions = []
    for kind, body in records:
        if kind == "C":
            fields = body.split("|")
            if len(fields) < 4:
                raise BC3ImportError("Registro ~C incompleto")
            code_field, unit, summary, price_text = fields[:4]
            from .bc3_aliases import concept_codes
            try:
                code = concept_codes(code_field)[0]
            except ValueError as exc:
                raise BC3ImportError(str(exc)) from exc
            if not code or code in concepts:
                raise BC3ImportError(f"Concepto vacío o duplicado: {code!r}")
            # Se conserva el código literal (incluido #) para las referencias
            # internas; si el ~C contiene varios precios, este primer importador
            # no selecciona un precio arbitrariamente.
            if "\\" in price_text:
                raise BC3ImportError(f"Varios precios en {code}: pendiente de implementación")
            price = _decimal(price_text, f"~C {code}") if price_text.strip() else Decimal(0)
            concepts[code] = BudgetConcept(code, unit, summary, nature=fields[5].strip() if len(fields) > 5 else '', base_price=price)
            declared[code] = price
        elif kind == "D" or (native_economic and kind == "Y"):
            fields = body.split("|")
            if len(fields) < 2:
                raise BC3ImportError("Registro ~D incompleto")
            decompositions.append((fields[0], fields[1]))
            decomposition_actions.append((kind,fields[0],fields[1]))
    if not concepts:
        raise BC3ImportError("No hay conceptos")
    # En FIEBDC, # distingue el código de capítulo en ~C, pero en las
    # descomposiciones suele aparecer sin #. Resolver sin colisiones.
    from .bc3_aliases import source_synonyms, reference_codes
    try:
        synonyms = source_synonyms(records, concepts)
        if observed_presto88 and any(synonyms.values()):
            raise BC3ImportError('Sinónimos BC3: el ensayo Presto 8.8 no resolvió sus referencias. '
                                 'Usa la importación documental sin el perfil 8.8 para conservarlas.')
        canonical = reference_codes(concepts, synonyms)
    except ValueError as exc:
        raise BC3ImportError(str(exc)) from exc

    def resolve(code: str) -> str:
        if code not in canonical:
            raise BC3ImportError(f"Referencia sin concepto ~C: {code!r}")
        return canonical[code]

    children = []
    factor_warnings = []
    if native_economic:
        combined={}
        for action,parent,items in decomposition_actions:
            canonical_parent=resolve(parent)
            if action=='D':
                combined[canonical_parent]=items
            else:
                previous=combined.get(canonical_parent,'').rstrip('\\')
                combined[canonical_parent]=(previous+'\\' if previous else '')+items
        decompositions=list(combined.items())
    for parent, raw_items in decompositions:
        pieces = raw_items.rstrip("\\").split("\\")
        if not raw_items or pieces == [""]:
            continue
        if len(pieces) % 3:
            raise BC3ImportError(f"Descomposición ~D incompleta: {parent}")
        parent_code = resolve(parent)
        for pos, index in enumerate(range(0, len(pieces), 3), start=1):
            child, factor, yield_value = pieces[index:index+3]
            # Perfil actual: se combinan ambos campos. No acredita que Presto
            # conserve o aplique el factor de la misma manera.
            factor_value = _decimal(factor, f"factor ~D {parent}")
            yield_number = _decimal(yield_value, f"rendimiento ~D {parent}")
            quantity = factor_value * yield_number
            if factor_value != Decimal(1):
                factor_warnings.append(
                    f"~D {parent} / {child}: factor {factor_value} combinado con rendimiento; "
                    "no se conserva como campo editable separado. "
                    "Equivalencia con Presto no verificada para esta relación.")
            children.append((parent_code, resolve(child), pos,
                             yield_number if observed_presto88 or native_economic else quantity,
                             factor_value if observed_presto88 or native_economic else Decimal('1')))

    roots = sorted(set(concepts) - {child for _, child, _, _, _ in children})
    main_roots = [code for code in roots if code.endswith("##")]
    if len(main_roots) != 1:
        raise BC3ImportError(f"No se pudo determinar una raíz principal: {roots[:12]}")
    main_root = main_roots[0]
    budget = Budget(root_code=main_root)
    if native_economic:
        budget.project_metadata['engine']='native-v1'
        if indirect_rate is not None:
            budget.root_quantity_decimals=0
    if observed_presto88:
        budget.root_quantity_decimals = 0
        budget.bc3_zero_dimensions_as_blank = True
    try:
        for concept in concepts.values():
            budget.add_concept(concept)
        for parent, child, position, quantity, factor in children:
            budget.add_relation(BudgetRelation(parent, child, quantity, position, factor=factor))
    except BudgetError as exc:
        raise BC3ImportError(f"Descomposición incompatible: {exc}") from exc
    counts = dict(Counter(kind for kind, _ in records))
    unsupported = {kind: count for kind, count in counts.items()
                   if kind not in {"C", "D", "V", "T"}}
    warnings = [
        "Perfil de medición: parciales a 2 decimales HALF_UP; fórmulas por línea (+, -, *, /).",
        ("Política económica: cantidades raíz 0 y resto 3, precios 2, importes 2 decimales; ~K no se aplica."
         if observed_presto88 else "Política económica fija: cantidades 3, precios 2, importes 2 decimales; ~K no se aplica."),
        "Los precios ~C se conservan por separado: el motor puede calcular importes distintos.",
        "Textos ~T editables; imágenes, ofertas y pliegos permanecen en registros originales.",
        f"Conceptos desconectados de la raíz principal: {len(roots) - 1}.",
        "No guardar el Budget parcial como sustituto del BC3 original.",
    ]
    if encoding_warning:
        warnings.append(encoding_warning)
    if any(synonyms.values()):
        warnings.append('Sinónimos BC3: interpretación documental; el ensayo Presto 8.8 no conservó '
                        'esas identidades y referencias. No se declara equivalencia con ese perfil.')
    for code in concepts:
        kind = special_price_kind(code)
        if kind and not (native_economic and kind == 'porcentaje'):
            warnings.append(f'Cálculo no disponible: {code} es de tipo {kind}; sus datos se conservan pero no se valora como recurso ordinario.')
    if native_economic:
        warnings.append('Motor nativo propio: factores separados, porcentajes por prefijo y configuración ~K documentada; no acredita equivalencia externa.')
    elif not observed_presto88:
        warnings.extend(factor_warnings)
    else:
        warnings.append('Perfil contrastado parcial Presto 8.8: factor separado; cantidades de raíz a 0 decimales; dimensiones cero tratadas como vacías en líneas normales BC3. No certifica compatibilidad general; solo admite la configuración ~K contrastada.')
    from .bc3_measurements import parse_measurement, rebuild_record, MeasurementParseError
    pending = {}
    rejected = set()
    applied_appends = 0
    for kind, body in records:
        if kind not in ("M", "N"):
            continue
        relation = None
        try:
            record = parse_measurement(body, zero_dimensions_as_blank=observed_presto88,native_formulas=native_economic)
            refs = record.reference.split("\\")
            child = resolve(refs[-1])
            parent = resolve(refs[-2]) if len(refs) > 1 else None
            matches = [r for r in budget.relations if r.child_code == child
                       and (parent is None or r.parent_code == parent)]
            positions = [int(v) for v in record.phase.split("\\") if v]
            if positions:
                current = main_root
                target = None
                for pos in positions:
                    targets = [r for r in budget.relations if r.parent_code == current and r.position == pos]
                    if len(targets) != 1:
                        raise MeasurementParseError("Ruta de posiciones no válida")
                    target = targets[0]
                    current = target.child_code
                matches = [r for r in matches if r.id == target.id]
            if len(matches) != 1:
                raise MeasurementParseError("Referencia de medición ambigua o inexistente")
            relation = matches[0]
            if kind == 'N':
                if relation.id in rejected or not record.lines or record.calculated_quantity is None:
                    rejected.add(relation.id)
                    pending.pop(relation.id, None)
                    raise MeasurementParseError('Registro ~N no calculable; se conserva la cantidad de descomposición')
                previous = pending.get(relation.id)
                if previous is None:
                    # Appending to an unexpanded manual quantity has no explicit line origin.
                    if relation.quantity != 0:
                        raise MeasurementParseError('~N sin desglose previo: no se transforma una cantidad manual en líneas implícitas')
                    pending[relation.id] = record
                else:
                    pending[relation.id] = rebuild_record(previous, [*previous.lines, *record.lines])
                applied_appends += 1
                continue
            if relation.id in pending or relation.id in rejected:
                rejected.add(relation.id)
                pending.pop(relation.id, None)
                raise MeasurementParseError("Varios registros ~M para una relación; conservados sin aplicar")
            if record.calculated_quantity is None:
                raise MeasurementParseError("; ".join(record.warnings))
            pending[relation.id] = record
            if record.lines and record.declared_quantity != record.calculated_quantity:
                warnings.append(f"~M {record.reference}: cantidad declarada distinta de la calculada")
        except (MeasurementParseError, BC3ImportError, ValueError) as exc:
            if kind == 'N' and relation is not None:
                pending.pop(relation.id, None)
                rejected.add(relation.id)
            warnings.append(f"Medición no aplicada: {exc}")
    budget.bc3_measurements = pending
    budget.source_records = tuple(records)
    restore_texts(budget)
    if indirect_rate is not None:
        from .indirect_costs import calculator_from_config
        budget.indirect_config = {'profile': 'presto88_default',
            'chapter_codes': sorted(r.child_code for r in budget.relations
                                    if r.parent_code == main_root and r.child_code.endswith('#')),
            'rate': str(indirect_rate), 'exclude_undecomposed': False}
        try:
            if native_economic:
                from .calculations import calculator_for
                calculator_for(budget).total()
            else:
                calculator_from_config(budget)
        except (ValueError, ArithmeticError) as exc:
            raise BC3ImportError(f'Perfil ~K de indirectos no compatible: {exc}') from exc
        warnings.append('Indirectos ~K aplicados incluyendo partidas simples con el motor seleccionado.')
    warnings.append(f"Mediciones aplicadas: {len(pending)} de {counts.get('M', 0)}.")
    if counts.get('N'):
        warnings.append(f"Ampliaciones ~N aplicadas: {applied_appends} de {counts['N']}.")
    budget.import_warnings = tuple(warnings)
    if len(pending) == counts.get("M", 0):
        unsupported.pop("M", None)
    if counts.get('N') and applied_appends == counts['N']:
        unsupported.pop('N', None)
        budget.project_metadata['bc3_applied_n_count'] = str(applied_appends)
    if native_economic:
        unsupported.pop('Y',None)
        if counts.get('Y'):
            budget.project_metadata['bc3_applied_y']='true'
        from .calculations import calculator_for
        try:
            calculator=calculator_for(budget)
            for code in budget.concepts:
                calculator.price(code)
            for relation in budget.relations:
                calculator.relation(relation.id)
            calculator.total()
        except (ValueError,ArithmeticError,RecursionError) as exc:
            raise BC3ImportError('Presupuesto BC3 no calculable con el motor nativo: ' + str(exc)) from exc
    return ImportResult(budget, declared, tuple(records), counts, unsupported,
                        tuple(warnings), main_root)
