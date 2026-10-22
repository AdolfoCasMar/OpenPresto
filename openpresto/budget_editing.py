"""Budget editing rules; no widget, locale, dialog or selection dependencies."""
from dataclasses import replace
from .budget import BudgetError, BudgetConcept, BudgetRelation, BudgetMeasurement
from .bc3_measurements import BC3MeasurementLine, rebuild_record


def edit_relation(budget, relation_id, field, value):
    relation = budget._relation(relation_id)
    if field not in ('quantity', 'factor'):
        raise BudgetError('Campo de relación no editable')
    if field == 'quantity':
        if '%' in relation.child_code:
            raise BudgetError('La base porcentual se calcula desde los componentes anteriores.')
        if any(m.relation_id == relation_id for m in budget.measurements) or (
                relation_id in budget.bc3_measurements and budget.bc3_measurements[relation_id].lines):
            raise BudgetError('Cantidad calculada: edita las mediciones.')
    updated = replace(relation, **{field: value})
    budget.relations[budget.relations.index(relation)] = updated
    budget._relations_by_id[relation_id] = updated


def edit_concept(budget, code, changes):
    if not isinstance(changes, dict) or not changes or set(changes) - {'nature','unit','summary','base_price','text','measurement_decimals'}:
        raise BudgetError('Campos de concepto no editables')
    if code not in budget.concepts:
        raise BudgetError('Concepto desconocido: ' + str(code))
    changes = dict(changes)
    if 'base_price' in changes:
        price = changes.pop('base_price')
        if '%' in code:
            from .percentage_calculations import set_percentage_rate
            set_percentage_rate(budget, code, price)
        else:
            if any(r.parent_code == code for r in budget.relations):
                raise BudgetError('Precio calculado: utiliza bloquear o ajustar precio.')
            changes['base_price'] = price
    budget.concepts[code] = replace(budget.concepts[code], **changes)


def _validate_subtotal_edit(budget, old, updated):
    if (budget.project_metadata.get('measurement_kind:' + old.id) in ('1','2')
            and replace(updated, comment=old.comment) != old):
        raise BudgetError('Un subtotal se calcula desde las líneas anteriores. Solo se edita su comentario.')


def edit_measurement(budget, measurement_id, field, value):
    if field not in ('comment','n_lines','length','width','height','formula','annulled_dimensions'):
        raise BudgetError('Campo de medición no editable')
    old = next((m for m in budget.measurements if m.id == measurement_id), None)
    if old is None:
        raise BudgetError('Medición desconocida')
    if field == 'annulled_dimensions':
        value = tuple(value)
    updated=replace(old, **{field:value})
    _validate_subtotal_edit(budget,old,updated)
    budget.measurements[budget.measurements.index(old)] = updated


def edit_bc3_measurement(budget, relation_id, index, field, value):
    if field not in ('description','a','b','c','d','formula','kind'):
        raise BudgetError('Campo BC3 no editable')
    record = budget.bc3_measurements.get(relation_id)
    if record is None or type(index) is not int or not 0 <= index < len(record.lines):
        raise BudgetError('Medición BC3 desconocida')
    rows = list(record.lines)
    changes = {'description':value, 'kind':'3' if value.strip() else ''} if field == 'formula' else {field:value}
    rows[index] = replace(rows[index], **changes)
    budget.bc3_measurements[relation_id] = rebuild_record(record, rows)


def move_measurement(budget, kind, identity, delta):
    if type(delta) is not int or delta not in (-1,1):
        raise BudgetError('Movimiento de medición inválido')
    if kind == 'native':
        from .measurement_operations import move_native_line
        return move_native_line(budget, identity, delta)
    record = budget.bc3_measurements.get(kind)
    if record is None or type(identity) is not int or not 0 <= identity < len(record.lines):
        raise BudgetError('Medición BC3 desconocida')
    rows = list(record.lines)
    target = identity + delta
    if 0 <= target < len(rows):
        rows[identity], rows[target] = rows[target], rows[identity]
        budget.bc3_measurements[kind] = rebuild_record(record, rows)


