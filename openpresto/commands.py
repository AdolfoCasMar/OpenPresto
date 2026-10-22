"""Public application command catalogue, independent from Qt and transport.

Handlers work on a private project. Validation and round-trip must succeed
before a result is returned, so every client gets the same atomic behaviour.
"""
from dataclasses import dataclass
from importlib import import_module
from inspect import signature
from .budget import BudgetError
from .history_snapshots import capture_snapshot as dumps, restore_snapshot as loads


@dataclass(frozen=True)
class CommandSpec:
    id: str
    label: str
    section: str
    module: str
    handler: str

    def describe(self):
        function = getattr(import_module('.' + self.module, __package__), self.handler)
        parameters = list(signature(function).parameters.values())[1:]
        return {'id':self.id, 'label':self.label, 'section':self.section,
                'parameters':[{'name':p.name, 'required':p.default is p.empty} for p in parameters]}


COMMANDS = (
    CommandSpec('assets.richtext.set','Editar texto con formato','Gestión','project_assets','set_rich_text'),
    CommandSpec('budget.phases.line.link','Vincular línea de fase','Presupuesto','budget_phase_measurements','link_line'),
    CommandSpec('retention.settlement.record','Registrar liquidación de retención','Gestión','retention_settlements','record'),
    CommandSpec('retention.settlement.cancel','Anular liquidación de retención','Gestión','retention_settlements','cancel'),
    CommandSpec('agenda.copy_pzh','Copiar agenda PZH','Planificación','agenda','copy_source'),
    CommandSpec('agenda.day.set','Editar día de agenda','Planificación','agenda','set_day'),
    CommandSpec('agenda.holidays.add','Añadir festivos al plan','Planificación','agenda','add_holidays_to_plan'),
    CommandSpec('assets.copy_pzh','Copiar índice de adjuntos PZH','Gestión','project_assets','copy_source'),
    CommandSpec('assets.set','Editar adjunto','Gestión','project_assets','set_asset'),
    CommandSpec('concept.keywords.set','Editar términos de búsqueda','Presupuesto','concept_keywords','set_terms'),
    CommandSpec('concept.keywords.copy_pzh','Copiar términos PZH','Presupuesto','concept_keywords','copy_source'),
    CommandSpec('management.retention.opening.set','Revisar apertura de retenciones','Gestión','retention_openings','set_opening'),
    CommandSpec('management.retention.opening.clear','Retirar revisión de retenciones','Gestión','retention_openings','clear_opening'),
    CommandSpec('budget.phases.copy_pzh','Copiar mediciones por fases','Presupuesto','budget_phase_measurements','copy_source'),
    CommandSpec('budget.phases.line.edit','Editar medición de fase','Presupuesto','budget_phase_measurements','edit_line'),
    CommandSpec('budget.phases.clear','Retirar copia de fases','Presupuesto','budget_phase_measurements','clear_copy'),
    CommandSpec('budget.phases.apply','Aplicar mediciones por fases','Presupuesto','budget_phase_measurements','apply_through'),
    CommandSpec('technical.document.set','Documento técnico','Gestión','technical_documents','set_document'),
    CommandSpec('technical.document.attach_original','Conservar documento PZH original','Gestión','technical_documents','attach_original'),
    CommandSpec('technical.document.copy_pzh','Copiar texto de entidad PZH','Gestión','technical_documents','copy_source'),
    CommandSpec('technical.document.remove','Retirar documento técnico','Gestión','technical_documents','remove_document'),
    CommandSpec('quality.issue.create','Incidencia desde no conformidad','Gestión','nonconformities','create_issue'),
    CommandSpec('budget.baseline.freeze','Guardar línea base','Presupuesto','budget_baselines','freeze'),
    CommandSpec('budget.baseline.remove','Retirar línea base','Presupuesto','budget_baselines','remove'),
    CommandSpec('quality.inspection.set','Control de calidad','Gestión','quality_control','set_inspection'),
    CommandSpec('quality.inspection.status','Revisar o anular control','Gestión','quality_control','set_status'),
    CommandSpec('site.issue.set','Incidencia de obra','Gestión','site_issues','set_issue'),
    CommandSpec('site.issue.status','Estado de incidencia','Gestión','site_issues','set_status'),
    CommandSpec('resource.hours.set','Horas de recurso','Gestión','resource_hours','set_entry'),
    CommandSpec('resource.hours.status','Confirmar o anular horas','Gestión','resource_hours','set_status'),
    CommandSpec('production.report.set','Parte de obra','Gestión','production','set_report'),
    CommandSpec('production.report.status','Confirmar o anular parte','Gestión','production','set_status'),
    CommandSpec('entities.set','Entidad y datos de contacto','Gestión','entities','set_entity'),
    CommandSpec('pzh.entities.copy','Copiar entidades PZH','Gestión','entities','copy_pzh'),
    CommandSpec('pzh.record.copy','Copiar registro de control','Gestión','pzh_native_modules','copy_record'),
    CommandSpec('pzh.record.set','Editar estado y nota de control','Gestión','pzh_native_modules','set_record'),
    CommandSpec('pzh.native.convert','Crear copias editables PZH','Importación','pzh_native_modules','convert_project'),
    CommandSpec('issued.customer.set','Cliente','Gestión emitida','issued_management','set_customer'),
    CommandSpec('issued.document.set','Documento emitido','Gestión emitida','issued_management','set_document'),
    CommandSpec('issued.document.status','Estado de documento emitido','Gestión emitida','issued_management','set_status'),
    CommandSpec('issued.receipt.record','Registrar cobro','Gestión emitida','issued_management','record_receipt'),
    CommandSpec('issued.receipt.cancel','Anular cobro','Gestión emitida','issued_management','cancel_receipt'),
    CommandSpec('issued.opening.cancel','Retirar apertura de cobros','Gestión emitida','issued_management','cancel_opening'),
    CommandSpec('issued.opening.accept','Aceptar apertura de cobros','Gestión emitida','issued_management','accept_opening'),
    CommandSpec('issued.retention.opening.set','Revisar retenciones emitidas','Gestión emitida','issued_retention_openings','set_opening'),
    CommandSpec('issued.retention.opening.clear','Retirar revisión de retenciones emitidas','Gestión emitida','issued_retention_openings','clear_opening'),
    CommandSpec('pzh.issued.copy','Copiar documento PZH emitido','Gestión emitida','issued_management','copy_source'),
    CommandSpec('earned_value.baseline.freeze','Congelar línea base desde plan por fases','Control económico','earned_value','freeze_phases'),
    CommandSpec('earned_value.progress.set','Producción y coste real acumulados','Control económico','earned_value','set_progress'),
    CommandSpec('earned_value.period.set','Revisar periodo de control completo','Control económico','earned_value','set_period'),
    CommandSpec('planning.phases.copy_pzh','Copiar planificación PZH a fases editables','Planificación','planning_phases','copy_pzh'),
    CommandSpec('planning.phases.configure','Calendario y aprobación del plan','Planificación','planning_phases','configure'),
    CommandSpec('planning.phases.task.set','Actividad, objetivo y cantidades por fase','Planificación','planning_phases','set_task'),
    CommandSpec('management.schedule.set','Calendario de vencimientos','Gestión','management_schedule','set_schedule'),
    CommandSpec('management.opening.set','Saldo de apertura','Gestión','management_schedule','set_opening'),
    CommandSpec('pzh.management.dues.copy','Copiar vencimientos PZH','Gestión','pzh_native_management','copy_dues'),
    CommandSpec('pzh.management.contract.copy','Copiar contrato y ofertas PZH','Gestión','pzh_native_management','copy_contract'),
    CommandSpec('pzh.management.document.copy','Copiar documento PZH a borrador','Gestión','pzh_native_management','copy_document'),
    CommandSpec('pzh.operations.convert','Convertir planificación y gestión del PZH conservado','Proyecto','pzh_operations','convert_archived'),
    CommandSpec('budget.concept.add','Añadir concepto','Presupuesto','budget_editing','add_concept'),
    CommandSpec('budget.concept.edit','Editar concepto','Presupuesto','budget_editing','edit_concept'),
    CommandSpec('budget.relation.add','Insertar relación','Presupuesto','budget_editing','add_relation'),
    CommandSpec('budget.relation.edit','Editar relación','Presupuesto','budget_editing','edit_relation'),
    CommandSpec('budget.measurement.replace','Editar línea completa','Mediciones','budget_editing','replace_measurement'),
    CommandSpec('budget.measurement.add','Añadir medición','Mediciones','budget_editing','add_measurement'),
    CommandSpec('budget.measurement.edit','Editar medición','Mediciones','budget_editing','edit_measurement'),
    CommandSpec('budget.measurement.bc3.edit','Editar medición BC3','Mediciones','budget_editing','edit_bc3_measurement'),
    CommandSpec('budget.measurement.move','Mover línea','Mediciones','budget_editing','move_measurement'),
    CommandSpec('budget.measurement.subtotal','Añadir subtotal','Mediciones','measurement_operations','insert_subtotal'),
    CommandSpec('budget.measurement.remove','Eliminar líneas','Mediciones','measurement_operations','remove_lines'),
    CommandSpec('budget.measurement.copy','Copiar mediciones','Mediciones','editing_services','copy_measurements'),
    CommandSpec('budget.text.replace','Reemplazar texto','Presupuesto','editing_services','replace_text'),
    CommandSpec('budget.children.reorder','Ordenar nivel','Presupuesto','editing_services','reorder_children'),
    CommandSpec('budget.relation.move','Mover relación','Presupuesto','hierarchy_services','move_relation'),
    CommandSpec('budget.concept.duplicate','Duplicar concepto','Presupuesto','hierarchy_services','duplicate_concept'),
    CommandSpec('budget.price.lock','Bloquear o desbloquear precio','Presupuesto','budget_editing','set_locked_price'),
    CommandSpec('budget.price.scale','Multiplicar precios','Presupuesto','budget_editing','scale_prices'),
    CommandSpec('budget.price.adjust','Ajustar precio','Presupuesto','budget_editing','adjust_price'),
    CommandSpec('budget.engine.set','Cambiar motor','Presupuesto','budget_editing','set_engine'),
    CommandSpec('budget.precision.set','Precisión económica','Presupuesto','budget_editing','set_precision'),
    CommandSpec('budget.root.precision.set','Precisión raíz','Presupuesto','budget_editing','set_root_precision'),
    CommandSpec('budget.indirect.set','Costes indirectos','Presupuesto','budget_editing','set_indirect_costs'),
    CommandSpec('budget.summary.set','Resumen financiero','Presupuesto','budget_editing','set_summary_rates'),
    CommandSpec('budget.relation.replace','Editar relación completa','Presupuesto','budget_editing','replace_relation'),
    CommandSpec('budget.concept.replace','Editar concepto completo','Presupuesto','budget_editing','replace_concept'),
    CommandSpec('budget.measurement.bc3.replace','Editar línea BC3','Presupuesto','budget_editing','replace_bc3_line'),
    CommandSpec('budget.relations.remove','Eliminar relaciones','Presupuesto','hierarchy_services','remove_relations'),
    CommandSpec('budget.concepts.remove','Eliminar conceptos sin uso','Presupuesto','hierarchy_services','remove_unused_concepts'),
    CommandSpec('budget.concepts.edit','Editar selección','Proyecto','budget_editing','edit_many_concepts'),
    CommandSpec('project.properties.set','Propiedades de obra','Proyecto','budget_editing','set_project_properties'),
    CommandSpec('project.document.attach','Vincular documento','Proyecto','budget_editing','attach_document'),
    CommandSpec('project.document.remove','Retirar vínculo','Proyecto','budget_editing','remove_document'),
    CommandSpec('planning.advanced.configure','Inicio del plan avanzado','Planificación','planning_advanced','configure'),
    CommandSpec('planning.advanced.task.set','Actividad, objetivo y precedencias','Planificación','planning_advanced','set_task'),
    CommandSpec('planning.advanced.task.remove','Retirar actividad avanzada','Planificación','planning_advanced','remove_task'),
    CommandSpec('management.payment.record','Registrar pago','Gestión','management_advanced','record_payment_command'),
    CommandSpec('management.payment.cancel','Anular pago','Gestión','management_advanced','cancel_payment'),
    CommandSpec('planning.calendar.set','Calendario laboral','Planificación','planning','configure_calendar'),
    CommandSpec('planning.task.set','Programar partida','Planificación','planning','set_task'),
    CommandSpec('planning.task.remove','Retirar actividad','Planificación','planning','remove_task'),
    CommandSpec('management.supplier.set','Proveedor','Gestión','management','set_supplier'),
    CommandSpec('management.contract.set','Contrato','Gestión','management','set_contract'),
    CommandSpec('management.offer.set','Oferta','Gestión','management','set_offer'),
    CommandSpec('management.contract.award','Adjudicar','Gestión','management','award_contract'),
    CommandSpec('management.document.set','Documento','Gestión','management','set_document'),
    CommandSpec('management.document.status','Confirmar o cancelar documento','Gestión','management','set_document_status'),
    CommandSpec('management.consumption.add','Consumo','Gestión','management','consume'),
    CommandSpec('certification.schedule.set','Calendario y aprobación','Certificaciones','certification_editing','set_schedule'),
    CommandSpec('certification.price.set','Precio certificado','Certificaciones','certification_editing','set_price'),
    CommandSpec('certification.phase.quantity.set','Cantidad de periodo','Certificaciones','certification_editing','set_phase_quantity'),
    CommandSpec('certification.origin.quantity.set','Cantidad a origen','Certificaciones','certification_editing','set_origin_quantity'),
    CommandSpec('certification.lines.replace','Líneas de periodo','Certificaciones','certification_editing','replace_lines'),
)
_INDEX = {spec.id: spec for spec in COMMANDS}


