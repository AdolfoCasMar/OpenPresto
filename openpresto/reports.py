"""Informes independientes de Qt, derivados del modelo económico activo."""
import csv
import io
from html import escape
from .calculations import calculator_for
from .measurements import summarize_budget


def budget_rows(budget):
    calculator = calculator_for(budget)
    children = {}
    for relation in budget.relations:
        children.setdefault(relation.parent_code, []).append(relation)
    rows = []
    def visit(code, depth, ancestors):
        if code in ancestors:
            raise ValueError('Ciclo en el presupuesto')
        for relation in sorted(children.get(code, ()), key=lambda row: row.position):
            concept = budget.concepts[relation.child_code]
            amount = calculator.relation(relation.id)
            rows.append((depth, concept.code, concept.unit, concept.summary,
                         str(amount.quantity), str(amount.unit_price), str(amount.amount)))
            visit(concept.code, depth + 1, ancestors | {code})
    if budget.root_code:
        visit(budget.root_code, 0, set())
    return rows


def report_table(budget, kind='presupuesto'):
    if kind=='retention_settlements':
        from .retention_settlements import HEADERS,report_rows
        return HEADERS,report_rows(budget)
    if kind=='agenda':
        from .agenda import HEADERS,report_rows
        return HEADERS,report_rows(budget)
    if kind=='agenda_source_totals':
        from .agenda import source_total_rows
        return ('Fecha de agenda','Importe de origen · no es movimiento nativo','Valor conservado'),source_total_rows(budget)
    if kind=='project_assets':
        from .project_assets import HEADERS,report_rows
        return HEADERS,report_rows(budget)
    if kind=='concept_keywords':
        from .concept_keywords import report_rows
        return ('Código','Concepto','Término de búsqueda'),report_rows(budget)
    if kind=='entity_properties':
        from .entities import property_rows
        return ('Código','Entidad','Cantidad','Superficie construida','Ruta de referencia','Activa','Fecha'),property_rows(budget)
    if kind=='entity_source_totals':
        from .entities import source_total_rows
        return ('Código','Entidad','Campo PZH','Total acumulado en origen · no es movimiento nativo','Valor conservado'),source_total_rows(budget)
    if kind=='pzh_completion':
        from .pzh_completion import HEADERS,report_rows
        return HEADERS,report_rows(budget)
    if kind=='retenciones_emitidas_apertura':
        from .issued_retention_openings import HEADERS,report_rows
        return HEADERS,report_rows(budget)
    if kind=='retenciones_apertura':
        from .retention_openings import HEADERS,report_rows
        return HEADERS,report_rows(budget)
    if kind=='mediciones_fases':
        from .budget_phase_measurements import HEADERS,report_rows
        return HEADERS,report_rows(budget)
    if kind in ('documentos_tecnicos','documentos_tecnicos_contenido'):
        from .technical_documents import HEADERS,report_rows,validate
        return (HEADERS,report_rows(budget)) if kind=='documentos_tecnicos' else (('Referencia','Título','Texto'),[(r['reference'],r['title'],r['text']) for r in validate(budget)])
    if kind=='inventario_abc' or kind.startswith('inventario_abc:'):
        from datetime import date
        from .inventory_control import abc,ABC_HEADERS,ABC_SUMMARY_HEADERS
        parts=kind.split(':')
        if len(parts) not in (1,4) or (len(parts)==4 and (parts[2] not in ('detalle','resumen') or parts[3] not in ('saldos','todos'))):raise ValueError('Vista ABC de inventario inválida')
        cut,mode,zeros=parts[1:] if len(parts)==4 else (date.today().isoformat(),'detalle','saldos')
        view=abc(budget,cut,zeros=='todos')
        return (ABC_SUMMARY_HEADERS,view['summary']) if mode=='resumen' else (ABC_HEADERS,view['rows'])
    if kind=='inventario_periodo' or kind.startswith('inventario_periodo:'):
        from datetime import date
        from .inventory_control import period,PERIOD_HEADERS,MOVEMENT_HEADERS
        parts=kind.split(':')
        if len(parts) not in (1,4) or (len(parts)==4 and parts[3] not in ('saldos','todos','movimientos')):raise ValueError('Vista del período de inventario inválida')
        today=date.today();start,end,mode=(parts[1:4] if len(parts)==4 else (today.replace(day=1).isoformat(),today.isoformat(),'saldos'))
        view=period(budget,start,end,mode=='todos')
        return (MOVEMENT_HEADERS,view['movements']) if mode=='movimientos' else (PERIOD_HEADERS,view['rows'])
    if kind=='inventario' or kind.startswith('inventario:'):
        from datetime import date
        from .inventory_control import snapshot,HEADERS,MOVEMENT_HEADERS
        parts=kind.split(':')
        if len(parts) not in (1,3) or (len(parts)==3 and parts[2] not in ('saldos','todos','movimientos')):raise ValueError('Vista de inventario inválida')
        view=snapshot(budget,parts[1] if len(parts)==3 else date.today().isoformat(),len(parts)==3 and parts[2]=='todos')
        return (MOVEMENT_HEADERS,view['movements']) if len(parts)==3 and parts[2]=='movimientos' else (HEADERS,view['rows'])
    if kind=='no_conformidades' or kind.startswith('no_conformidades:'):
        from .nonconformities import HEADERS,report_rows
        parts=kind.split(':')
        if len(parts) not in (1,3) or (len(parts)==3 and (parts[1] not in ('vigentes','anulados') or parts[2] not in ('pendientes','todas'))):raise ValueError('Filtro de no conformidades inválido')
        return HEADERS,report_rows(budget,len(parts)==3 and parts[1]=='anulados',len(parts)==3 and parts[2]=='pendientes')
    if kind=='lineas_base':
        from .budget_baselines import BASE_HEADERS,overview
        return BASE_HEADERS,overview(budget)
    if kind.startswith('comparacion_base:'):
        from .budget_baselines import HEADERS,comparison
        parts=kind.split(':')
        if len(parts) not in (2,3) or (len(parts)==3 and parts[2]!='cambios'):raise ValueError('Vista de línea base inválida')
        return HEADERS,comparison(budget,parts[1],len(parts)==3)['rows']
    if kind=='rendimientos' or kind.startswith('rendimientos:'):
        from datetime import date
        from .productivity import snapshot,WORK_HEADERS,RESOURCE_HEADERS,UNASSIGNED_HEADERS
        parts=kind.split(':')
        if len(parts) not in (1,4) or (len(parts)==4 and parts[3] not in ('partidas','recursos','sin_asignar')):raise ValueError('Vista de rendimientos inválida')
        view=snapshot(budget,parts[1] if len(parts)==4 else '0001-01-01',parts[2] if len(parts)==4 else date.today().isoformat())
        target=parts[3] if len(parts)==4 else 'partidas'
        return (WORK_HEADERS,view['work_items']) if target=='partidas' else (RESOURCE_HEADERS,view['resources']) if target=='recursos' else (UNASSIGNED_HEADERS,view['unassigned'])
    if kind in ('calidad_controles','calidad_comprobaciones'):
        from .quality_control import HEADERS,DETAIL_HEADERS,report_rows,detail_rows
        return (HEADERS,report_rows(budget)) if kind=='calidad_controles' else (DETAIL_HEADERS,detail_rows(budget))
    if kind=='incidencias_historial':
        from .site_issues import EVENT_HEADERS,event_rows
        return EVENT_HEADERS,event_rows(budget)
    if kind=='incidencias' or kind.startswith('incidencias:'):
        from datetime import date
        from .site_issues import HEADERS,report_rows
        parts=kind.split(':')
        if len(parts) not in (1,3) or (len(parts)==3 and parts[2] not in ('todas','pendientes','vencidas')):raise ValueError('Filtro de incidencias inválido')
        return HEADERS,report_rows(budget,parts[1] if len(parts)==3 else date.today().isoformat(),len(parts)==3 and parts[2]=='pendientes',len(parts)==3 and parts[2]=='vencidas')
    if kind=='horas_recursos' or kind.startswith('horas_recursos:'):
        from . import resource_hours
        parts=kind.split(':')
        if len(parts)==1:return resource_hours.HEADERS,resource_hours.report_rows(budget)
        if len(parts)!=3 or parts[2] not in ('recursos','partidas'):raise ValueError('Vista de horas inválida')
        view=resource_hours.snapshot(budget,parts[1])
        return (resource_hours.RESOURCE_HEADERS,view['resources']) if parts[2]=='recursos' else (resource_hours.WORK_HEADERS,view['work_items'])
    if kind=='partes_obra':
        from .production import HEADERS,report_rows
        return HEADERS,report_rows(budget)
    if kind=='seguimiento_compras' or kind.startswith('seguimiento_compras:'):
        from datetime import date
        from .procurement_tracking import snapshot,order_rows,delivery_rows,ORDER_HEADERS,DELIVERY_HEADERS,LINK_HEADERS
        parts=kind.split(':')
        if len(parts)>4 or (len(parts)>2 and parts[2] not in ('pedidos','albaranes','trazabilidad')) or (len(parts)>3 and (parts[3]!='pendientes' or parts[2]=='trazabilidad')):raise ValueError('Informe de seguimiento inválido')
        view=snapshot(budget,parts[1] if len(parts)>1 else date.today().isoformat());target=parts[2] if len(parts)>2 else 'pedidos'
        if target=='trazabilidad':return LINK_HEADERS,view['links']
        return (ORDER_HEADERS,order_rows(view,len(parts)>3)) if target=='pedidos' else (DELIVERY_HEADERS,delivery_rows(view,len(parts)>3))
    if kind=='control_economico' or kind.startswith('control_economico:'):
        from datetime import date
        from .cost_control import snapshot,summary_rows,concept_rows,document_rows,SUMMARY_HEADERS,CONCEPT_HEADERS,DOCUMENT_HEADERS
        parts=kind.split(':')
        if len(parts)>3 or (len(parts)==3 and parts[2] not in ('conceptos','documentos')):raise ValueError('Informe de control económico inválido')
        view=snapshot(budget,parts[1] if len(parts)>1 else date.today().isoformat())
        if len(parts)==3:
            return (CONCEPT_HEADERS,concept_rows(view)) if parts[2]=='conceptos' else (DOCUMENT_HEADERS,document_rows(view))
        return SUMMARY_HEADERS,summary_rows(view)
    if kind=='antiguedad' or kind.startswith('antiguedad:'):
        from datetime import date
        from .receivables_aging import snapshot,HEADERS,DETAIL_HEADERS
        parts=kind.split(':')
        if len(parts) not in (1,3,4) or (len(parts)>1 and parts[2] not in ('resumen','detalle')) or (len(parts)==4 and parts[3]!='+proformas'):raise ValueError('Informe de antigüedad inválido')
        view=snapshot(budget,parts[1] if len(parts)>1 else date.today().isoformat(),len(parts)==4)
        return (DETAIL_HEADERS,view['details']) if len(parts)>1 and parts[2]=='detalle' else (HEADERS,view['rows'])
    if kind=='tesoreria' or kind.startswith('tesoreria:'):
        from datetime import date
        from .treasury import snapshot,month_rows
        parts=kind.split(':')
        if len(parts)>3 or (len(parts)==3 and parts[2]!='+proformas'):raise ValueError('Informe de tesorería inválido')
        cut=parts[1] if len(parts)>1 else date.today().isoformat()
        return ('Mes','Cobros registrados','Pagos registrados','Neto registrado','Entradas previstas conocidas','Salidas previstas conocidas','Neto previsto conocido','Revisiones pendientes'),month_rows(snapshot(budget,cut,len(parts)==3))
    if kind=='entidades':
        from .entities import report_rows
        return ('ID','Código','Nombre','Tipo','Contacto','Teléfono','Correo','NIF','Dirección','Localidad','Código postal','Provincia','Otro teléfono','Fax','Titulación','Colegio','Colegiado','Nota'),report_rows(budget)
    if kind=='pzh_control_records':
        from .pzh_native_modules import record_rows
        return ('ID','ID origen','Referencia','Entidad','Fecha','Estado','Nota'),record_rows(budget)
    if kind=='pzh_conversion':
        from .pzh_native_modules import results
        return ('Módulo','ID de origen','Resultado','Detalle'),[(r['module'],r['item'],'Disponible' if r['status']=='available' else 'Pendiente',r['detail']) for r in results(budget)]
    if kind.startswith('issued_'):
        from .issued_management import document_rows, source_rows, validate
        data=validate(budget)
        if kind=='issued_documents':
            kinds={'order':'Pedido','delivery':'Albarán','invoice':'Factura','proforma':'Proforma'};states={'draft':'Borrador','posted':'Confirmado','cancelled':'Cancelado'}
            return ('ID','Tipo','Referencia','Cliente','Fecha','Estado','Base','Impuesto','Retención','Total neto','Cobros fechados','Apertura aceptada','Saldo nativo','Cobrado en origen','Revisión'),[(r[0],kinds[r[1]],r[2],r[3],r[4],states[r[5]],*r[6:]) for r in document_rows(budget)]
        if kind=='issued_source':return ('ID origen','Referencia','Fecha','Proforma','Base','Conversión disponible'),source_rows(budget)
        if kind=='issued_customers':return ('ID','Cliente','Contacto'),[(r['id'],r['name'],r['contact']) for r in data['customers']]
        if kind=='issued_receipts':return ('ID','Documento','Fecha real','Importe','Referencia'),[(r['id'],r['document_id'],r['date'],r['amount'],r['reference']) for r in data['receipts']]
        if kind=='issued_dues':return ('Documento','Fecha origen','Tipo','Pagado en origen','Importe','Nota'),[(rid,d['date'] or '',d['kind'],d['paid'],d['amount'],d['note']) for rid,source in data['source_states'].items() for d in source['dues']]
        raise ValueError('Informe de gestión emitida desconocido')
    if kind=='pzh_unresolved':
        import json
        references=json.loads(budget.project_metadata.get('pzh_unresolved_relations','[]'))
        measurements=json.loads(budget.project_metadata.get('pzh_unresolved_measurements','[]'))
        return ('ID origen','Superior','Inferior','Cantidad original','Mediciones conservadas'),[(row['id'],row['parent'],row['child'],row['fields'].get('14',''),sum(m['relation'][:2]==[row['parent'],row['child']] for m in measurements)) for row in references]
    if kind=='valor_ganado':
        from .earned_value import report_rows
        return ('Fase','Fecha','BAC','PV','EV','AC','CV','SV','CPI','SPI','EAC · CPI','EAC · resto al coste base','EAC · CPI×SPI','ETC · CPI','VAC · CPI','TCPI · BAC','Producción informada','Coste informado'),report_rows(budget)
    calculator = calculator_for(budget)
    if kind=='plan_fases_actividades':
        from .planning_phases import activity_rows
        return ('Relación','Capítulo','Partida','Inicio','Final','Cantidad objetivo','Precio objetivo','Coste objetivo','Cantidad total repartida','Precio plan','Coste repartido','Cantidad aprobada','Cantidad global de origen','Precedentes'),activity_rows(budget)
    if kind=='plan_fases_reparto':
        from .planning_phases import phase_rows
        return ('Capítulo','Partida','Fase','Final del periodo','Cantidad','Acumulado','Precio plan','Coste de fase'),phase_rows(budget)
    if kind=='calendario_pagos':
        from .management_schedule import due_rows
        return ('Documento','Factura','Vencimiento','Tipo','Importe programado','Nota'),[(r[0],r[1],r[2],{'normal':'Normal','guarantee':'Garantía','fiscal':'Fiscal'}[r[3]],r[4],r[5]) for r in due_rows(budget)]
    if kind=='saldos_apertura':
        from .management_schedule import opening_rows
        return ('Documento','Factura','Pagado en origen sin fecha','Inicio seguimiento','Liquidado de apertura','Revisión'),opening_rows(budget)
    if kind=='ofertas':
        from .management import offer_rows
        return ('Contrato','Proveedor','Suministros sin precio','Importe con precios disponibles','Adjudicatario','Importe adjudicado'),offer_rows(budget)
    if kind=='pzh_native_contracts':
        from .pzh_native_management import contract_rows
        return ('ID origen','Referencia','Entidad ofertante','Contrato','Ofertas','Adjudicatario','Importe adjudicado','Estado de conversión'),contract_rows(budget)
    if kind=='pzh_native_documents':
        from .pzh_native_management import rows
        return ('ID origen','Referencia','Entidad','Base del borrador','Estado de conversión'),rows(budget)
    if kind.startswith('pzh_'):
        from .pzh_operations import table
        return table(budget,kind)
    if kind=='ruta_critica':
        from .planning_advanced import schedule
        return ('Relación','Inicio','Final','Inicio tardío','Final tardío','Holgura','Crítica','Cantidad objetivo','Precio objetivo','Importe objetivo'),[(r['relation_id'],r['start'],r['finish'],r['latest_start'],r['latest_finish'],r['slack'],r['critical'],r['quantity'],r['price'],r['amount']) for r in schedule(budget)]
    if kind=='pagos_saldos':
        from .management_advanced import settlement_rows
        return ('Documento','Tipo','Referencia','Proveedor','Próximo vencimiento','A pagar','Liquidado con apertura','Pendiente','Vencido'),[tuple('Revisar apertura' if value is None and i in (6,7) else '' if value is None else value for i,value in enumerate(row)) for row in settlement_rows(budget)]
    if kind in ('planificacion','recursos'):
        from .planning import task_rows, resources
        return (('Capítulo','Partida','Inicio','Final','Mes','Días laborales','Cantidad','Importe estimado'), task_rows(budget)) if kind=='planificacion' else (('Mes','Recurso','Unidad','Cantidad'),resources(budget))
    if kind in ('gestion','existencias','vencimientos'):
        from .management import document_rows, ledger, cash_rows
        if kind=='gestion':return ('Identificador','Tipo','Referencia','Fecha','Proveedor','Estado','Base','Impuesto','Retención','Total'),document_rows(budget)
        if kind=='existencias':return ('Fecha','Recurso','Movimiento','Origen / destino','Cantidad','Valor','Existencias','Valor restante'),ledger(budget)
        return ('Vencimiento','Tipo','Referencia','Importe previsto'),cash_rows(budget)
    if kind=='certificaciones':
        from .certification_phases import project_phases
        from .certifications import CertificationAtOrigin
        view=project_phases(budget);eligible=CertificationAtOrigin(budget,{})
        rows=[]
        for relation in budget.relations:
            try:eligible._eligible(relation.id)
            except ValueError:continue
            value=view.relation(relation.id) if view else CertificationAtOrigin(budget,budget.certified_quantities).relation(relation.id)
            quantity=value.cumulative_quantity if view else value.quantity
            amount=value.cumulative_amount if view else value.amount
            rows.append((relation.parent_code,relation.child_code,quantity,value.unit_price,amount))
        return ('Capítulo','Partida','Cantidad aprobada','Precio certificado','Importe aprobado'),rows
    if kind == 'precios':
        return ('Código', 'Unidad', 'Resumen', 'Precio'), [
            (c.code, c.unit, c.summary, str(calculator.price(c.code)))
            for c in sorted(budget.concepts.values(), key=lambda c: c.code)]
    if kind == 'mediciones':
        from .measurement_operations import native_displays
        displays = native_displays(budget)
        native = {}
        for line in budget.measurements:
            native.setdefault(line.relation_id, []).append(line)
        rows = []
        for relation in budget.relations:
            label = relation.parent_code + ' → ' + relation.child_code
            if relation.id in budget.bc3_measurements:
                for line in budget.bc3_measurements[relation.id].lines:
                    subtotal = line.kind in ('1','2')
                    rows.append((label,line.description,line.a,line.b,line.c,line.d,
                        line.description if line.kind == '3' else line.applied_formula,
                        '' if subtotal else str(line.partial), str(line.partial) if subtotal else '', line.kind))
            else:
                for line in native.get(relation.id, ()):
                    partial,subtotal,kind = displays[line.id]
                    rows.append((label,line.comment,str(line.n_lines),
                        '' if line.length is None else str(line.length),
                        '' if line.width is None else str(line.width),
                        '' if line.height is None else str(line.height),line.formula,str(partial),str(subtotal),kind))
        return ('Relación','Comentario','N','Longitud','Anchura','Altura','Fórmula','Parcial','Subtotal','Tipo'), rows
    if kind == 'economico':
        from .economic_summary import economic_summary
        return ('Concepto', 'Importe'), economic_summary(budget)
    rows = budget_rows(budget)
    if kind == 'resumen':
        rows = [row for row in rows if row[0] == 0]
    return ('Nivel', 'Código', 'Unidad', 'Resumen', 'Cantidad', 'Precio', 'Importe'), rows


