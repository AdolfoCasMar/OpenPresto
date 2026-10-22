"""Persistencia JSON local de presupuestos OpenPresto (formato v1).

Los números Decimal se serializan como cadenas para preservar exactitud.
Este formato propio NO es BC3/FIEBDC. El guardado es atómico mediante
archivo temporal y sustitución en el mismo directorio.
"""
from __future__ import annotations

import json
import os
import tempfile
from decimal import Decimal
from pathlib import Path

from .budget import Budget, BudgetConcept, BudgetError, BudgetMeasurement, BudgetRelation

FORMAT = "openpresto-budget"
VERSION = 1
# Native containers can retain a 64 MiB source plus editable module data.
MAX_FILE_BYTES = 256 * 1024 * 1024


class StorageError(ValueError):
    """Archivo de presupuesto no válido o error de almacenamiento."""


def _mapping(value: object, label: str, keys: set[str]) -> dict:
    if not isinstance(value, dict) or set(value) != keys:
        raise StorageError(f"Estructura no válida de {label}")
    return value


def _items(value: object, label: str) -> list:
    if not isinstance(value, list):
        raise StorageError(f"{label} debe ser una lista")
    return value


def _text(value: object, label: str, nullable: bool = False) -> str | None:
    if nullable and value is None:
        return None
    if not isinstance(value, str):
        raise StorageError(f"{label} debe ser texto")
    return value


def _number(value: object, label: str, nullable: bool = False) -> str | None:
    if nullable and value is None:
        return None
    if not isinstance(value, str):
        raise StorageError(f"{label} debe ser una cadena decimal")
    return str(Decimal(value))  # validación posterior con Budget._decimal


def to_dict(budget: Budget) -> dict:
    document = _base_to_dict(budget)
    if budget.locked_prices:
        from .locked_prices import LockedPriceCalculator
        try:
            LockedPriceCalculator(budget, budget.locked_prices).total()
        except (ValueError, ArithmeticError, TypeError, RecursionError) as exc:
            raise StorageError(f'Bloqueos inválidos: {exc}') from exc
        return {'format': FORMAT, 'version': 13,
                'locked_prices': {code: str(value) for code, value in budget.locked_prices.items()},
                'project': document}
    if budget.indirect_config is not None:
        from .indirect_costs import calculator_from_config
        try:
            calculator_from_config(budget)
        except (ValueError, ArithmeticError, TypeError, RecursionError) as exc:
            raise StorageError(f'Indirectos inválidos: {exc}') from exc
        import copy
        return {'format': FORMAT, 'version': 12,
                'indirect_costs': copy.deepcopy(budget.indirect_config), 'project': document}
    if budget.percentage_profile is None:
        return document
    if budget.percentage_profile != 'presto88_bc3':
        raise StorageError('Perfil porcentual no compatible')
    from .percentage_calculations import validate_project_percentages
    try:
        validate_project_percentages(budget)
    except (ValueError, ArithmeticError, RecursionError) as exc:
        raise StorageError(f'Perfil porcentual inválido: {exc}') from exc
    return {'format': FORMAT, 'version': 11, 'percentage_profile': budget.percentage_profile,
            'project': document}