def add_concept(budget, data, parent_code=None):
    concept = BudgetConcept(**data)
    if parent_code is not None and parent_code not in budget.concepts:
        raise BudgetError('El concepto superior no existe')
    budget.add_concept(concept)
    if budget.root_code is None:
        budget.set_root(concept.code)
    elif parent_code is not None:
        quantity=concept.base_price/100 if '%' in concept.code else '1'
        position=max((r.position for r in budget.relations if r.parent_code==parent_code),default=0)+1
        budget.add_relation(BudgetRelation(parent_code,concept.code,quantity,position))


def add_relation(budget, data):
    from .hierarchy_services import insert_relation
    return insert_relation(budget, BudgetRelation(**data))


def add_measurement(budget, data):
    data = dict(data)
    data['annulled_dimensions'] = tuple(data.get('annulled_dimensions', ()))
    if data['relation_id'] in budget.bc3_measurements:
        raise BudgetError('La relación tiene mediciones BC3; utiliza su editor.')
    budget.add_measurement(BudgetMeasurement(**data))

def set_locked_price(budget, code, value=None):
    if code not in budget.concepts:
        raise BudgetError('Concepto desconocido')
    if value is None:
        budget.locked_prices.pop(code, None)
    else:
        from .budget import _decimal
        budget.locked_prices[code] = _decimal(value, 'Precio bloqueado')
    from .calculations import calculator_for
    calculator_for(budget).total()


def scale_prices(budget, factor, codes):
    from .budget import _decimal
    from .price_operations import scale_resource_prices
    return scale_resource_prices(budget, _decimal(factor, 'Factor'), codes)


def adjust_price(budget, code, target):
    from .budget import _decimal
    from .price_adjustment import adjust_price as adjust
    return adjust(budget, code, _decimal(target, 'Precio objetivo')).budget

def set_engine(budget, engine=None):
    if engine not in (None, 'native-v1'):
        raise BudgetError('Motor económico desconocido')
    if engine is None:
        budget.project_metadata.pop('engine', None)
    else:
        budget.project_metadata['engine'] = engine


def set_precision(budget, quantity_decimals, price_decimals, amount_decimals, rounding='ROUND_HALF_UP'):
    if budget.project_metadata.get('engine') != 'native-v1' and (budget.percentage_profile or budget.indirect_config or budget.locked_prices):
        raise BudgetError('Precisión personalizada incompatible con el perfil histórico activo')
    values = {'quantity_decimals':quantity_decimals,'price_decimals':price_decimals,'amount_decimals':amount_decimals}
    if any(type(v) is not int or not 0 <= v <= 12 for v in values.values()) or rounding not in ('ROUND_HALF_UP','ROUND_HALF_EVEN','ROUND_DOWN'):
        raise BudgetError('Precisión o redondeo inválidos')
    budget.project_metadata.update({k:str(v) for k,v in values.items()})
    budget.project_metadata['economic_rounding'] = rounding


def set_root_precision(budget, value=None):
    from .calculations import CalculationPolicy
    CalculationPolicy(root_quantity_decimals=value)
    budget.root_quantity_decimals = value


def set_indirect_costs(budget, config=None):
    budget.indirect_config = config


def set_summary_rates(budget, overhead_percent, profit_percent, tax_percent):
    from .economic_summary import economic_summary
    budget.project_metadata.update(overhead_percent=str(overhead_percent),
        profit_percent=str(profit_percent), tax_percent=str(tax_percent))
    economic_summary(budget)


