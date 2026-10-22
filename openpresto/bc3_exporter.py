"""Limited export of current editable data, never a copy of source records."""
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
import os
import tempfile

from .calculations import calculator_for as BudgetCalculator
from .bc3_measurements import parse_measurement


class BC3ExportError(ValueError):
    pass


@dataclass(frozen=True)
class BC3Export:
    data: bytes
    warnings: tuple[str, ...]


def _field(value, *, code=False):
    text = str(value)
    if any(c in text for c in ('|', '~', '\x00')) or (code and ('\\' in text or any(c.isspace() for c in text))):
        raise BC3ExportError('Hay separadores BC3 no representables en un campo')
    return text.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\r\n')


def render_indirect_trial(budget, *, encoding='cp1252'):
    """Partial indirect profile contrasted with native 8.8 import."""
    from .indirect_costs import calculator_from_config
    from .storage import dumps, loads
    calculator = calculator_from_config(budget)
    if budget.indirect_config['exclude_undecomposed']:
        raise BC3ExportError('La exclusión de simples no se conserva en el ensayo BC3')
    if calculator.policy.quantity_decimals != 3 or calculator.policy.price_decimals != 2 or calculator.policy.amount_decimals != 2:
        raise BC3ExportError('Precisiones de indirectos sin contraste')
    clone = loads(dumps(budget))
    clone.indirect_config = None
    ordinary = render_bc3(clone, encoding=encoding)
    rows = []
    for row in ordinary.data.decode(encoding).splitlines():
        if row.startswith('~M|'):
            continue  # the own native trial uses only ~D quantities
        if row.startswith('~C|'):
            fields = row.split('|')
            code = next(c for c in budget.concepts if c.rstrip('#') == fields[1].split('\\')[0].rstrip('#'))
            fields[4] = str(calculator.price(code))
            row = '|'.join(fields)
        rows.append(row)
    rows.insert(1, '~K|\\2\\2\\3\\2\\2\\2\\2\\EUR\\|' + str(calculator.rate) + '|')
    return BC3Export(('\r\n'.join(rows) + '\r\n').encode(encoding),
                     ('Indirectos: perfil parcial Presto 8.8, incluye partidas simples. '
                      'Para reimportar usa el perfil explícito Presto 8.8; conserva también JSON.',)
                     + ordinary.warnings[1:])


def render_locked_price_trial(budget, *, encoding='cp1252'):
    """Export the bounded manual-price profile contrasted in native Presto 8.8.

    The native trial exports declared manual prices plus decomposition, but
    neither recalculating nor changing resources after import retains a lock.
    """
    from .storage import dumps, loads
    from .bc3_aliases import source_synonyms
    if not budget.locked_prices:
        raise BC3ExportError('El ensayo necesita precios bloqueados explícitos')
    if (budget.root_quantity_decimals != 0 or budget.measurements or budget.bc3_measurements
            or any(r.factor != 1 for r in budget.relations)
            or any(source_synonyms(budget.source_records, budget.concepts).values())):
        raise BC3ExportError('Ensayo de bloqueos limitado a precisión raíz 0, factores 1 y sin mediciones ni sinónimos')
    calculator = BudgetCalculator(budget)
    calculator.total()
    clone = loads(dumps(budget))
    clone.locked_prices = {}
    ordinary = render_bc3(clone, encoding=encoding)
    identities = {code.rstrip('#'): code for code in budget.concepts}
    rows = []
    for row in ordinary.data.decode(encoding).splitlines():
        if row.startswith('~C|'):
            fields = row.split('|')
            code = identities[fields[1].rstrip('#')]
            fields[4] = str(calculator.price(code))
            row = '|'.join(fields)
        rows.append(row)
    rows.insert(1, '~K|\\2\\2\\3\\2\\2\\2\\2\\EUR\\|0|')
    return BC3Export(('\r\n'.join(rows) + '\r\n').encode(encoding),
        ('Archivo de ensayo de precios manuales: no acredita conservar el bloqueo al importar. '
         'En el ensayo Presto 8.8 Recalcular o cambiar un recurso vuelve a calcular desde la descomposición. '
         'Conserva JSON para mantener los bloqueos.',) + ordinary.warnings[1:])