def report_html(budget, kind='presupuesto'):
    headers, rows = report_table(budget, kind)
    total=str(calculator_for(budget).total()) if budget.root_code is not None else 'Sin raíz presupuestaria'
    text_style='td{white-space:pre-wrap;overflow-wrap:anywhere}' if kind=='documentos_tecnicos_contenido' else ''
    cells = lambda values, tag: ''.join(f'<{tag}>{escape(str(value))}</{tag}>' for value in values)
    return ('<!DOCTYPE html><html><head><meta charset="utf-8"><style>'
            'body{font-family:sans-serif}table{border-collapse:collapse;width:100%}'
            'td,th{border:1px solid #aaa;padding:5px;text-align:left}'
            + text_style + '</style></head><body><h1>OpenPresto · ' + escape(kind) + '</h1><table><tr>'
            + cells(headers, 'th') + '</tr>'
            + ''.join('<tr>' + cells(row, 'td') + '</tr>' for row in rows)
            + '</table><p>Proyecto: ' + escape(budget.project_metadata.get('title', ''))
            + '</p><p>Total del presupuesto: '
            + escape(total) + '</p></body></html>')


def report_csv(budget, kind='presupuesto', delimiter=';'):
    headers, rows = report_table(budget, kind)
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, delimiter=delimiter)
    def safe(value):
        text = str(value)
        return "'" + text if text.startswith(('=', '+', '-', '@', '\t', '\r')) else text
    writer.writerow(headers)
    writer.writerows([safe(value) for value in row] for row in rows)
    return stream.getvalue()