def _base_to_dict(budget: Budget) -> dict:
    """Transforma un presupuesto a un documento JSON sin perder decimales."""
    if not isinstance(budget, Budget):
        raise TypeError("budget debe ser Budget")
    if budget.root_code is not None and budget.root_code not in budget.concepts:
        raise StorageError("El concepto raíz no existe")
    from .bc3_aliases import project_synonyms
    try:
        project_synonyms(budget.source_records, budget.concepts)
    except ValueError as exc:
        raise StorageError(f'Sinónimos BC3 inválidos: {exc}') from exc
    document = {
        "format": FORMAT,
        "version": VERSION,
        "root_code": budget.root_code,
        "concepts": [
            {"code": c.code, "unit": c.unit, "summary": c.summary,
             "nature": c.nature, "base_price": str(c.base_price)}
            for c in budget.concepts.values()
        ],
        "relations": [
            {"id": r.id, "parent_code": r.parent_code, "child_code": r.child_code,
             "quantity": str(r.quantity), "position": r.position}
            for r in budget.relations
        ],
        "measurements": [
            {"id": m.id, "relation_id": m.relation_id, "comment": m.comment,
             "n_lines": str(m.n_lines),
             "length": None if m.length is None else str(m.length),
             "width": None if m.width is None else str(m.width),
             "height": None if m.height is None else str(m.height)}
            for m in budget.measurements
        ],
    }
    if budget.source_records or budget.bc3_measurements:
        document["version"] = 2
        document["bc3"] = {
            "records": [list(r) for r in budget.source_records],
            "measurements": {key: record.raw_body for key, record in budget.bc3_measurements.items()},
            "warnings": list(budget.import_warnings),
        }
    if any(c.text for c in budget.concepts.values()):
        document["version"] = 3
        document.setdefault("bc3", {"records": [], "measurements": {}, "warnings": []})
        for item, concept in zip(document["concepts"], budget.concepts.values()):
            item["text"] = concept.text
    elif any(kind == "T" for kind, _ in budget.source_records):
        # Un texto importado vaciado por el usuario no debe reaparecer desde raw_records.
        document["version"] = 3
        for item in document["concepts"]:
            item["text"] = ""
    separate = budget.bc3_zero_dimensions_as_blank or any(r.factor != 1 for r in budget.relations)
    precision = any(c.measurement_decimals is not None for c in budget.concepts.values())
    annulled = any(m.annulled_dimensions for m in budget.measurements)
    formulas = any(m.formula.strip() for m in budget.measurements) or annulled or precision
    if budget.root_quantity_decimals is not None or separate or formulas:
        from .calculations import CalculationPolicy
        CalculationPolicy(root_quantity_decimals=budget.root_quantity_decimals)
        document["version"] = 4
        document["calculation"] = {"root_quantity_decimals": budget.root_quantity_decimals}
        document.setdefault("bc3", {"records": [], "measurements": {}, "warnings": []})
        for item, concept in zip(document["concepts"], budget.concepts.values()):
            item["text"] = concept.text
        if separate or formulas:
            document['version'] = (8 if precision else 7 if annulled else 6) if formulas else 5
            document['calculation']['bc3_zero_dimensions_as_blank'] = budget.bc3_zero_dimensions_as_blank
            for item, relation in zip(document['relations'], budget.relations):
                item['factor'] = str(relation.factor)
        if formulas:
            for item, measurement in zip(document['measurements'], budget.measurements):
                item['formula'] = measurement.formula
                if annulled or precision:
                    item['annulled_dimensions'] = list(measurement.annulled_dimensions)
    if precision:
        for item, concept in zip(document['concepts'], budget.concepts.values()):
            item['measurement_decimals'] = concept.measurement_decimals
    if budget.certified_quantities or budget.certification_schedule is not None or budget.phase_certified_quantities:
        from .certifications import CertificationAtOrigin
        certification = CertificationAtOrigin(budget, budget.certified_quantities)
        certification.rows()
        document['version'] = 9
        document.setdefault('bc3', {'records': [], 'measurements': {}, 'warnings': []})
        document['calculation'] = {'root_quantity_decimals': budget.root_quantity_decimals,
            'bc3_zero_dimensions_as_blank': budget.bc3_zero_dimensions_as_blank}
        for item, concept in zip(document['concepts'], budget.concepts.values()):
            item['text'] = concept.text
            item['measurement_decimals'] = concept.measurement_decimals
        for item, relation in zip(document['relations'], budget.relations):
            item['factor'] = str(relation.factor)
        for item, measurement in zip(document['measurements'], budget.measurements):
            item['formula'] = measurement.formula
            item['annulled_dimensions'] = list(measurement.annulled_dimensions)
        document['certification_at_origin'] = {key: str(value) for key, value in certification.quantities.items()}
    from .certification_phases import project_phases
    phases = project_phases(budget)
    if phases is not None:
        document['version'] = 10
        schedule = phases.schedule
        document['certification_phases'] = {'start_date': schedule.start_date,
            'end_dates': list(schedule.end_dates), 'current_phase': schedule.current_phase,
            'quantities': [{'phase': number, 'quantities': {rid: str(value) for rid, value in rows.items()}}
                for number, rows in sorted(phases.quantities.items())]}
    return document



