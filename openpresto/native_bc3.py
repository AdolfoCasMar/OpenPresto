"""Conversión explícita y acotada del presupuesto nativo al perfil BC3 2002."""
from decimal import Decimal
import ast
from .storage import dumps,loads
from .native_calculations import NativeBudgetCalculator


def render_native_bc3(budget,encoding):
    from .bc3_exporter import render_bc3,BC3Export,BC3ExportError
    if budget.project_metadata.get('percentage_base_mode') is not None:
        raise BC3ExportError('El cálculo porcentual sobre base completa no se conserva en este perfil BC3; guarda el proyecto JSON')
    if budget.locked_prices:
        raise BC3ExportError('El intercambio combinado de bloqueos no conserva su estado; guarda JSON o desactiva los bloqueos en una copia')
    keys=('quantity_decimals','price_decimals','amount_decimals','economic_rounding')
    policy=NativeBudgetCalculator(budget).policy
    if ((policy.quantity_decimals,policy.price_decimals,policy.amount_decimals)!=(3,2,2)
            or getattr(policy,'rounding','ROUND_HALF_UP')!='ROUND_HALF_UP'):
        raise BC3ExportError('La política económica personalizada necesita una conversión BC3 adicional; conserva JSON')
    for record in budget.bc3_measurements.values():
        active=False
        if not record.native_formulas:
            for line in record.lines:
                if line.kind=='3':
                    tree=ast.parse(line.description,mode='eval')
                    active=any(isinstance(node,ast.Name) and node.id.lower() in ('a','b','c','d') for node in ast.walk(tree))
                elif active and line.kind=='' and any(value.strip() for value in (line.a,line.b,line.c,line.d)):
                    raise BC3ExportError('La medición usa fórmulas legadas por línea que cambiarían al heredar expresiones BC3. Conserva JSON o convierte explícitamente sus líneas.')
    calculator=NativeBudgetCalculator(budget)
    for relation in budget.relations:
        if relation.parent_code != budget.root_code:
            continue
        quantity=calculator.quantity(relation.id)
        record=budget.bc3_measurements.get(relation.id)
        measured=bool(record and record.lines) or any(m.relation_id==relation.id for m in budget.measurements)
        raw=budget.relation_quantity(relation.id) if measured else quantity
        if calculator.policy.quantity(raw) != quantity:
            raise BC3ExportError('La precisión de una cantidad de raíz no se conserva en el perfil de importación nativo del intercambio')
    clone=loads(dumps(budget))
    clone.project_metadata.pop('engine',None)
    for key in keys:
        clone.project_metadata.pop(key,None)
    config=clone.indirect_config
    clone.indirect_config=None
    clone.percentage_profile='presto88_bc3' if any('%' in code for code in clone.concepts) else None
    warnings=['Exportación del presupuesto nativo al subconjunto BC3 2002 documentado. Conserva JSON para las propiedades nativas.']
    if clone.certified_quantities or clone.certification_schedule is not None or clone.phase_certified_quantities:
        warnings.append('El BC3 contiene el presupuesto, no las cantidades ni estados de certificación; conserva el proyecto JSON.')
        clone.certified_quantities={}
        clone.certification_schedule=None
        clone.phase_certified_quantities={}
    if config is not None:
        if (budget.project_metadata.get('currency','EUR') or 'EUR') != 'EUR':
            raise BC3ExportError('El perfil nativo de indirectos de intercambio declara EUR; no se cambia la moneda implícitamente')
        if config['exclude_undecomposed'] or budget.root_quantity_decimals != 0:
            raise BC3ExportError('La conversión nativa de indirectos requiere inclusión de simples y precisión de raíz 0')
        chapters=set(config['chapter_codes'])
        roots={r.child_code for r in budget.relations if r.parent_code==budget.root_code}
        if not chapters or roots != chapters:
            raise BC3ExportError('El perfil de intercambio requiere raíz → capítulos explícitos → partidas')
        items={r.child_code for r in budget.relations if r.parent_code in chapters}
        if items & chapters or budget.root_code in items:
            raise BC3ExportError('La jerarquía de capítulos no corresponde al perfil de indirectos exportable')
        for code in chapters:
            from dataclasses import replace
            clone.concepts[code]=replace(clone.concepts[code],nature='capítulo')
        for relation in budget.relations:
            if relation.parent_code in (chapters | {budget.root_code}):
                continue
            if relation.parent_code not in items:
                raise BC3ExportError('Los recursos auxiliares anidados requieren un perfil BC3 adicional para indirectos')
            if any(child.parent_code==relation.child_code for child in budget.relations):
                raise BC3ExportError('Los recursos de partida deben ser básicos en este perfil BC3 de indirectos')
        warnings.append('Indirectos con inclusión de partidas simples mediante ~K; recalculo del receptor pendiente de validar para esta combinación.')
    ordinary=render_bc3(clone,encoding=encoding,native_dimensions=True)
    identities={code.rstrip('#'):code for code in budget.concepts}
    rows=[]
    for row in ordinary.data.decode(encoding).splitlines():
        if row.startswith('~C|'):
            fields=row.split('|')
            code=identities[fields[1].split('\\')[0].rstrip('#')]
            fields[4]=str(calculator.price(code))
            row='|'.join(fields)
        rows.append(row)
    if config is not None:
        rows.insert(1,'~K|\\2\\2\\3\\2\\2\\2\\2\\EUR\\|'+str(calculator.indirect_rate)+'|')
    return BC3Export(('\r\n'.join(rows)+'\r\n').encode(encoding),tuple(warnings)+ordinary.warnings)