def replace_relation(budget, relation_id, data):
    from .storage import to_dict, from_dict, economic_document
    old = budget._relation(relation_id)
    proposed = BudgetRelation(**dict(data, id=old.id, factor=old.factor))
    measured = any(m.relation_id == relation_id for m in budget.measurements) or (
        relation_id in budget.bc3_measurements and budget.bc3_measurements[relation_id].lines)
    if (measured or budget.has_certification(relation_id)) and proposed != old:
        raise BudgetError('No se reasignan relaciones con mediciones o certificación; modifica sus líneas.')
    if '%' in old.child_code:
        raise BudgetError('La base porcentual es calculada; edita el tipo en Precios.')
    document = to_dict(budget)
    row = next(r for r in economic_document(document)['relations'] if r['id'] == old.id)
    row.update(parent_code=proposed.parent_code, child_code=proposed.child_code,
        position=proposed.position, quantity=str(proposed.quantity))
    return from_dict(document)


def replace_concept(budget, data):
    from .calculations import calculator_for
    proposed = BudgetConcept(**data)
    old = budget.concepts[proposed.code]
    percentage = '%' in old.code and (budget.percentage_profile is not None or budget.project_metadata.get('engine') == 'native-v1')
    composed = any(r.parent_code == old.code for r in budget.relations)
    displayed = calculator_for(budget).price(old.code) if percentage or composed else old.base_price
    if percentage and proposed.base_price != displayed:
        from .percentage_calculations import set_percentage_rate
        set_percentage_rate(budget, old.code, proposed.base_price)
        proposed = replace(proposed, base_price=budget.concepts[old.code].base_price)
    elif percentage or composed:
        if composed and proposed.base_price != displayed:
            raise BudgetError('Precio calculado: utiliza bloquear o ajustar precio.')
        proposed = replace(proposed, base_price=old.base_price)
    budget.concepts[old.code] = proposed


def replace_bc3_line(budget, relation_id, data, index=None):
    record = budget.bc3_measurements[relation_id]
    line = BC3MeasurementLine(**data)
    rows = list(record.lines)
    if index is None:
        rows.append(line)
    elif type(index) is int and 0 <= index < len(rows):
        rows[index] = line
    else:
        raise BudgetError('Índice BC3 inválido')
    budget.bc3_measurements[relation_id] = rebuild_record(record, rows)


def replace_measurement(budget, data):
    data = dict(data)
    data['annulled_dimensions'] = tuple(data.get('annulled_dimensions', ()))
    line = BudgetMeasurement(**data)
    old = next((m for m in budget.measurements if m.id == line.id), None)
    if old is None or old.relation_id != line.relation_id:
        raise BudgetError('La línea no existe o pertenece a otra relación')
    _validate_subtotal_edit(budget,old,line)
    budget.measurements[budget.measurements.index(old)] = line

def edit_many_concepts(budget, codes, field, value):
    if field not in ('unit','summary','nature','base_price'):
        raise BudgetError('Campo masivo no editable')
    if not isinstance(codes, (list, tuple)) or not codes:
        raise BudgetError('Selecciona conceptos')
    if field == 'base_price':
        if any('%' in code for code in codes) or any(r.parent_code in codes for r in budget.relations):
            raise BudgetError('La edición masiva de precio requiere conceptos básicos ordinarios')
    for code in set(codes):
        edit_concept(budget, code, {field:value})


def set_project_properties(budget, changes):
    if not isinstance(changes, dict) or set(changes) - {'title','author','client','location','currency'} or any(not isinstance(v,str) for v in changes.values()):
        raise BudgetError('Propiedades de proyecto inválidas')
    budget.project_metadata.update(changes)


def attach_document(budget, code, path):
    if code not in budget.concepts or not isinstance(path,str) or not path or '\0' in path:
        raise BudgetError('Referencia documental inválida')
    item = {'concept':code, 'path':path}
    if item not in budget.documents:
        budget.documents.append(item)


def remove_document(budget, index):
    if type(index) is not int or not 0 <= index < len(budget.documents):
        raise BudgetError('Documento desconocido')
    budget.documents.pop(index)