def from_dict(data: object, *, project_metadata=None, bc3_formula_profiles=None) -> Budget:
    """Restaura un presupuesto validando referencias, duplicados y ciclos."""
    if isinstance(data, dict) and type(data.get('version')) is int and data['version'] == 13:
        wrapper = _mapping(data, 'documento v13', {'format', 'version', 'locked_prices', 'project'})
        project = wrapper['project']
        if (wrapper['format'] != FORMAT or not isinstance(project, dict)
                or type(project.get('version')) is not int or project['version'] not in range(1, 11)
                or not isinstance(wrapper['locked_prices'], dict) or not wrapper['locked_prices']):
            raise StorageError('Documento de bloqueos no compatible')
        budget = _restore_economic_project(project, project_metadata=project_metadata, bc3_formula_profiles=bc3_formula_profiles)
        try:
            budget.locked_prices = {_text(code, 'código bloqueado'): Decimal(_number(value, 'precio bloqueado'))
                                    for code, value in wrapper['locked_prices'].items()}
            from .locked_prices import LockedPriceCalculator
            LockedPriceCalculator(budget, budget.locked_prices).total()
        except (ValueError, ArithmeticError, TypeError, RecursionError) as exc:
            raise StorageError(f'Bloqueos inválidos: {exc}') from exc
        return budget
    if isinstance(data, dict) and type(data.get('version')) is int and data['version'] == 12:
        wrapper = _mapping(data, 'documento v12', {'format', 'version', 'indirect_costs', 'project'})
        project = wrapper['project']
        if (wrapper['format'] != FORMAT or not isinstance(project, dict)
                or type(project.get('version')) is not int or project['version'] not in range(1, 11)):
            raise StorageError('v12 requiere un proyecto base v1–v10')
        budget = _restore_economic_project(project, project_metadata=project_metadata, bc3_formula_profiles=bc3_formula_profiles)
        import copy
        budget.indirect_config = copy.deepcopy(wrapper['indirect_costs'])
        from .indirect_costs import calculator_from_config
        try:
            calculator_from_config(budget)
        except (ValueError, ArithmeticError, TypeError, RecursionError) as exc:
            raise StorageError(f'Indirectos inválidos: {exc}') from exc
        return budget
    if isinstance(data, dict) and type(data.get('version')) is int and data['version'] == 11:
        wrapper = _mapping(data, 'documento v11', {'format', 'version', 'percentage_profile', 'project'})
        if wrapper['format'] != FORMAT or wrapper['percentage_profile'] != 'presto88_bc3':
            raise StorageError('Perfil porcentual no compatible')
        project = wrapper['project']
        if not isinstance(project, dict) or project.get('version') not in range(1, 11):
            raise StorageError('v11 requiere un proyecto base v1–v10')
        budget = _restore_economic_project(project, project_metadata=project_metadata, bc3_formula_profiles=bc3_formula_profiles)
        budget.percentage_profile = wrapper['percentage_profile']
        from .percentage_calculations import validate_project_percentages
        try:
            validate_project_percentages(budget)
        except (ValueError, ArithmeticError, RecursionError) as exc:
            raise StorageError(f'Perfil porcentual inválido: {exc}') from exc
        return budget
    keys = {"format", "version", "root_code", "concepts", "relations", "measurements"}
    if isinstance(data, dict) and data.get("version") in (2, 3, 4, 5, 6, 7, 8, 9, 10):
        keys.add("bc3")
    if isinstance(data, dict) and data.get("version") in (4, 5, 6, 7, 8, 9, 10):
        keys.add("calculation")
    if isinstance(data, dict) and data.get('version') in (9, 10):
        keys.add('certification_at_origin')
    if isinstance(data, dict) and data.get('version') == 10:
        keys.add('certification_phases')
    document = _mapping(data, "documento", keys)
    if document["format"] != FORMAT or type(document["version"]) is not int or document["version"] not in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10):
        raise StorageError("Formato o versión de presupuesto no compatibles")
    root = _text(document["root_code"], "root_code", nullable=True)
    budget = Budget()
    if project_metadata is not None:
        budget.project_metadata = dict(project_metadata)
    try:
        if document["version"] in (4, 5, 6, 7, 8, 9, 10):
            from .calculations import CalculationPolicy
            calculation_keys = {"root_quantity_decimals"}
            if document['version'] in (5, 6, 7, 8, 9, 10):
                calculation_keys.add('bc3_zero_dimensions_as_blank')
            calculation = _mapping(document["calculation"], "calculation", calculation_keys)
            value = calculation["root_quantity_decimals"]
            CalculationPolicy(root_quantity_decimals=value)
            budget.root_quantity_decimals = value
            if document['version'] in (5, 6, 7, 8, 9, 10):
                flag = calculation['bc3_zero_dimensions_as_blank']
                if type(flag) is not bool:
                    raise StorageError('bc3_zero_dimensions_as_blank debe ser booleano')
                budget.bc3_zero_dimensions_as_blank = flag
        for item in _items(document["concepts"], "concepts"):
            concept_keys = {"code", "unit", "summary", "nature", "base_price"}
            if document["version"] in (3, 4, 5, 6, 7, 8, 9, 10):
                concept_keys.add("text")
            if document['version'] in (8, 9, 10):
                concept_keys.add('measurement_decimals')
            c = _mapping(item, "concepto", concept_keys)
            budget.add_concept(BudgetConcept(
                code=_text(c["code"], "code"), unit=_text(c["unit"], "unit"),
                summary=_text(c["summary"], "summary"),
                nature=_text(c["nature"], "nature"),
                base_price=_number(c["base_price"], "base_price"),
                text=_text(c.get("text", ""), "text"),
                measurement_decimals=c.get("measurement_decimals"),
            ))
        for item in _items(document["relations"], "relations"):
            relation_keys = {"id", "parent_code", "child_code", "quantity", "position"}
            if document['version'] in (5, 6, 7, 8, 9, 10):
                relation_keys.add('factor')
            r = _mapping(item, "relación", relation_keys)
            if type(r["position"]) is not int:
                raise StorageError("position debe ser un entero")
            budget.add_relation(BudgetRelation(
                parent_code=_text(r["parent_code"], "parent_code"),
                child_code=_text(r["child_code"], "child_code"),
                quantity=_number(r["quantity"], "quantity"),
                position=r["position"], id=_text(r["id"], "id"),
                factor=_number(r.get('factor', '1'), 'factor'),
            ))
        for item in _items(document["measurements"], "measurements"):
            measurement_keys = {"id", "relation_id", "comment", "n_lines", "length", "width", "height"}
            if document['version'] in (6, 7, 8, 9, 10):
                measurement_keys.add('formula')
            if document['version'] in (7, 8, 9, 10):
                measurement_keys.add('annulled_dimensions')
            m = _mapping(item, "medición", measurement_keys)
            budget.add_measurement(BudgetMeasurement(
                relation_id=_text(m["relation_id"], "relation_id"),
                comment=_text(m["comment"], "comment"),
                n_lines=_number(m["n_lines"], "n_lines"),
                length=_number(m["length"], "length", nullable=True),
                width=_number(m["width"], "width", nullable=True),
                height=_number(m["height"], "height", nullable=True),
                id=_text(m["id"], "id"),
                formula=_text(m.get('formula', ''), 'formula'),
                annulled_dimensions=tuple(_text(name, 'dimensión anulada') for name in
                    _items(m.get('annulled_dimensions', []), 'annulled_dimensions')),
            ))
        if root is not None:
            budget.set_root(root)
        if document["version"] in (2, 3, 4, 5, 6, 7, 8, 9, 10):
            from .bc3_measurements import parse_measurement
            bc3 = _mapping(document["bc3"], "bc3", {"records", "measurements", "warnings"})
            records = []
            for record in _items(bc3["records"], "records"):
                if not isinstance(record, list) or len(record) != 2:
                    raise StorageError("Registro BC3 inválido")
                records.append(tuple(_text(v, "record") for v in record))
            budget.source_records = tuple(records)
            from .bc3_aliases import project_synonyms
            project_synonyms(budget.source_records, budget.concepts)
            budget.import_warnings = tuple(_text(v, "warning") for v in _items(bc3["warnings"], "warnings"))
            if not isinstance(bc3["measurements"], dict):
                raise StorageError("Mediciones BC3 inválidas")
            for key, body in bc3["measurements"].items():
                budget._relation(key)
                if any(m.relation_id == key for m in budget.measurements):
                    raise StorageError("Motores de medición mezclados")
                record = parse_measurement(_text(body, "body"),
                    zero_dimensions_as_blank=budget.bc3_zero_dimensions_as_blank,
                    native_formulas=(bc3_formula_profiles or {}).get(key,False))
                if record.calculated_quantity is None:
                    raise StorageError("Medición BC3 inválida")
                budget.bc3_measurements[key] = record
            if document["version"] == 2:
                from .bc3_importer import restore_texts
                restore_texts(budget)
        if document['version'] in (9, 10):
            from .certifications import CertificationAtOrigin
            quantities = document['certification_at_origin']
            if not isinstance(quantities, dict):
                raise StorageError('certification_at_origin debe ser un mapa')
            certification = CertificationAtOrigin(budget, {
                _text(key, 'relación certificada'): _number(value, 'CanCert')
                for key, value in quantities.items()})
            certification.rows()
            budget.certified_quantities = dict(certification.quantities)
        if document['version'] == 10:
            from .certification_phases import CertificationSchedule, project_phases
            block = _mapping(document['certification_phases'], 'fases',
                {'start_date', 'end_dates', 'current_phase', 'quantities'})
            budget.certification_schedule = CertificationSchedule(
                _text(block['start_date'], 'start_date') if block['start_date'] is not None else None,
                tuple(_text(value, 'end_date') for value in _items(block['end_dates'], 'end_dates')),
                block['current_phase'])
            for item in _items(block['quantities'], 'quantities'):
                phase = _mapping(item, 'fase', {'phase', 'quantities'})
                number = phase['phase']
                budget.certification_schedule.validate_phase(number)
                if number in budget.phase_certified_quantities:
                    raise StorageError('Número de fase repetido')
                if not isinstance(phase['quantities'], dict):
                    raise StorageError('Las cantidades de fase deben ser un mapa')
                budget.phase_certified_quantities[number] = {
                    _text(rid, 'relación de fase'): Decimal(_number(value, 'CanCert fase'))
                    for rid, value in phase['quantities'].items()}
            project_phases(budget)
    except (BudgetError, ArithmeticError, ValueError, TypeError) as exc:
        raise StorageError(f"Presupuesto inválido: {exc}") from exc
    return budget