def catalogue():
    return [spec.describe() for spec in COMMANDS]


def execute(budget, command, params=None):
    if not isinstance(command, str) or command not in _INDEX:
        raise BudgetError('Comando desconocido: ' + str(command))
    if params is None:
        params = {}
    if not isinstance(params, dict) or any(not isinstance(k,str) for k in params):
        raise BudgetError('Los parámetros del comando deben ser un objeto JSON')
    spec = _INDEX[command]
    function = getattr(import_module('.' + spec.module, __package__), spec.handler)
    try:
        signature(function).bind(None, **params)
    except TypeError as exc:
        raise BudgetError('Parámetros incorrectos de ' + command + ': ' + str(exc)) from exc
    candidate = loads(dumps(budget))
    try:
        result = function(candidate, **params)
        candidate = candidate if result is None else result
        candidate = loads(dumps(candidate))
        from .calculations import calculator_for
        if candidate.root_code is not None:
            calculator_for(candidate).total()
        return candidate
    except (TypeError, KeyError, IndexError, AttributeError) as exc:
        raise BudgetError('Datos incorrectos de ' + command + ': ' + str(exc)) from exc


class ProjectSession:
    """Headless project history. The desktop uses its existing UI history."""
    def __init__(self, budget, history_limit=100):
        if type(history_limit) is not int or not 1 <= history_limit <= 1000:
            raise BudgetError('Límite de historial inválido')
        self.budget = loads(dumps(budget))
        self.history_limit = history_limit
        self._undo, self._redo = [], []

    def execute(self, command, params=None):
        before = dumps(self.budget)
        result = execute(self.budget, command, params)
        if dumps(result) != before:
            self._undo.append(before)
            self._undo = self._undo[-self.history_limit:]
            self._redo.clear()
            self.budget = result
        return self.budget

    def undo(self):
        if self._undo:
            self._redo.append(dumps(self.budget))
            self.budget = loads(self._undo.pop())
        return self.budget

    def redo(self):
        if self._redo:
            self._undo.append(dumps(self.budget))
            self.budget = loads(self._redo.pop())
        return self.budget