def render_bc3(budget, *, encoding='cp1252', native_dimensions=False):
    """Export C/D/T/M 2002 with ANSI/CRLF, and report precision limitations."""
    if encoding not in ('cp1252', 'utf-8', 'cp850', 'cp437'):
        raise BC3ExportError('Codificación de exportación no admitida')
    if budget.project_metadata.get('engine') == 'native-v1':
        from .native_bc3 import render_native_bc3
        return render_native_bc3(budget,encoding)
    if any(key in getattr(budget, 'project_metadata', {}) for key in ('quantity_decimals', 'price_decimals', 'amount_decimals', 'economic_rounding')):
        raise BC3ExportError('La precisión económica personalizada se conserva en JSON; no se convierte implícitamente al perfil BC3')
    currency = budget.project_metadata.get('currency','EUR') or 'EUR'
    if (budget.indirect_config is not None or budget.locked_prices) and currency != 'EUR':
        raise BC3ExportError('El perfil económico de intercambio actual declara EUR; conserva la moneda y el proyecto en JSON')
    if budget.root_code not in budget.concepts:
        raise BC3ExportError('El presupuesto necesita una raíz válida')
    if budget.locked_prices:
        return render_locked_price_trial(budget, encoding=encoding)
    if budget.indirect_config is not None:
        return render_indirect_trial(budget, encoding=encoding)
    if budget.certified_quantities or budget.certification_schedule is not None or budget.phase_certified_quantities:
        raise BC3ExportError('La certificación a origen todavía no se exporta a BC3; conserva el proyecto JSON')
    if any(c.measurement_decimals is not None for c in budget.concepts.values()):
        raise BC3ExportError('La precisión nativa por concepto aún no se representa en BC3; conserva el proyecto JSON')
    if any(m.formula.strip() for m in budget.measurements):
        raise BC3ExportError('La exportación de fórmulas nativas modernas a BC3 requiere un perfil adicional; conserva el proyecto JSON')
    if any(m.annulled_dimensions for m in budget.measurements):
        raise BC3ExportError('La exportación de dimensiones anuladas necesita contraste BC3; conserva el proyecto JSON')
    supported = {'V', 'K', 'C', 'D', 'T', 'M'}
    if budget.project_metadata.get('bc3_applied_y') == 'true':
        supported.add('Y')
    append_count = sum(kind == 'N' for kind,_ in budget.source_records)
    if (budget.project_metadata.get('bc3_applied_n_count') == str(append_count)
            and not any(w.startswith('Medición no aplicada') for w in budget.import_warnings)):
        supported.add('N')  # applied append records are canonicalized as current ~M lines
    unsupported = {kind for kind, _ in budget.source_records} - supported
    if unsupported:
        raise BC3ExportError('La exportación aún no representa: ' + ', '.join('~'+k for k in sorted(unsupported)))
    if any(w.startswith('Medición no aplicada') for w in budget.import_warnings):
        raise BC3ExportError('Resuelve las mediciones no aplicadas antes de exportar')
    if any('%' in code for code in budget.concepts):
        if budget.percentage_profile != 'presto88_bc3':
            raise BC3ExportError('Los porcentajes requieren el perfil contrastado Presto 8.8')
        from .percentage_calculations import validate_project_percentages
        validate_project_percentages(budget)
        for relation in budget.relations:
            if '%' in relation.child_code:
                rate = relation.quantity * 100
                if rate < 0 or rate != rate.quantize(Decimal('.01')):
                    raise BC3ExportError('Tipo porcentual negativo o de precisión adicional pendiente de contraste')
    aliases = [code.rstrip('#') for code in budget.concepts]
    if len(set(aliases)) != len(aliases):
        raise BC3ExportError('Códigos ambiguos al clasificar raíz y capítulos')
    from .bc3_aliases import source_synonyms, reference_codes
    try:
        synonyms = source_synonyms(budget.source_records, budget.concepts)
        reference_codes(budget.concepts, synonyms)
    except ValueError as exc:
        raise BC3ExportError(str(exc)) from exc
    codes = {code: code for code in budget.concepts}
    codes[budget.root_code] = budget.root_code.rstrip('#') + '##'
    for code in codes:
        if code != budget.root_code and budget.concepts[code].nature.lower() in ('capítulo', 'capitulo'):
            codes[code] = code.rstrip('#') + '#'
        if code != budget.root_code and codes[code].endswith('##'):
            raise BC3ExportError('Solo se puede exportar una raíz principal')
    exported_codes = {code: tuple(dict.fromkeys((codes[code],
                      *((code, *synonyms[code]) if synonyms.get(code) else ()))))
                      for code in codes}
    try:
        reference_codes(codes.values(), {codes[code]: values[1:] for code, values in exported_codes.items()})
    except ValueError as exc:
        raise BC3ExportError(str(exc)) from exc
    calculator = BudgetCalculator(budget)
    groups = {}
    for relation in budget.relations:
        groups.setdefault(relation.parent_code, []).append(relation)
    paths = {budget.root_code: ()}
    pending = [budget.root_code]
    measured = {m.relation_id for m in budget.measurements} | set(budget.bc3_measurements)
    for parent, children in groups.items():
        children.sort(key=lambda r: r.position)
        if [r.position for r in children] != list(range(1, len(children)+1)):
            raise BC3ExportError('Las posiciones deben ser consecutivas para exportar mediciones estructuradas')
    # A repeated parent can be exported for prices, but its measurement paths
    # need a future explicit occurrence model rather than an invented path.
    ambiguous = set()
    while pending:
        parent = pending.pop()
        for relation in groups.get(parent, []):
            child = relation.child_code
            if child in paths:
                ambiguous.add(child)
                continue
            paths[child] = paths[parent] + (relation.position,)
            pending.append(child)
    changed = True
    while changed:
        before = len(ambiguous)
        ambiguous.update(r.child_code for r in budget.relations if r.parent_code in ambiguous)
        changed = len(ambiguous) != before
    for relation in budget.relations:
        if relation.parent_code not in paths or relation.child_code not in paths:
            raise BC3ExportError('No se exportan conceptos o relaciones desconectados de la raíz')
        current = relation.parent_code
        if relation.id in measured and (current in ambiguous):
            raise BC3ExportError('La ruta de una medición reutilizada es ambigua')
    if set(paths) != set(budget.concepts):
        raise BC3ExportError('Hay conceptos desconectados de la raíz')
    charset = {'cp1252': 'ANSI', 'utf-8': 'UTF-8', 'cp850': '850', 'cp437': '437'}[encoding]
    rows = ['~V|OpenPresto|FIEBDC-3/2002|OpenPresto||' + charset + '|']
    types = {'': '0', '0': '0', '1': '1', '2': '2', '3': '3',
             'capítulo': '0', 'capitulo': '0', 'partida': '0', 'otros': '0',
             'mano de obra': '1', 'maquinaria': '2', 'material': '3'}
    for code, concept in budget.concepts.items():
        if concept.nature.lower() not in types:
            raise BC3ExportError(f'Naturaleza no representable: {concept.nature}')
        code_field = '\\'.join(_field(value, code=True) for value in exported_codes[code])
        rows.append('~C|' + '|'.join((code_field, _field(concept.unit),
                    _field(concept.summary), str(calculator.price(code)), '', types[concept.nature.lower()], '')))
        if concept.text:
            rows.append(f'~T|{_field(codes[code], code=True)}|{_field(concept.text)}|')
    for parent, children in groups.items():
        tokens = []
        for relation in children:
            # Native 8.8 export writes the fractional rate, never the displayed base.
            quantity = relation.quantity if '%' in relation.child_code else calculator.quantity(relation.id)
            tokens += [codes[relation.child_code], str(relation.factor), str(quantity)]
        rows.append(f'~D|{_field(codes[parent], code=True)}|' + '\\'.join(tokens) + '\\|')
        for relation in children:
            if '%' in relation.child_code:
                # A synthetic ~M carrying the base would change the percentage semantics.
                continue
            record = budget.bc3_measurements.get(relation.id)
            tokens = []
            if record is not None:
                if record.warnings:
                    raise BC3ExportError('Una medición contiene líneas no interpretadas')
                for line in record.lines:
                    dimensions = [line.b, line.c, line.d]
                    if record.zero_dimensions_as_blank and line.kind == '':
                        dimensions = ['' if v.strip() and Decimal(v) == 0 else v for v in dimensions]
                    elif line.kind == '' and not native_dimensions and any(v.strip() and Decimal(v) == 0 for v in dimensions):
                        raise BC3ExportError('Una dimensión cero requiere un perfil de exportación contrastado')
                    tokens.extend((line.kind, line.description, line.a, *dimensions))
            else:
                for line in (m for m in budget.measurements if m.relation_id == relation.id):
                    kind = budget.project_metadata.get('measurement_kind:' + line.id,'')
                    if kind in ('1','2'):
                        tokens.extend((kind,line.comment,'','','',''))
                        continue
                    dimensions = [line.length, line.width, line.height]
                    if not native_dimensions and any(v == 0 for v in dimensions if v is not None):
                        raise BC3ExportError('No se exportan dimensiones nativas cero sin una representación contrastada')
                    tokens.extend(('', line.comment, str(line.n_lines),
                                   *('' if v is None else str(v) for v in dimensions)))
            for token in tokens:
                if any(c in str(token) for c in ('\\', '|', '~', '\r', '\n')):
                    raise BC3ExportError('Una celda de medición contiene separadores BC3')
            path = paths[relation.parent_code] + (relation.position,)
            route = '\\'.join(map(str, path)) + '\\'
            body = '\\'.join(tokens) + ('\\' if tokens else '')
            if tokens:
                check = parse_measurement(f'P\\C||{calculator.quantity(relation.id)}|{body}|',
                    native_formulas=record.native_formulas if record is not None else False)
                places = (budget.root_quantity_decimals if relation.parent_code == budget.root_code
                          and budget.root_quantity_decimals is not None else calculator.policy.quantity_decimals)
                if check.calculated_quantity is None or calculator.policy._round(check.calculated_quantity, places) != calculator.quantity(relation.id):
                    raise BC3ExportError('La precisión de las líneas no se conserva en este perfil BC3')
            rows.append(f'~M|{codes[parent]}\\{codes[relation.child_code]}|{route}|{calculator.quantity(relation.id)}|{body}|')
    try:
        data = ('\r\n'.join(rows) + '\r\n').encode(encoding)
    except UnicodeError as exc:
        raise BC3ExportError('Hay caracteres fuera de la codificación elegida; no se sustituyen ni se pierden') from exc
    warnings = ('Exportación BC3 parcial de los datos actuales. No aplica ni escribe ~K; '
                'el receptor debe usar precisiones y reglas de cálculo compatibles.',)
    if getattr(budget, 'project_metadata', {}) or getattr(budget, 'documents', []):
        warnings += ('Las propiedades de proyecto y los vínculos documentales nativos no se representan en este perfil BC3; conserva JSON.',)
    if any(Decimal(budget.project_metadata.get(key,'0')) != 0 for key in ('overhead_percent','profit_percent','tax_percent')):
        warnings += ('Los gastos generales, beneficio e impuestos del resumen financiero no se transmiten en este perfil BC3. El archivo contiene el presupuesto base; conserva JSON o el informe económico.',)
    if currency != 'EUR':
        warnings += (f'La moneda {currency} no se escribe en este perfil sin ~K; configúrala en el receptor y conserva JSON.',)
    composed_codes = set(groups)
    rounded_basics = [code for code, concept in budget.concepts.items()
                      if code not in composed_codes and '%' not in code
                      and calculator.price(code) != concept.base_price]
    if rounded_basics:
        shown = ', '.join(rounded_basics[:8])
        if len(rounded_basics) > 8:
            shown += ', …'
        warnings += (f'BC3 guarda precios básicos redondeados en {len(rounded_basics)} conceptos: '
                     f'{shown}. Conserva JSON para mantener todas las cifras originales.',)
    if any(synonyms.values()):
        warnings += ('Sinónimos BC3: Presto 8.8 no conservó sus identidades en el ensayo; '
                     'comprueba la estructura y los códigos en el receptor.',)
    return BC3Export(data, warnings)


def save_bc3(budget, path, *, encoding='cp1252'):
    """Write a new file atomically; an existing destination is never replaced."""
    target = Path(path)
    if target.suffix.lower() != '.bc3':
        raise BC3ExportError('El destino debe tener extensión .bc3')
    result = render_bc3(budget, encoding=encoding)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.openpresto-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(result.data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, target)
    except OSError as exc:
        raise BC3ExportError(f'No se pudo crear un BC3 nuevo: {exc}') from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return result