def _unique_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for name, value in pairs:
        if name in result:
            raise StorageError(f"Clave JSON duplicada: {name}")
        result[name] = value
    return result


def dumps(budget: Budget) -> str:
    return json.dumps(to_dict(budget), ensure_ascii=False, indent=2) + "\n"


def loads(source: str) -> Budget:
    try:
        data = json.loads(source, object_pairs_hook=_unique_keys,
                          parse_constant=lambda value: (_ for _ in ()).throw(
                              StorageError(f"Constante JSON prohibida: {value}")))
        return from_dict(data)
    except (json.JSONDecodeError, UnicodeError, RecursionError) as exc:
        raise StorageError(f"JSON inválido: {exc}") from exc


def save_budget(budget: Budget, path: str | os.PathLike) -> None:
    """Guarda de forma atómica; nunca altera un archivo BC3 original."""
    target = Path(path)
    if target.suffix.lower() == ".bc3":
        raise StorageError("Guarda el proyecto como JSON; el original BC3 está protegido")
    serialized = dumps(budget).encode("utf-8")
    if len(serialized) > MAX_FILE_BYTES:
        raise StorageError("El presupuesto supera el tamaño máximo permitido")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=f".{target.name}.", suffix=".tmp",
            dir=target.parent, delete=False
        ) as file:
            temporary = Path(file.name)
            file.write(serialized)
            file.flush()
            os.fsync(file.fileno())
        if target.exists():
            # Preserve the previous complete project before replacing it.
            import shutil
            backup = target.with_name(target.name + '.bak')
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as backup_file:
                backup_temp = Path(backup_file.name)
            try:
                shutil.copyfile(target, backup_temp)
                with backup_temp.open('rb+') as backup_file:
                    os.fsync(backup_file.fileno())
                os.replace(backup_temp, backup)
            finally:
                backup_temp.unlink(missing_ok=True)
        os.replace(temporary, target)
    except OSError as exc:
        raise StorageError(f"No se pudo guardar {target}: {exc}") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def load_budget_revision(path: str | os.PathLike):
    """Read one bounded byte snapshot and return model plus its content revision."""
    import hashlib
    target = Path(path)
    try:
        with target.open('rb') as file:
            raw = file.read(MAX_FILE_BYTES + 1)
        if len(raw) > MAX_FILE_BYTES:
            raise StorageError('El archivo supera el tamaño máximo permitido')
        return loads(raw.decode('utf-8-sig')), hashlib.sha256(raw).hexdigest()
    except (OSError,UnicodeError) as exc:
        raise StorageError(f'No se pudo leer {target}: {exc}') from exc


def load_budget(path: str | os.PathLike) -> Budget:
    """Load a native project while retaining the bounded reader contract."""
    return load_budget_revision(path)[0]


# Version 14 adds project metadata without altering prior economic profiles.
_serialize_economic_project = to_dict
_restore_economic_project = from_dict


def to_dict(budget):
    if (any(record.native_formulas for record in budget.bc3_measurements.values())
            and budget.project_metadata.get('engine') != 'native-v1'):
        raise StorageError('Las fórmulas BC3 persistentes necesitan el motor nativo para conservar su interpretación')
    if budget.project_metadata.get('engine') == 'native-v1':
        from copy import copy, deepcopy
        from .native_calculations import NativeBudgetCalculator
        calculator = NativeBudgetCalculator(budget)
        with calculator.batch():
            with calculator.batch():
                for code in budget.concepts:
                    calculator.price(code)
                for relation in budget.relations:
                    calculator.relation(relation.id)
        if budget.root_code is not None:
            calculator.total()
        shadow = copy(budget)
        shadow.locked_prices = {}
        shadow.indirect_config = None
        shadow.percentage_profile = None
        document = _base_to_dict(shadow)
        metadata, documents = _project_information(budget.project_metadata,budget.documents,budget)
        wrapper = {'format':FORMAT,'version':15,'project':document,'metadata':metadata,'documents':documents,
                'locked_prices':{code:str(value) for code,value in budget.locked_prices.items()},
                'indirect_costs':deepcopy(budget.indirect_config),'percentage_profile':budget.percentage_profile}
        profiles={rid:True for rid,record in budget.bc3_measurements.items() if record.native_formulas}
        if profiles:
            wrapper['version']=16
            wrapper['bc3_formula_profiles']=profiles
        return wrapper
    document = _serialize_economic_project(budget)
    if not budget.project_metadata and not budget.documents:
        return document
    metadata, documents = _project_information(budget.project_metadata, budget.documents, budget)
    return {'format': FORMAT, 'version': 14, 'project': document,
            'metadata': metadata, 'documents': documents}


def _project_information(metadata, documents, budget):
    if not isinstance(metadata, dict) or any(not isinstance(k, str) or not isinstance(v, str)
                                           for k, v in metadata.items()):
        raise StorageError('Metadatos de proyecto inválidos')
    if not isinstance(documents, list):
        raise StorageError('Documentos de proyecto inválidos')
    if 'engine' in metadata and metadata['engine'] != 'native-v1':
        raise StorageError('Motor económico desconocido')
    if metadata.get('economic_rounding','ROUND_HALF_UP') not in ('ROUND_HALF_UP','ROUND_HALF_EVEN','ROUND_DOWN'):
        raise StorageError('Modo de redondeo económico inválido')
    for name in ('quantity_decimals', 'price_decimals', 'amount_decimals'):
        if name in metadata and metadata[name] not in {str(i) for i in range(13)}:
            raise StorageError('Precisión económica inválida: ' + name)
    for name in ('overhead_percent', 'profit_percent', 'tax_percent'):
        if name in metadata:
            try:
                value = Decimal(metadata[name])
                if not value.is_finite() or not 0 <= value <= 100:
                    raise ValueError('porcentaje fuera de rango')
            except (ValueError, ArithmeticError) as exc:
                raise StorageError('Porcentaje económico inválido: ' + name) from exc
    copied = []
    for item in documents:
        item = _mapping(item, 'documento vinculado', {'concept', 'path'})
        if (not isinstance(item['concept'], str) or item['concept'] not in budget.concepts
                or not isinstance(item['path'], str) or not item['path'] or '\x00' in item['path']):
            raise StorageError('Referencia documental inválida')
        copied.append(dict(item))
    return dict(metadata), copied


def from_dict(data):
    if isinstance(data,dict) and type(data.get('version')) is int and data['version'] in (15,16):
        keys={'format','version','project','metadata','documents','locked_prices','indirect_costs','percentage_profile'}
        if data['version']==16:
            keys.add('bc3_formula_profiles')
        wrapper = _mapping(data,'proyecto nativo v15/v16',keys)
        profiles=wrapper.get('bc3_formula_profiles',{})
        if not isinstance(profiles,dict) or any(not isinstance(rid,str) or type(flag) is not bool for rid,flag in profiles.items()):
            raise StorageError('Perfiles de fórmula BC3 inválidos')
        if wrapper['format'] != FORMAT or not isinstance(wrapper['project'],dict) or wrapper['project'].get('version') not in range(1,11):
            raise StorageError('Contenedor nativo inválido')
        metadata,_ = _project_information(wrapper['metadata'],[],Budget())
        if metadata.get('engine') != 'native-v1' or not isinstance(wrapper['locked_prices'],dict):
            raise StorageError('Configuración de motor nativo inválida')
        budget = _restore_economic_project(wrapper['project'],project_metadata=metadata,bc3_formula_profiles=profiles)
        if not set(profiles) <= set(budget.bc3_measurements):
            raise StorageError('Perfil de fórmula para una medición inexistente')
        budget.project_metadata,budget.documents = _project_information(metadata,wrapper['documents'],budget)
        try:
            budget.locked_prices = {_text(code,'código bloqueado'):Decimal(_number(value,'precio bloqueado'))
                                    for code,value in wrapper['locked_prices'].items()}
            budget.indirect_config = wrapper['indirect_costs']
            if wrapper['percentage_profile'] not in (None,'presto88_bc3'):
                raise StorageError('Perfil porcentual de origen desconocido')
            budget.percentage_profile = wrapper['percentage_profile']
            from .native_calculations import NativeBudgetCalculator
            calculator = NativeBudgetCalculator(budget)
            with calculator.batch():
                for code in budget.concepts:
                    calculator.price(code)
                for relation in budget.relations:
                    calculator.relation(relation.id)
            from .certifications import CertificationAtOrigin
            CertificationAtOrigin(budget,budget.certified_quantities).rows()
            from .certification_phases import project_phases
            project_phases(budget)
        except (ValueError,ArithmeticError,TypeError,RecursionError) as exc:
            raise StorageError('Proyecto nativo inválido: ' + str(exc)) from exc
        return budget
    if isinstance(data, dict) and type(data.get('version')) is int and data['version'] == 14:
        wrapper = _mapping(data, 'proyecto v14', {'format', 'version', 'project', 'metadata', 'documents'})
        if wrapper['format'] != FORMAT or not isinstance(wrapper['project'], dict) or wrapper['project'].get('version') == 14:
            raise StorageError('Contenedor de proyecto inválido')
        metadata, _ = _project_information(wrapper['metadata'], [], Budget())
        budget = _restore_economic_project(wrapper['project'], project_metadata=metadata)
        budget.project_metadata, budget.documents = _project_information(wrapper['metadata'], wrapper['documents'], budget)
        return budget
    return _restore_economic_project(data)


def economic_document(document):
    """Return the innermost economic graph for validated editing."""
    while isinstance(document, dict) and 'project' in document:
        document = document['project']
    return document


_serialize_project_v16 = to_dict
_restore_project_v16 = from_dict


def to_dict(budget):
    _validate_extensions(budget)
    document = _serialize_project_v16(budget)
    if any('color' in run or 'alignment' in run
           for row in json.loads(budget.project_metadata.get('project_assets_v1','[]'))
           for run in row.get('rich_text',[])):
        return {'format': FORMAT, 'version': 48, 'project': document}
    if any('rich_text' in row for row in json.loads(budget.project_metadata.get('project_assets_v1','[]'))):
        return {'format': FORMAT, 'version': 47, 'project': document}
    if any('source_relation' in row for row in json.loads(budget.project_metadata.get('budget_phase_measurements_v1','{"lines":[]}'))['lines']):
        return {'format': FORMAT, 'version': 46, 'project': document}
    if 'retention_settlements_v1' in budget.project_metadata:
        return {'format': FORMAT, 'version': 45, 'project': document}
    if 'agenda_v1' in budget.project_metadata:
        return {'format': FORMAT, 'version': 44, 'project': document}
    if 'project_assets_v1' in budget.project_metadata:
        return {'format': FORMAT, 'version': 43, 'project': document}
    if 'concept_keywords_v1' in budget.project_metadata:
        return {'format': FORMAT, 'version': 42, 'project': document}
    if any('properties' in row for row in json.loads(budget.project_metadata.get('entities_v1','[]'))):
        return {'format': FORMAT, 'version': 41, 'project': document}
    if any('source_payload' in row for row in json.loads(budget.project_metadata.get('technical_documents_v1','[]'))):
        return {'format': FORMAT, 'version': 40, 'project': document}
    if 'issued_retention_openings_v1' in budget.project_metadata:
        return {'format': FORMAT, 'version': 39, 'project': document}
    if 'retention_openings_v1' in budget.project_metadata:
        return {'format': FORMAT, 'version': 38, 'project': document}
    if 'budget_phase_measurements_v1' in budget.project_metadata:
        return {'format': FORMAT, 'version': 37, 'project': document}
    if 'percentage_base_mode' in budget.project_metadata:
        if budget.project_metadata.get('engine')!='native-v1' or budget.project_metadata['percentage_base_mode']!='exact-amount-v1':
            raise StorageError('Modo de base porcentual inválido')
        return {'format': FORMAT, 'version': 36, 'project': document}
    if 'technical_documents_v1' in budget.project_metadata:
        return {'format': FORMAT, 'version': 35, 'project': document}
    if 'quality_issue_links_v1' in budget.project_metadata:
        return {'format': FORMAT, 'version': 34, 'project': document}
    if 'budget_baselines_v1' in budget.project_metadata:
        return {'format': FORMAT, 'version': 33, 'project': document}
    if 'quality_control_v1' in budget.project_metadata:
        return {'format': FORMAT, 'version': 32, 'project': document}
    if 'site_issues_v1' in budget.project_metadata:
        return {'format': FORMAT, 'version': 31, 'project': document}
    if 'resource_hours_v1' in budget.project_metadata:
        return {'format': FORMAT, 'version': 30, 'project': document}
    if 'production_v1' in budget.project_metadata:
        return {'format': FORMAT, 'version': 29, 'project': document}
    if 'entities_v1' in budget.project_metadata:
        return {'format': FORMAT, 'version': 28, 'project': document}
    if any(key in budget.project_metadata for key in ('linked_proformas_v1','planning_unphased_v1')):
        return {'format': FORMAT, 'version': 27, 'project': document}
    if 'pzh_records_v1' in budget.project_metadata:
        return {'format': FORMAT, 'version': 26, 'project': document}
    if 'issued_management_v1' in budget.project_metadata:
        return {'format': FORMAT, 'version': 25, 'project': document}
    if 'earned_value_v1' in budget.project_metadata:
        return {'format': FORMAT, 'version': 24, 'project': document}
    if 'planning_phases_v1' in budget.project_metadata:
        return {'format': FORMAT, 'version': 23, 'project': document}
    if 'management_schedule_v1' in budget.project_metadata:
        return {'format': FORMAT, 'version': 22, 'project': document}
    management_data=None
    if 'management_v1' in budget.project_metadata:
        from .management import state as management_state
        management_data=management_state(budget)
    service_lines=management_data and any('stock' in line for key in ('documents','contracts') for row in management_data[key] for line in row['lines'])
    if service_lines or (management_data and any('rounding' in row for key in ('contracts','documents') for row in management_data[key])) or any(k in budget.project_metadata for k in ('management_services_v1','management_pricing_v1')):
        return {'format': FORMAT, 'version': 21, 'project': document}
    if management_data:
        documents={r['id']:r for r in management_data['documents']}
        if any(row['status']=='draft' and any(line['source_document'] in documents and documents[line['source_document']]['status']=='draft' for line in row['lines']) for row in documents.values()):
            return {'format': FORMAT, 'version': 20, 'project': document}
    if any(key in budget.project_metadata for key in ('planning_advanced_v1','management_advanced_v1','pzh_operations_v1','management_linked_drafts_v1')):
        return {'format': FORMAT, 'version': 20, 'project': document}
    if any(key in budget.project_metadata for key in ('planning_v1','management_v1')):
        return {'format': FORMAT, 'version': 19, 'project': document}
    context = any(key.startswith(('certification_price:', 'certification_role:'))
                  for key in budget.project_metadata)
    unknown_start = budget.certification_schedule is not None and budget.certification_schedule.start_date is None
    if 'certification_lines_v1' in budget.project_metadata:
        return {'format': FORMAT, 'version': 18, 'project': document}
    if context or unknown_start:
        return {'format': FORMAT, 'version': 17, 'project': document}
    return document


def from_dict(data):
    if isinstance(data, dict) and type(data.get('version')) is int and data['version'] in (17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48):
        wrapper = _mapping(data, 'proyecto v17', {'format', 'version', 'project'})
        project = wrapper['project']
        if wrapper['format'] != FORMAT or not isinstance(project, dict) or project.get('version') in (17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48):
            raise StorageError('Contenedor v17 inválido')
        budget = _restore_project_v16(project)
        _validate_extensions(budget)
        return budget
    budget = _restore_project_v16(data)
    _validate_extensions(budget)
    return budget


def _validate_extensions(budget):
    try:
        if 'retention_settlements_v1' in budget.project_metadata:
            from .retention_settlements import validate as retention_settlements
            retention_settlements(budget)
        if 'agenda_v1' in budget.project_metadata:
            from .agenda import validate as agenda
            agenda(budget)
        if 'project_assets_v1' in budget.project_metadata:
            from .project_assets import validate as project_assets
            project_assets(budget)
        if 'concept_keywords_v1' in budget.project_metadata:
            from .concept_keywords import validate as concept_keywords
            concept_keywords(budget)
        if 'issued_retention_openings_v1' in budget.project_metadata:
            from .issued_retention_openings import validate as issued_retention_openings
            issued_retention_openings(budget)
        if 'retention_openings_v1' in budget.project_metadata:
            from .retention_openings import validate as retention_openings
            retention_openings(budget)
        if 'budget_phase_measurements_v1' in budget.project_metadata:
            from .budget_phase_measurements import state as measurement_phases
            measurement_phases(budget)
        if 'percentage_base_mode' in budget.project_metadata:
            if budget.project_metadata.get('engine')!='native-v1' or budget.project_metadata['percentage_base_mode']!='exact-amount-v1':
                raise StorageError('Modo de base porcentual inválido')
        from .planning_advanced import validate as advanced_planning
        from .management_advanced import validate as advanced_management
        from .pzh_operations import validate as validate_source
        if 'technical_documents_v1' in budget.project_metadata:
            from .technical_documents import validate as validate_technical_documents
            validate_technical_documents(budget)
        if 'quality_issue_links_v1' in budget.project_metadata:
            from .nonconformities import validate as validate_nonconformities
            validate_nonconformities(budget)
        if 'budget_baselines_v1' in budget.project_metadata:
            from .budget_baselines import validate as validate_budget_baselines
            validate_budget_baselines(budget)
        if 'quality_control_v1' in budget.project_metadata:
            from .quality_control import validate as validate_quality_control
            validate_quality_control(budget)
        if 'site_issues_v1' in budget.project_metadata:
            from .site_issues import validate as validate_site_issues
            validate_site_issues(budget)
        if 'resource_hours_v1' in budget.project_metadata:
            from .resource_hours import validate as validate_resource_hours
            validate_resource_hours(budget)
        if 'production_v1' in budget.project_metadata:
            from .production import validate as validate_production
            validate_production(budget)
        if 'entities_v1' in budget.project_metadata:
            from .entities import validate as validate_entities
            validate_entities(budget)
        if 'pzh_records_v1' in budget.project_metadata:
            from .pzh_native_modules import control_records
            control_records(budget)
        if 'pzh_native_conversion_v1' in budget.project_metadata:
            from .pzh_native_modules import results as conversion_results
            conversion_results(budget)
        if 'issued_management_v1' in budget.project_metadata:
            from .issued_management import validate as issued_management
            issued_management(budget)
        if 'earned_value_v1' in budget.project_metadata:
            from .earned_value import validate as earned_value
            earned_value(budget)
        if 'planning_advanced_v1' in budget.project_metadata: advanced_planning(budget)
        if 'planning_phases_v1' in budget.project_metadata:
            from .planning_phases import validate as phase_planning
            phase_planning(budget)
        if 'management_advanced_v1' in budget.project_metadata: advanced_management(budget)
        if 'management_schedule_v1' in budget.project_metadata: advanced_management(budget)
        if 'pzh_operations_v1' in budget.project_metadata: validate_source(budget)
        if 'planning_v1' in budget.project_metadata:
            from .planning import validate as validate_planning
            validate_planning(budget)
        if 'management_v1' in budget.project_metadata:
            from .management import validate as validate_management
            validate_management(budget)
    except (ValueError, TypeError, KeyError, IndexError, RecursionError) as exc:
        raise StorageError('Módulos de obra inválidos: ' + str(exc)) from exc
