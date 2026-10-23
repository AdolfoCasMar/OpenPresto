from .storage import economic_document
from .number_format import display, input_number
"""Ventanas MDI sobre el editor, historial y motor existentes."""
from dataclasses import replace
from pathlib import Path
from typing import NamedTuple

from PySide6.QtCore import Qt, QSignalBlocker, QTimer, QRect, QItemSelectionModel, QSize, QSettings
from PySide6.QtGui import QKeySequence, QColor, QIcon, QPalette
from PySide6.QtWidgets import (QApplication, QMdiArea, QMdiSubWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QPlainTextEdit,
    QTableWidgetItem, QAbstractItemView, QHeaderView, QToolBar, QMessageBox,
    QDialog, QStyleFactory, QInputDialog, QFileDialog, QMenu, QCheckBox, QStackedWidget, QComboBox, QToolButton)

from .editor import BudgetEditor, MeasurementDialog, RelationDialog, ConceptDialog
from .budget import Budget, BudgetError, BudgetRelation, BudgetMeasurement
from .calculations import calculator_for as BudgetCalculator
from .storage import to_dict, from_dict
from .bc3_measurements import rebuild_record
from .bc3_exporter import render_bc3, save_bc3, BC3ExportError
from .theme import LIGHT_STYLESHEET
from . import __version__
from .ui_icons import icon, action_icon, nature_icon
from .concept_appearance import style_code


class _ViewState(NamedTuple):
    parent: str | None
    concept: str | None
    relation: str | None
    origin: str
    navigation: tuple
    search: str
    measurement: tuple | None
    section: int
    pane: str | None
    management_tab: int


class WindowSelector:
    """Compatibilidad de API con pruebas/clientes 0.2; no crea pestañas."""
    def __init__(self, workspace):
        self.workspace = workspace

    def setCurrentWidget(self, widget):
        self.workspace.show_widget(widget)


class PrestoWorkspace(BudgetEditor):
    def __init__(self):
        self.project_open = False
        self._ready = False
        self._reference_layout = False
        self.window_snapping = QSettings().value('workspace/snap',True,type=bool)
        self._refreshing = False
        self.current_code = None
        self.active_concept = None
        self.selected_relation = None
        self._selection_origin = 'precios'
        self._navigation = []
        self._selection_override = None
        self._text_pending = False
        self._text_code = None
        super().__init__()
        self._prepare_workspace()
        self._ready = True
        from .session_services import install_recovery
        install_recovery(self)
        from .preferences import apply
        apply(self)
        self.refresh()

    def _prepare_workspace(self):
        self.resize(1320, 860)
        self.setWindowIcon(QIcon(str(Path(__file__).with_name('data')/'openpresto.svg')))
        from .mdi_windows import WorkspaceStyle
        self._mdi_style = WorkspaceStyle()
        # El estilo debe sobrevivir a todos los widgets que lo utilizan.
        self._mdi_style.setParent(QApplication.instance())
        self.setStyleSheet(LIGHT_STYLESHEET)
        old = self.takeCentralWidget()
        self.mdi = QMdiArea()
        self.mdi.setBackground(QColor('#e5e8ed'))
        self.mdi.setViewMode(QMdiArea.ViewMode.SubWindowView)
        self.setCentralWidget(self.mdi)
        self.windows = {}
        self.prices = self._table(('Código', 'Nc', 'Info', 'Ud', 'Resumen', 'CanPres', 'PrPres', 'ImpPres', 'Factor'))
        self.prices.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.prices.setEditTriggers(QAbstractItemView.EditTrigger.EditKeyPressed | QAbstractItemView.EditTrigger.DoubleClicked)
        self.prices.horizontalHeader().setStretchLastSection(False)
        self.prices.horizontalHeader().setSectionsMovable(True)
        self.prices.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        for col, width in ((0,100),(1,38),(2,38),(3,42),(5,85),(6,85),(7,95),(8,55)):
            self.prices.setColumnWidth(col, width)
        for visual,logical in enumerate((0,1,2,4,5,3,6,7,8)):
            self.prices.horizontalHeader().moveSection(self.prices.horizontalHeader().visualIndex(logical),visual)
        self.prices.setColumnHidden(2,True);self.prices.setColumnHidden(8,True)
        self.concepts_table.horizontalHeader().setStretchLastSection(False)
        self.concepts_table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch)
        for visual,logical in enumerate((0,3,2,1,4)):
            self.concepts_table.horizontalHeader().moveSection(self.concepts_table.horizontalHeader().visualIndex(logical),visual)
        for column,width in ((0,95),(1,42),(3,55),(4,90)):self.concepts_table.setColumnWidth(column,width)
        for column,label in ((1,'Ud'),(3,'Nat'),(4,'Pres')):self.concepts_table.horizontalHeaderItem(column).setText(label)
        from .concept_appearance import NatureIconDelegate
        self.concepts_table.setItemDelegateForColumn(3,NatureIconDelegate(self.concepts_table))
        self.prices.cellDoubleClicked.connect(self.enter_concept)
        self.prices.itemSelectionChanged.connect(self.select_price)
        self.prices.itemChanged.connect(self.edit_price_cell)
        self.prices.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.prices.customContextMenuRequested.connect(self.price_context_menu)
        price_header = self.prices.horizontalHeader()
        price_header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        price_header.customContextMenuRequested.connect(self.price_columns_context_menu)
        self.crumb = QLabel()
        self.search = QLineEdit()
        self.search.setPlaceholderText('Buscar código, sinónimo o resumen…')
        self.search.textChanged.connect(self.filter_prices)
        up = QPushButton('Superior')
        up.setIcon(icon('up'))
        up.setToolTip('Volver al concepto superior')
        up.clicked.connect(self.go_up)
        text = QPushButton('Texto 1')
        text.setIcon(icon('text'))
        text.clicked.connect(lambda: self.show_panel('texto'))
        measurement = QPushButton('Medición del presupuesto')
        measurement.setIcon(icon('measure'))
        measurement.clicked.connect(lambda: self.show_panel('mediciones'))
        for button in (up, text, measurement):
            button.setToolTip(button.toolTip() or button.text())
            button.setText('')
            button.setFixedWidth(28)
            button.setIconSize(QSize(16,16))
        self.prices_widget = QWidget()
        layout = QVBoxLayout(self.prices_widget)
        layout.setContentsMargins(0,0,0,0);layout.setSpacing(0)
        self.description.setParent(self.prices_widget);self.description.hide()
        self.crumb.setParent(self.prices_widget);self.crumb.hide()
        row = QHBoxLayout()
        row.setContentsMargins(3,2,3,2);row.setSpacing(3)
        for label,symbol,callback in (('Ir a raíz','tree',self.go_root),('Desplegar árbol','down',lambda:self.budget_structure.tree.expandAll()),('Plegar árbol','up',lambda:self.budget_structure.tree.collapseAll())):
            button=QToolButton();button.setIcon(icon(symbol));button.setToolTip(label);button.setIconSize(QSize(16,16));button.clicked.connect(callback);row.addWidget(button)
        row.addWidget(up)
        self.budget_view=QComboBox();self.budget_view.setObjectName('vista-presupuesto')
        for label,key in (('Árbol','arbol'),('Capítulos','capitulos'),('Capítulos y partidas','capitulos-partidas'),('Presupuesto · Precios','precios')):self.budget_view.addItem(label,key)
        self.budget_view.setMaximumWidth(150)
        row.addWidget(self.budget_view)
        phase=QComboBox();phase.addItem('Presupuesto');phase.setToolTip('Importes del presupuesto');phase.setMaximumWidth(220);row.addWidget(phase,1)
        self.search.setPlaceholderText('Buscar…');self.search.setMaximumWidth(160)
        for widget in (text,measurement):
            row.addWidget(widget)
        for label,symbol,target in (('Archivos','attachments','gestion:technical_documents:assets'),('Relaciones','link','relaciones'),('Fechas e importes','phases','planificacion:6')):
            button=QToolButton();button.setIcon(icon(symbol));button.setToolTip(label);button.setIconSize(QSize(16,16));button.clicked.connect(lambda checked=False,target=target:self.section_ui.ribbon.show_view(target));row.addWidget(button)
        row.addStretch();row.addWidget(self.search)
        layout.addLayout(row)
        self.budget_stack=QStackedWidget();self.budget_stack.addWidget(self.prices)
        from .budget_views import BudgetStructureView
        self.budget_structure=BudgetStructureView(self,'arbol',embedded=True);self.budget_stack.addWidget(self.budget_structure);layout.addWidget(self.budget_stack)
        self.budget_stack.setCurrentWidget(self.budget_structure)
        self.budget_view.currentIndexChanged.connect(lambda _:self.set_budget_view(self.budget_view.currentData()))
        self.text_editor = QPlainTextEdit()
        self.text_editor.setPlaceholderText('Texto del concepto activo')
        self.text_editor.setUndoRedoEnabled(False)
        self.text_editor.textChanged.connect(self.queue_text)
        self._text_timer = QTimer(self)
        self._text_timer.setSingleShot(True)
        self._text_timer.setInterval(400)
        self._text_timer.timeout.connect(self.flush_text)
        self.import_notes = QPlainTextEdit()
        self.import_notes.setReadOnly(True)
        self.measurements_table.setColumnCount(10)
        self.measurements_table.setHorizontalHeaderLabels(('Comentario','N','Longitud','Anchura','Altura','Fórmula','Parcial','Subtotal','Tipo','Fase'))
        self.measurements_table.horizontalHeader().setStretchLastSection(False)
        self.measurements_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1,10):
            self.measurements_table.setColumnWidth(col, 86 if col < 8 else 70)
        self.measurements_table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed)
        self.measurements_table.itemChanged.connect(self.edit_measurement_cell)
        self.measurements_widget=QWidget();measurement_layout=QVBoxLayout(self.measurements_widget);measurement_layout.setContentsMargins(0,0,0,0);measurement_layout.setSpacing(0)
        measurement_bar=QHBoxLayout();measurement_bar.setContentsMargins(3,2,3,2)
        add_measurement=QToolButton();add_measurement.setIcon(icon('measure'));add_measurement.setToolTip('Añadir medición');add_measurement.clicked.connect(lambda:self.commands['Introducir medición…'][0].trigger());measurement_bar.addWidget(add_measurement)
        context=QComboBox();context.addItem('Datos generales');context.setMaximumWidth(220);measurement_bar.addWidget(context);measurement_bar.addStretch();measurement_layout.addLayout(measurement_bar);measurement_layout.addWidget(self.measurements_table)
        self.concepts_table.itemSelectionChanged.connect(self.select_concept)
        self.relations_table.itemSelectionChanged.connect(self.select_relation)
        self.certification_table = self._table(['Capítulo','Partida','Ud','CanPres','CanCert a origen','Precio','Importe certificado','Estado'])
        self.certification_table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed)
        self.certification_table.itemChanged.connect(self.edit_certification_cell)
        self.certification_table.setToolTip('Solo partidas con naturaleza explícita bajo capítulos. Cantidad acumulada, sin fases. Vacía CanCert para retirar el dato.')
        from .phase_editor import CertificationPhasePanel
        self.certification_phase_panel = CertificationPhasePanel(self)
        from .planning_panel import PlanningPanel
        from .management_panel import ManagementPanel
        from .reports_panel import ReportsPanel
        self.planning_panel = PlanningPanel(self)
        self.management_panel = ManagementPanel(self)
        self.reports_panel = ReportsPanel(self)
        self.panels = {
            'planificacion': ('Planificación', self.planning_panel),
            'gestion': ('Gestión · Compras y ejecución', self.management_panel),
            'informes': ('Informes', self.reports_panel),
            'precios': ('Precios · Presupuesto', self.prices_widget),
            'texto': ('Texto 1', self.text_editor),
            'mediciones': ('Medición del presupuesto', self.measurements_widget),
            'conceptos': ('Conceptos', self.concepts_table),
            'relaciones': ('Relaciones', self.relations_table),
            'avisos': ('Avisos de importación', self.import_notes),
            'certificacion': ('Certificación a origen', self.certification_table),
            'certificacion-fases': ('Certificación por fases', self.certification_phase_panel),
        }
        from .budget_views import BudgetStructureView
        for key,title in (('arbol','Árbol'),('capitulos','Capítulos'),('capitulos-partidas','Capítulos y partidas')):
            self.panels[key]=(title,BudgetStructureView(self,key))
        for _, widget in self.panels.values():
            widget.setParent(self)
            widget.hide()
        old.deleteLater()
        self.bottom_tabs = WindowSelector(self)
        self._build_menus()
        from .section_workspace import SectionWorkspace
        self.section_ui = SectionWorkspace(self)
        self.mdi.subWindowActivated.connect(lambda _: self._sync_actions())
        QApplication.instance().focusChanged.connect(self._focus_changed)

    def _focus_changed(self,old,new):
        self._sync_actions()

    def _action(self, menu, label, callback=None, shortcut=None, key=None, requires_project=True):
        action = menu.addAction(label)
        action.setIcon(action_icon(label))
        action.setIconVisibleInMenu(True)
        action.setToolTip(label + (f' ({shortcut})' if shortcut else ''))
        action.setStatusTip(label)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        if callback is None:
            action.setEnabled(False)
            action.setVisible(False)
        else:
            action.triggered.connect(callback)
        self.commands[key or label] = (action, callback is not None, requires_project)
        return action

    def _build_menus(self):
        self.menuBar().clear()
        self.commands = {}
        self.menus = {name: self.menuBar().addMenu(name) for name in
            ('Archivo','Edición','Ver','Asistentes','Herramientas','Macros','Cálculos','Informes','Ventana','Internet','?')}
        a = self.menus['Archivo']
        self._action(a,'Nuevo',self.new_budget,'Ctrl+N',requires_project=False)
        self._action(a,'Abrir…',self.open_budget,'Ctrl+O',requires_project=False)
        self._action(a,'Cerrar',self.close_project)
        from .session_services import another_window, recent, recover, preferences, open_backup
        self._action(a,'Otra ventana de proyecto',lambda: another_window(self),requires_project=False)
        self._action(a,'Proyectos recientes…',lambda: recent(self),requires_project=False)
        self._action(a,'Recuperar proyecto…',lambda: recover(self),requires_project=False)
        self._action(a,'Abrir respaldo…',lambda: open_backup(self),requires_project=False)
        self._action(a,'Preferencias…',lambda: preferences(self),requires_project=False)
        self._action(a,'Ejemplo de planificación y gestión',self.open_modules_demo,requires_project=False)
        a.addSeparator()
        self._action(a,'Guardar',self.save,'Ctrl+S')
        self._action(a,'Guardar como…',self.save_as)
        from .project_properties import properties, attach_document, open_document, remove_document
        self._action(a,'Propiedades obra',lambda: properties(self))
        self._action(a,'Vincular documento…',lambda: attach_document(self))
        self._action(a,'Abrir documento vinculado…',lambda: open_document(self))
        self._action(a,'Retirar vínculo documental…',lambda: remove_document(self))
        from .project_bundle import choose_bundle
        self._action(a,'Proyecto con documentos…',lambda: choose_bundle(self))
        imp = a.addMenu('Importar')
        self._action(imp,'FIEBDC / BC3…',self.import_budget,key='importar',requires_project=False)
        self._action(imp,'Presto PZH · experimental…',self.import_pzh_budget,requires_project=False)
        self._action(imp,'BC3 · perfil contrastado Presto 8.8…',self.import_observed_profile,
                     key='importar-perfil88',requires_project=False)
        self._action(imp,'BC3 · motor nativo…',self.import_native_profile,requires_project=False)
        exp = a.addMenu('Exportar')
        self._action(exp,'FIEBDC / BC3…',self.export_budget,key='exportar')
        a.addSeparator()
        self._action(a,'Salir',QApplication.closeAllWindows,'Ctrl+Q',requires_project=False)
        e = self.menus['Edición']
        self._action(e,'Deshacer',self.undo,'Ctrl+Z')
        self._action(e,'Deshacer especial')
        self._action(e,'Rehacer',self.redo,'Ctrl+Y')
        e.addSeparator()
        from .clipboard_services import copy, paste
        self._action(e,'Cortar',lambda: copy(self,True),'Ctrl+X')
        self._action(e,'Copiar',lambda: copy(self),'Ctrl+C')
        self._action(e,'Pegar',lambda: paste(self),'Ctrl+V')
        self._action(e,'Eliminar',self.delete_selected,'Delete')
        self._action(e,'Editar selección…',self.edit_selected,'F2')
        e.addSeparator()
        self._action(e,'Añadir concepto…',self.add_concept)
        self._action(e,'Insertar relación…',self.add_relation)
        self._action(e,'Introducir medición…',self.add_measurement)
        self._action(e,'Añadir subtotal parcial',lambda: self.add_measurement_subtotal(False))
        self._action(e,'Añadir subtotal acumulado',lambda: self.add_measurement_subtotal(True))
        self._action(e,'Subir línea de medición',lambda: self.move_measurement_line(-1))
        self._action(e,'Bajar línea de medición',lambda: self.move_measurement_line(1))
        e.addSeparator()
        self._action(e,'Buscar',lambda: (self.show_panel('precios'),self.search.setFocus()),'Ctrl+F')
        from .catalog_search import show_catalog
        self._action(e,'Buscar en toda la obra…',lambda: self._workspace_setting(show_catalog),'Ctrl+Shift+F')
        self._action(e,'Reemplazar',self.replace_project_text,'Ctrl+H')
        self._action(e,'Ordenar nivel…',self.sort_current_level)
        self._action(e,'Duplicar concepto…',self.duplicate_active_concept)
        from .bulk_editor import edit_selection
        self._action(e,'Editar conceptos seleccionados…',lambda: edit_selection(self))
        self._action(e,'Seleccionar todo',lambda: self._selected_table().selectAll() if self._selected_table() else None,'Ctrl+A')
        self._action(e,'Mover relación…',self.move_active_relation)
        self._action(e,'Copiar mediciones entre partidas…',self.copy_relation_measurements)
        self._action(e,'Ir a raíz',self.go_root)
        v = self.menus['Ver']
        from .tree_navigation import show_tree
        self._action(v,'Estructura jerárquica…',lambda: self._workspace_setting(show_tree))
        for key in ('precios','conceptos','relaciones'):
            self._action(v,self.panels[key][0].split(' · ')[0],lambda checked=False,k=key:self.show_panel(k),key='ver-'+key)
        for key in ('arbol','capitulos','capitulos-partidas'):
            self._action(v,self.panels[key][0],lambda checked=False,k=key:self.show_panel(k),key='ver-'+key)
        for label in ('Enlace CAD','Entidades','Entidades y conceptos','Términos y conceptos','Agenda','Resumen de fases','Registros','Tiempos','Contratos','Control'):
            self._action(v,label)
        v.addSeparator()
        for key in ('texto','mediciones','avisos','certificacion','certificacion-fases','planificacion','gestion','informes'):
            self._action(v,self.panels[key][0],lambda checked=False,k=key:self.show_panel(k),key='ver-'+key)
        disabled = {
            'Asistentes': ('Introducción de datos','Generación de precios y entidades','Traspaso a la obra','Configuración','Memoria','Modelos','Cuadros de precios soportados','Codificación de entidades'),
            'Herramientas': ('Actualizar conceptos de referencia','Actualizar entidades de referencia','Actualizar mediciones','Comparar dos obras','Sustituir concepto','Regenerar paramétricos','Elegir precio de una entidad','Asociar entidades a conceptos','Reducir niveles','Regenerar presupuesto u objetivo','Generar pliego de condiciones','Crear registros','Generar precedencias','Rellenar planificación','Generar lotes de compra','Calcular recursos y contratos','Paramétricos','Optimizar imágenes'),
            'Macros': ('Complementos','Exportar compras a Obralia','Exportar facturas'),
            'Informes': ('Imprimir informes','Configurar página','Encadenar informes','Diseñar informe','Personalizar plantilla','Actualizar lista de informes'),
            'Internet': ('Actualizar lista de catálogos y cuadros',),
        }
        for name, labels in disabled.items():
            for label in labels:
                self._action(self.menus[name],label,key=name+':'+label)
        from .report_actions import export_report, preview_report, configure_page
        self._action(self.menus['Informes'], 'Configurar página…', lambda: configure_page(self))
        self._action(self.menus['Informes'], 'Exportar informe…', lambda: export_report(self))
        self._action(self.menus['Informes'], 'Vista previa e impresión…', lambda: preview_report(self), 'Ctrl+P')
        c = self.menus['Cálculos']
        from .calculation_dialogs import configure_engine
        self._action(c,'Motor económico…',lambda: configure_engine(self))
        from .calculation_dialogs import configure_summary
        self._action(c,'Porcentajes del resumen…',lambda: configure_summary(self))
        from .precision_settings import configure
        self._action(c,'Precisión económica…',lambda: configure(self))
        self._action(c,'Precios',self.recalculate,key='calcular-precios')
        self._action(c,'Multiplicar precios seleccionados…',self.multiply_selected_prices,key='multiplicar-precios')
        self._action(c,'Operar precios por naturaleza…',self.multiply_nature_prices)
        self._action(c,'Ajustar precio…',self.adjust_selected_price,key='ajustar-precio')
        self.commands['ajustar-precio-calculos'] = self.commands['ajustar-precio']
        self._action(c,'Precisión de cantidades de la raíz…',self.configure_root_precision,key='precision-raiz')
        self._action(c,'Costes indirectos…',self.configure_indirect_costs,key='costes-indirectos')
        self._action(c,'Bloquear precio…',self.lock_selected_price,key='bloquear-precio')
        self._action(c,'Desbloquear precio',self.unlock_selected_price,key='desbloquear-precio')
        for label,target in (('Directorio de entidades','gestion:entities'),('Costes de documentos','gestion:cost_control'),('Rendimientos de obra','gestion:productivity'),('Horas y equipos','gestion:resource_hours'),('Líneas base del presupuesto','gestion:budget_baselines'),('Inventario a fecha','gestion:inventory_control')):
            self._action(c,label,lambda checked=False,target=target:self.section_ui.ribbon.show_view(target))
        self._action(c,'Calcular todo',self.recalculate)
        self._action(self.menus['Edición'],'Términos de búsqueda…',self.edit_search_terms,key='concept-search-terms')
        w = self.menus['Ventana']
        self._action(w,'Cascada',self.cascade_windows)
        self._action(w,'Mosaico horizontal',lambda:self.tile_windows(True))
        self._action(w,'Mosaico vertical',lambda:self.tile_windows(False))
        snap=w.addAction('Imán entre ventanas');snap.setCheckable(True);snap.setChecked(self.window_snapping);snap.toggled.connect(self.set_window_snapping)
        self._action(w,'Estilos de ventanas de defecto',self.default_layout)
        from .workspace_settings import save_layout, restore_layout
        self._action(w,'Guardar estilo de ventanas',lambda: self._workspace_setting(save_layout))
        self._action(w,'Recuperar estilo de ventanas',lambda: self._workspace_setting(restore_layout))
        w.addSeparator()
        for key,(title,_) in self.panels.items():
            self._action(w,title,lambda checked=False,k=key:self.show_panel(k),key='ventana-'+key)
        from .help_view import show_help
        self._action(self.menus['?'],'Ayuda',lambda: show_help(self),'F1',requires_project=False)
        self._action(self.menus['?'],'Acerca de OpenPresto',self._about,requires_project=False)
        toolbar = self.findChildren(QToolBar)[0]
        toolbar.clear()
        toolbar.setObjectName('estandar')
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        toolbar.setIconSize(QSize(20, 20))
        toolbar.setStyleSheet('QToolBar { spacing: 6px; padding: 4px; } QToolButton { padding: 3px 8px; }')
        for key in ('Nuevo','Abrir…','Guardar','importar','Presto PZH · experimental…','Deshacer','Rehacer','Añadir concepto…','Insertar relación…','Introducir medición…','Calcular todo'):
            action = self.commands[key][0]
            action.setIconText({'Abrir…':'Abrir', 'Añadir concepto…':'Concepto', 'Insertar relación…':'Relación', 'Introducir medición…':'Medición', 'Calcular todo':'Calcular', 'importar':'BC3', 'Presto PZH · experimental…':'PZH'}.get(key, key))
            if key in ('Deshacer', 'Añadir concepto…', 'Calcular todo'):
                toolbar.addSeparator()
            toolbar.addAction(action)
        toolbar.addSeparator()
        action = self.commands['ver-certificacion-fases'][0]
        action.setIconText('Certificaciones')
        toolbar.addAction(action)

    def _sync_actions(self):
        if not hasattr(self,'commands'):
            return
        from shiboken6 import isValid
        if not all(isValid(menu) for menu in self.menus.values()):
            return
        for name, menu in self.menus.items():
            menu.menuAction().setVisible((self.project_open or name in ('Archivo','Internet','?')) and any(action.isVisible() and not action.isSeparator() for action in menu.actions()))
        for key,(action,implemented,needs_project) in self.commands.items():
            enabled = implemented and (self.project_open or not needs_project)
            if key == 'Deshacer':
                enabled = enabled and (bool(self._undo) or self._text_pending)
            if key == 'Rehacer':
                enabled = enabled and bool(self._redo) and not self._text_pending
            if key == 'Introducir medición…':
                enabled = enabled and bool(self.selected_relation)
            if key == 'bloquear-precio':
                enabled = enabled and any(r.parent_code == self.active_concept for r in self.budget.relations)
            if key in ('ajustar-precio', 'ajustar-precio-calculos'):
                code = self.active_concept
                enabled = enabled and bool(code) and not code.endswith('#') and code != self.budget.root_code and any(r.parent_code == code for r in self.budget.relations)
            if key == 'desbloquear-precio':
                enabled = enabled and self.active_concept in self.budget.locked_prices
            if key == 'Eliminar':
                # Supr dentro de una celda o del texto pertenece al editor de texto.
                enabled = enabled and QApplication.focusWidget() in (self.prices,self.concepts_table,self.relations_table,self.measurements_table,self.budget_structure.tree) and self._selected_table() is not None
            action.setEnabled(enabled)
        if self.project_open and self._text_pending:
            self.setWindowTitle(f'{self.path.name if self.path else "Sin guardar"} * — OpenPresto')
        if not self.project_open:
            self.setWindowTitle('OpenPresto · Sin obra')
            self.statusBar().showMessage('Crea un proyecto o importa un presupuesto BC3 para empezar.')

    def show_panel(self,key):
        if not self.project_open:
            return
        if key not in self.windows:
            title, widget = self.panels[key]
            from .mdi_windows import WorkspaceWindow
            sub = WorkspaceWindow(self)
            sub.setStyle(self._mdi_style)
            palette = sub.palette()
            for role,color in ((QPalette.ColorRole.Window,'#f2f2f2'),(QPalette.ColorRole.Button,'#e9edf2'),(QPalette.ColorRole.Highlight,'#c5d4e8'),(QPalette.ColorRole.WindowText,'#28313c')):
                palette.setColor(role,QColor(color))
            sub.setPalette(palette)
            sub.setObjectName(key)
            sub.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose,False)
            sub.setWidget(widget)
            sub.setWindowIcon(self.windowIcon())
            self.mdi.addSubWindow(sub)
            sub.setWindowTitle(title)
            sub.resize(850,380)
            self.windows[key] = sub
        sub = self.windows[key]
        sub.show()
        sub.widget().show()
        if key in ('arbol','capitulos','capitulos-partidas'):sub.widget().render()
        self.mdi.setActiveSubWindow(sub)
        self.update_titles()

    def show_widget(self,widget):
        if widget is self.measurements_table:self.show_panel('mediciones');return
        for key,(_,candidate) in self.panels.items():
            if candidate is widget:
                self.show_panel(key)
                break

    def show_prices(self):
        self.show_panel('precios')

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if (self._ready and self.project_open and self._reference_layout
                and self.section_ui.active == 0):
            QTimer.singleShot(0, self._resize_reference_layout)

    def _resize_reference_layout(self):
        if (self.project_open and self._reference_layout and self.section_ui.active == 0
                and all(key in self.windows and self.windows[key].isVisible()
                        and not self.windows[key].isMaximized()
                        for key in ('precios', 'conceptos', 'mediciones', 'texto'))):
            self.default_layout()

    def default_layout(self):
        if not self.project_open:
            return
        self._reference_layout = True
        for key in ('precios','conceptos','mediciones','texto'):
            self.show_panel(key)
        width, height = self.mdi.viewport().width(), self.mdi.viewport().height()
        top = height * 59 // 100
        left = width * 59 // 100
        measurement = left * 64 // 100
        rectangles = (
            ('precios', QRect(0, 0, left, top)),
            ('conceptos', QRect(left, 0, width-left, height)),
            ('mediciones', QRect(0, top, measurement, height-top)),
            ('texto', QRect(measurement, top, left-measurement, height-top)),
        )
        for key, rect in rectangles:
            self.windows[key].showNormal()
            self.windows[key].setMinimumSize(160, 100)
            self.windows[key].setGeometry(rect)
        self.mdi.setActiveSubWindow(self.windows['precios'])

    def set_window_snapping(self,enabled):
        self.window_snapping=enabled;QSettings().setValue('workspace/snap',enabled)

    def cascade_windows(self):
        self._reference_layout=False;self.mdi.cascadeSubWindows()

    def tile_windows(self,horizontal):
        self._reference_layout = False
        windows = [w for w in self.mdi.subWindowList() if w.isVisible()]
        n = len(windows)
        if not n:
            return
        width,height = self.mdi.viewport().width(),self.mdi.viewport().height()
        for i,window in enumerate(windows):
            window.showNormal()
            window.setGeometry(QRect(0,i*height//n,width,(i+1)*height//n-i*height//n) if horizontal else QRect(i*width//n,0,(i+1)*width//n-i*width//n,height))

    def update_titles(self):
        for key,sub in self.windows.items():
            suffix = self.current_code if key == 'precios' else self.active_concept if key in ('texto','mediciones') else None
            title=self.panels[key][0]
            if key=='precios' and self.budget_stack.currentWidget() is self.budget_structure:title=self.budget_view.currentText()+' · Presupuesto';suffix=None
            if key=='mediciones':title='Mediciones'
            if key=='texto':title='Texto'
            sub.setWindowTitle(title + (f' · {suffix}' if suffix else ''))
        if hasattr(self,'section_ui'):self.section_ui.ribbon.sync_views()

    def set_budget_view(self,key):
        index=self.budget_view.findData(key)
        if index<0:return
        with QSignalBlocker(self.budget_view):self.budget_view.setCurrentIndex(index)
        if key=='precios':self.budget_stack.setCurrentWidget(self.prices)
        else:
            if self.budget_structure.mode!=key:self.budget_structure.mode=key;self.budget_structure._stamp=None
            self.budget_stack.setCurrentWidget(self.budget_structure)
            if self.project_open:self.budget_structure.render();self.budget_structure.sync_selection();self.budget_structure.filter(self.search.text())
        if self.project_open:self.update_titles()

    def _open_views(self):
        self.project_open = True
        self.budget_structure._stamp=None
        self._selection_origin = 'precios'
        with QSignalBlocker(self.search):
            self.search.clear()
        self.refresh()
        self.section_ui.tabs.setCurrentIndex(0)
        self.section_ui.activate(0)

    def load_path(self,name, *, observed_presto88=False, native_economic=False):
        self.flush_text()
        if not super().load_path(name, observed_presto88=observed_presto88, native_economic=native_economic):
            return False
        self.selected_relation = None
        from .session_services import remember
        remember(name)
        self._open_views()
        return True

    def import_native_profile(self):
        from .preferences import working_directory
        if not self._confirm_discard():
            return
        name,_=QFileDialog.getOpenFileName(self,'Importar BC3 con motor nativo',working_directory(),'BC3 (*.bc3)')
        if name:
            self.load_path(name,native_economic=True)

    def import_observed_profile(self):
        if not self._confirm_discard():
            return
        name, _ = QFileDialog.getOpenFileName(self, 'Importar con perfil contrastado Presto 8.8', '', 'BC3 (*.bc3)')
        if name:
            self.load_path(name, observed_presto88=True)

    def export_budget(self):
        self.flush_text()
        encoding, accepted = QInputDialog.getItem(self, 'Codificación BC3', 'Codificación del receptor:',
            ['cp1252', 'utf-8', 'cp850', 'cp437'], 0, False)
        if not accepted:
            return
        try:
            result = render_bc3(self.budget, encoding=encoding)
            from .preferences import working_directory
            name, _ = QFileDialog.getSaveFileName(self, 'Exportar BC3 a un archivo nuevo', working_directory(),
                'BC3 (*.bc3)', options=QFileDialog.Option.DontConfirmOverwrite)
            if not name:
                return
            if not name.lower().endswith('.bc3'):
                name += '.bc3'
            result = save_bc3(self.budget, name, encoding=encoding)
        except (BC3ExportError, BudgetError, ArithmeticError, RecursionError) as exc:
            self._error(exc)
            return
        QMessageBox.information(self, 'BC3 exportado', '\n'.join(result.warnings))
        self.statusBar().showMessage('BC3 creado a partir de los datos actuales.', 7000)

    def new_budget(self):
        self.flush_text()
        old = self.budget
        super().new_budget()
        if self.budget is not old:
            self.current_code = self.active_concept = self.selected_relation = None
            self._navigation = []
            self._open_views()

    def close_project(self):
        if not self._confirm_discard():
            return False
        from .session_services import cleanup_recovery
        cleanup_recovery(self)
        from .pzh_assets import clear_cache
        clear_cache()
        self.project_open = False
        for key,sub in self.windows.items():
            widget = self.panels[key][1]
            widget.setParent(self)
            widget.hide()
            self.mdi.removeSubWindow(sub)
            sub.deleteLater()
        self.windows.clear()
        self.budget = Budget()
        self.path = None
        self._file_revision = None
        self.dirty = False
        self.current_code = self.active_concept = self.selected_relation = None
        self._navigation = []
        self._reset_history()
        self.refresh()
        return True

    def open_demo(self):
        if self._confirm_discard():
            self.load_path(Path(__file__).with_name('data')/'presupuesto-demo.bc3')

    def open_modules_demo(self):
        if not self._confirm_discard():return
        if self.load_path(Path(__file__).with_name('data')/'planificacion-gestion-demo.openpresto.json'):
            self.path=None;self._file_revision=None;self.dirty=True;self._reset_history();self.refresh()

    def refresh(self):
        if not self._ready:
            super().refresh()
            return
        self._refreshing = True
        tables = (self.prices,self.concepts_table,self.relations_table,self.measurements_table,self.certification_table)
        blockers = [QSignalBlocker(t) for t in tables]
        measurement_key = self._measurement_keys[self.measurements_table.currentRow()] if 0 <= self.measurements_table.currentRow() < len(self._measurement_keys) else None
        concept_code = self.concepts_table.item(self.concepts_table.currentRow(),0)
        concept_code = concept_code.text() if concept_code else None
        old_relation_row = self.relations_table.currentRow()
        old_ids = getattr(self,'_relation_ids',[])
        relation_id = old_ids[old_relation_row] if 0 <= old_relation_row < len(old_ids) else None
        presentation = QSettings().value('numbers/decimal_separator','.',type=str)
        data_changed = (getattr(self, '_table_presentation', None) != presentation or
                        getattr(self, '_table_budget', None) is not self.budget or
                        getattr(self, '_table_snapshot', None) != self._snapshot)
        if data_changed:
            super().refresh()
        from .bc3_aliases import source_synonyms
        synonyms = source_synonyms(self.budget.source_records, self.budget.concepts)
        from .concept_keywords import validate as keyword_state
        keywords=keyword_state(self.budget)
        search_terms={code:tuple(synonyms.get(code,()))+tuple(keywords.get(code,{}).get('terms',())) for code in self.budget.concepts}
        self._budget_search_terms=search_terms
        for row, code in enumerate(self.budget.concepts):
            if data_changed:
                concept=self.budget.concepts[code];style_code(self.concepts_table.item(row,0),concept,self.budget.root_code)
                self.concepts_table.item(row,3).setIcon(nature_icon(concept.nature));self.concepts_table.item(row,3).setToolTip(concept.nature)
                self.concepts_table.item(row,4).setForeground(QColor('#c445cc'))
                if concept.nature.casefold() in ('capitulo','capítulo') or code==self.budget.root_code:
                    for col in range(self.concepts_table.columnCount()):
                        item=self.concepts_table.item(row,col);item.setBackground(QColor('#cbd4e2'));font=item.font();font.setBold(True);item.setFont(font)
                style_code(self.concepts_table.item(row,0),concept,self.budget.root_code)
            if synonyms.get(code):
                self.concepts_table.item(row,0).setToolTip('Sinónimos BC3: ' + ', '.join(synonyms[code]))
        self._relation_ids = [r.id for r in self.budget.relations]
        if data_changed:
            for row,relation in enumerate(self.budget.relations):
                for col,code in ((1,relation.parent_code),(2,relation.child_code)):
                    style_code(self.relations_table.item(row,col),self.budget.concepts[code],self.budget.root_code)
        if relation_id in self._relation_ids:
            self.relations_table.setCurrentCell(self._relation_ids.index(relation_id),0)
        if self.current_code not in self.budget.concepts:
            self.current_code = self.budget.root_code
            self._navigation = []
        self._visible_relations = sorted((r for r in self.budget.relations if r.parent_code == self.current_code),key=lambda r:r.position)
        self.crumb.setText(self.current_code or 'Sin raíz: añade el primer concepto')
        calc = BudgetCalculator(self.budget)
        from .calculations import calculation_batch
        with calculation_batch(calc):
            visible_amounts = {r.id: calc.relation(r.id) for r in self._visible_relations}
        self.prices.setRowCount(len(self._visible_relations))
        measured_relations={m.relation_id for m in self.budget.measurements}
        measured_relations.update(rid for rid,record in self.budget.bc3_measurements.items() if record.lines)
        composed_codes={r.parent_code for r in self.budget.relations}
        for row,relation in enumerate(self._visible_relations):
            concept = self.budget.concepts[relation.child_code]
            percentage = '%' in concept.code
            value = visible_amounts[relation.id]
            composed = concept.code in composed_codes
            info = ('t' if concept.text else '') + ('m' if relation.id in measured_relations else '') + ('r' if composed else '')
            values = (concept.code,concept.nature,info,concept.unit,concept.summary,value.quantity,value.unit_price,value.amount,relation.factor)
            for col,value in enumerate(values):
                item = QTableWidgetItem(display(value))
                item.setData(Qt.ItemDataRole.UserRole,relation.id)
                if col == 1:
                    item.setIcon(nature_icon(concept.nature))
                    item.setToolTip(concept.nature)
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole + 1, ' '.join(search_terms.get(concept.code, ())))
                    if synonyms.get(concept.code):
                        item.setToolTip('Sinónimos BC3: ' + ', '.join(synonyms[concept.code]))
                editable = col in (1,3,4) or (col == 8 and not percentage and not self.budget.has_certification(relation.id)) or (col == 5 and not percentage and relation.id not in measured_relations) or col == 6
                if not editable:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if col == 5 and not editable:
                    item.setToolTip('Base porcentual calculada desde importes anteriores.' if percentage else
                                    'Cantidad calculada: modifica las líneas de Medición del presupuesto.')
                if col == 6 and percentage:
                    item.setToolTip('Tipo porcentual compartido por este código. Se guarda como fracción en el rendimiento BC3.')
                if col == 6 and not editable:
                    item.setToolTip('Precio calculado desde la descomposición.')
                if col == 6 and composed:
                    item.setToolTip('Al introducir un precio puedes bloquearlo conservando la descomposición o cancelar.')
                if col == 6 and concept.code in self.budget.locked_prices:
                    item.setForeground(QColor('#ef7777'))
                    item.setToolTip('Precio bloqueado. Cálculos → Desbloquear precio recalcula desde los componentes actuales.')
                if col >= 5:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if concept.nature.casefold() in ('capítulo', 'capitulo'):
                    item.setBackground(QColor('#cbd4e2'))
                    font = item.font(); font.setBold(True); item.setFont(font)
                elif col == 0:
                    item.setBackground(QColor('#fff0df'))
                if col in (5, 6) and not (col == 6 and concept.code in self.budget.locked_prices):
                    item.setForeground(QColor('#bd3ebd'))
                if col == 7:
                    item.setBackground(QColor('#fffde5'))
                if col == 0:
                    style_code(item,concept,self.budget.root_code)
                self.prices.setItem(row,col,item)
        for i,code in enumerate(self.budget.concepts):
            if code == concept_code:
                self.concepts_table.setCurrentCell(i,0)
        if data_changed:
            self._render_measurements()
            self._render_certification()
            self.certification_phase_panel.render()
            self._table_budget = self.budget
            self._table_snapshot = self._snapshot
            self._table_presentation = presentation
        if measurement_key in self._measurement_keys:
            self.measurements_table.setCurrentCell(self._measurement_keys.index(measurement_key),0)
        self.filter_prices()
        row = next((i for i,r in enumerate(self._visible_relations) if r.id == self.selected_relation and not self.prices.isRowHidden(i)),None)
        if row is None:
            row = next((i for i in range(self.prices.rowCount()) if not self.prices.isRowHidden(i)),None)
        self.prices.setCurrentCell(row if row is not None else -1,0)
        blockers.clear()
        self._refreshing = False
        self.import_notes.setPlainText('\n'.join(self.budget.import_warnings) or
            self.budget.project_metadata.get('pzh_import_notes', '') or 'Sin avisos de importación.')
        if self._selection_origin == 'conceptos' and concept_code in self.budget.concepts:
            self.select_concept()
        elif self._selection_origin == 'relaciones' and relation_id in self._relation_ids:
            self.select_relation()
        else:
            self.select_price()
        self._sync_actions()
        self.section_ui.refresh()
        for key in ('arbol','capitulos','capitulos-partidas'):
            if key in self.windows and self.windows[key].isVisible():self.panels[key][1].render()
        if self.project_open and self.budget_stack.currentWidget() is self.budget_structure:
            self.budget_structure.render();self.budget_structure.sync_selection();self.budget_structure.filter(self.search.text())

    def _render_measurements(self):
        from .measurement_operations import native_displays
        displays = native_displays(self.budget)
        native = {m.id:m for m in self.budget.measurements}
        self._measurement_row_groups={}
        self._measurement_filter_ready=False
        for row,(key,identity) in enumerate(self._measurement_keys):
            rid=native[identity].relation_id if key=='native' else key
            self._measurement_row_groups.setdefault(rid,[]).append(row)
            if key == 'native':
                m = native[identity]
                partial, subtotal, kind = displays[m.id]
                values = (m.comment,m.n_lines,m.length,m.width,m.height,m.formula,partial,subtotal,kind,'—')
                editable = {0} if subtotal != '' else {0,1,2,3,4,5}
            else:
                m = self.budget.bc3_measurements[key].lines[identity]
                subtotal = m.kind in ('1','2')
                values = ('' if m.kind == '3' else m.description,m.a,m.b,m.c,m.d,m.description if m.kind == '3' else m.applied_formula, '' if subtotal else m.partial,m.partial if subtotal else '',m.kind,'—')
                editable = ({1,2,3,4,5,8} if m.kind == '3' else {0,1,2,3,4,5,8}) if not subtotal else {0,8}
            for col,value in enumerate(values):
                item = QTableWidgetItem('' if value is None else display(value))
                if col not in editable:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if key == 'native' and col in (1,2,3,4) and ('n_lines','length','width','height')[col-1] in m.annulled_dimensions:
                    item.setBackground(QColor('#e4e7ec'))
                    item.setToolTip('Dimensión anulada: conserva su valor y no multiplica la cantidad.')
                if col == 9:
                    item.setToolTip('Este modelo todavía no admite fases. No se asigna una fase ficticia.')
                self.measurements_table.setItem(row,col,item)

    def _render_certification(self):
        from .certifications import CertificationAtOrigin
        cert = CertificationAtOrigin(self.budget, self.budget.certified_quantities)
        self._certification_ids = []
        for relation in self.budget.relations:
            try:
                cert._eligible(relation.id)
            except BudgetError:
                continue
            self._certification_ids.append(relation.id)
        self.certification_table.setRowCount(len(self._certification_ids))
        for row, rid in enumerate(self._certification_ids):
            relation = self.budget._relation(rid)
            result = cert.relation(rid)
            entered = self.budget.certified_quantities.get(rid, '')
            phased = any(rid in rows for rows in self.budget.phase_certified_quantities.values())
            values = (relation.parent_code, relation.child_code,
                self.budget.concepts[relation.child_code].unit, result.budget_quantity,
                entered, result.unit_price, result.amount,
                'Por fases' if phased else 'Exceso' if result.exceeds_budget else 'A origen')
            for col, value in enumerate(values):
                item = QTableWidgetItem(display(value))
                if col not in (4, 5) or (phased and col == 4):
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if phased:
                    item.setToolTip('Esta relación se certifica por fases. Vacía sus cantidades por periodo antes de introducir un valor a origen.')
                if result.exceeds_budget:
                    item.setForeground(QColor('#ef7777'))
                self.certification_table.setItem(row, col, item)

    def edit_certification_cell(self, item):
        if self._refreshing or item.column() not in (4, 5):
            return
        rid = self._certification_ids[item.row()]
        text = item.text().strip()
        command = 'certification.price.set' if item.column() == 5 else 'certification.origin.quantity.set'
        self._execute(command, relation_id=rid, value=text.replace(',', '.') or None)

    def filter_prices(self):
        query = self.search.text().strip().casefold()
        for row in range(self.prices.rowCount()):
            text = ' '.join(self.prices.item(row,col).text() for col in (0,4) if self.prices.item(row,col))
            code = self.prices.item(row,0)
            if code:
                text += ' ' + (code.data(Qt.ItemDataRole.UserRole + 1) or '')
            self.prices.setRowHidden(row,query not in text.casefold())
        if hasattr(self,'budget_stack') and self.budget_stack.currentWidget() is self.budget_structure and not self._refreshing:
            self.budget_structure.filter(query)
            if query:
                matches=getattr(self.budget_structure,'_matching_paths',[]);tree=self.budget_structure.tree;current=tree.currentItem()
                if not matches:
                    with QSignalBlocker(tree):tree.clearSelection();tree.setCurrentItem(None)
                    self.selected_relation=None;self.active_concept=None;self.sync_secondary()
                elif current is None or current.data(0,Qt.ItemDataRole.UserRole) not in matches:tree.setCurrentItem(self.budget_structure.items[matches[0]])
            return
        if not self._refreshing:
            if self.prices.currentRow() < 0 or self.prices.isRowHidden(self.prices.currentRow()):
                row = next((r for r in range(self.prices.rowCount()) if not self.prices.isRowHidden(r)),-1)
                self.prices.setCurrentCell(row,0)
            self.select_price()

    def edit_search_terms(self):
        from .concept_keywords import validate
        code=self.active_concept
        if code not in self.budget.concepts:self._error('Selecciona un concepto.');return
        terms=validate(self.budget).get(code,{}).get('terms',[])
        text,accepted=QInputDialog.getMultiLineText(self,'Términos de búsqueda','Un término por línea. No son códigos alternativos.', '\n'.join(terms))
        if accepted:self._execute('concept.keywords.set',code=code,terms=[line.strip() for line in text.splitlines() if line.strip()])

    def select_price(self):
        if not self._ready or self._refreshing:
            return
        row = self.prices.currentRow()
        relation = self._visible_relations[row] if 0 <= row < len(self._visible_relations) and not self.prices.isRowHidden(row) else None
        self.flush_text()
        self._selection_origin = 'precios'
        self.selected_relation = relation.id if relation else None
        self.active_concept = relation.child_code if relation else self.current_code if not self.search.text() else None
        if relation:
            row = next((i for i,r in enumerate(self._visible_relations) if r.id == relation.id),-1)
            with QSignalBlocker(self.prices):
                self.prices.selectionModel().setCurrentIndex(self.prices.model().index(row,0), QItemSelectionModel.SelectionFlag.NoUpdate)
        self.sync_secondary()

    def select_concept(self):
        if not self._ready or self._refreshing:
            return
        item = self.concepts_table.item(self.concepts_table.currentRow(),0)
        code = item.text() if item else None
        self.flush_text()
        self._selection_origin = 'conceptos'
        self.active_concept = code
        self.selected_relation = None
        self.sync_secondary()

    def select_relation(self):
        if not self._ready or self._refreshing:
            return
        row = self.relations_table.currentRow()
        relation = self.budget.relations[row] if 0 <= row < len(self.budget.relations) else None
        self.flush_text()
        self._selection_origin = 'relaciones'
        self.selected_relation = relation.id if relation else None
        self.active_concept = relation.child_code if relation else None
        self.sync_secondary()

    def sync_secondary(self):
        self._text_code = self.active_concept
        concept = self.budget.concepts.get(self.active_concept)
        with QSignalBlocker(self.text_editor):
            value = concept.text if concept else ''
            if self.text_editor.toPlainText() != value:
                self.text_editor.setPlainText(value)
            self.text_editor.setReadOnly(concept is None)
        self.filter_measurements()
        self.update_titles()
        self._sync_actions()

    def filter_measurements(self):
        target=self.selected_relation
        groups=getattr(self,'_measurement_row_groups',{})
        if not getattr(self,'_measurement_filter_ready',False):
            visible=set(groups.get(target,()))
            for row in range(self.measurements_table.rowCount()):
                self.measurements_table.setRowHidden(row,row not in visible)
            self._measurement_filter_ready=True
        elif self._measurement_filter_relation!=target:
            for row in groups.get(self._measurement_filter_relation,()):
                self.measurements_table.setRowHidden(row,True)
            for row in groups.get(target,()):
                self.measurements_table.setRowHidden(row,False)
        self._measurement_filter_relation=target

    def has_measurements(self,rid):
        return bool(rid in self.budget.bc3_measurements and self.budget.bc3_measurements[rid].lines) or any(m.relation_id == rid for m in self.budget.measurements)

    def price_columns_menu(self):
        menu = QMenu(self.prices)
        multiply = menu.addAction('Multiplicar precios seleccionados…')
        multiply.setEnabled(self.project_open and bool(self.prices.selectionModel().selectedRows()))
        multiply.triggered.connect(self.multiply_selected_prices)
        menu.addSeparator()
        for column in range(self.prices.columnCount()):
            label = self.prices.horizontalHeaderItem(column).text()
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(not self.prices.isColumnHidden(column))
            action.toggled.connect(lambda visible, col=column: self.prices.setColumnHidden(col, not visible))
        menu.addSeparator()
        restore = menu.addAction('Mostrar todas las columnas')
        restore.triggered.connect(self.show_all_price_columns)
        return menu

    def multiply_nature_prices(self):
        from .commands import execute
        from decimal import Decimal
        self.flush_text()
        composed = {r.parent_code for r in self.budget.relations}
        concepts = [c for c in self.budget.concepts.values() if c.code not in composed
                    and c.code != self.budget.root_code and '%' not in c.code and not c.code.startswith(('Σ','∑','Ʃ'))]
        natures = sorted({c.nature for c in concepts})
        if not natures:
            self._error('No hay precios básicos disponibles')
            return
        labels = [nature or '(sin clasificar)' for nature in natures]
        label,ok = QInputDialog.getItem(self,'Operar cuadro de precios','Naturaleza:',labels,0,False)
        if not ok:
            return
        text,ok = QInputDialog.getText(self,'Operar cuadro de precios','Factor positivo:',text='1')
        if not ok:
            return
        try:
            codes = [c.code for c in concepts if c.nature == natures[labels.index(label)]]
            proposed = execute(self.budget, 'budget.price.scale', {'factor':text.strip().replace(',','.'), 'codes':codes})
            before,after = BudgetCalculator(self.budget).total(),BudgetCalculator(proposed).total()
        except (ValueError,ArithmeticError) as exc:
            self._error(exc)
            return
        answer = QMessageBox.question(self,'Aplicar operación',
            f'{len(codes)} conceptos básicos de toda la obra. Total: {before} → {after}',
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self._execute('budget.price.scale', factor=text.strip().replace(',', '.'), codes=codes)

    def multiply_selected_prices(self):
        from decimal import Decimal
        from .commands import execute
        self.flush_text()
        rows = sorted({index.row() for index in self.prices.selectionModel().selectedRows()
                       if not self.prices.isRowHidden(index.row())})
        codes = list(dict.fromkeys(self._visible_relations[row].child_code for row in rows))
        if not codes:
            self._error('Selecciona las filas de los precios básicos que quieres multiplicar.')
            return
        text, accepted = QInputDialog.getText(self, 'Multiplicar precios seleccionados', 'Factor positivo:', text='1')
        if not accepted:
            return
        try:
            factor = Decimal(text.strip().replace(',', '.'))
            proposed = execute(self.budget, 'budget.price.scale', {'factor':str(factor), 'codes':codes})
            lines = []
            for code in codes:
                old = self.budget.concepts[code].base_price
                new = proposed.concepts[code].base_price
                lines.append(f'{code}: {old} → {new}')
        except (ValueError, ArithmeticError) as exc:
            self._error(exc)
            return
        preview = '\n'.join(lines[:20])
        if len(lines) > 20:
            preview += f'\n… y {len(lines)-20} conceptos más.'
        reply = QMessageBox.question(self, 'Aplicar multiplicación',
            f'{len(codes)} conceptos básicos. Cada código se modifica una sola vez.\n{preview}\n'
            f'Total: {BudgetCalculator(self.budget).total()} → {BudgetCalculator(proposed).total()}',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self._execute('budget.price.scale', factor=str(factor), codes=codes)

    def adjust_selected_price(self):
        from decimal import Decimal
        self.flush_text()
        code = self.active_concept
        if not self.project_open or code not in self.budget.concepts:
            return
        text, accepted = QInputDialog.getText(self, 'Ajustar precio',
            f'{code} · Precio de presupuesto solicitado:\n'
            'Se ajustan los precios de todos sus recursos básicos; se conservan los rendimientos.',
            text=str(BudgetCalculator(self.budget).price(code)))
        if not accepted:
            return
        try:
            self._apply_price_adjustment(code, Decimal(text.strip().replace(',', '.')))
        except (ValueError, ArithmeticError) as exc:
            self._error(exc)

    def _apply_price_adjustment(self, code, target):
        from .price_adjustment import adjust_price
        result = adjust_price(self.budget, code, target)
        lines = [f'{child}: {self.budget.concepts[child].base_price} → '
                 f'{result.budget.concepts[child].base_price}' for child in result.changed_codes]
        preview = '\n'.join(lines[:20])
        if len(lines) > 20:
            preview += f'\n… y {len(lines)-20} recursos más.'
        before_total = BudgetCalculator(self.budget).total()
        after_total = BudgetCalculator(result.budget).total()
        answer = QMessageBox.question(self, 'Aplicar ajuste de precio',
            f'{code}\nSolicitado: {target}\nResultado: {result.achieved_price}\n'
            f'Diferencia: {result.achieved_price - target}\n\n{preview}\n\n'
            'Los redondeos pueden impedir alcanzar el precio solicitado.\n'
            'Los recursos cambian también en las demás partidas que los utilicen.\n'
            f'Total de obra: {before_total} → {after_total}\n'
            'Puedes deshacer todo el ajuste en un solo paso.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self._execute('budget.price.adjust', code=code, target=str(target))

    def show_all_price_columns(self):
        for column in range(self.prices.columnCount()):
            self.prices.setColumnHidden(column, False)

    def price_columns_context_menu(self, position):
        menu = self.price_columns_menu()
        menu.exec(self.prices.horizontalHeader().mapToGlobal(position))
        menu.deleteLater()

    def price_context_menu(self, position):
        item = self.prices.itemAt(position)
        if item is None:
            return
        if not item.isSelected():
            self.prices.setCurrentItem(item)
        else:
            self.prices.selectionModel().setCurrentIndex(
                self.prices.indexFromItem(item), QItemSelectionModel.SelectionFlag.NoUpdate)
        self.select_price()
        menu = QMenu(self.prices)
        for key in ('Copiar','Cortar','Pegar','Editar selección…','Editar conceptos seleccionados…',
                    'Duplicar concepto…','Mover relación…','Eliminar'):
            command = self.commands.get(key)
            if command:
                menu.addAction(command[0])
        menu.addSeparator()
        for key in ('bloquear-precio','desbloquear-precio','ajustar-precio'):
            command = self.commands.get(key)
            if command and command[0].isEnabled():
                menu.addAction(command[0])
        menu.exec(self.prices.viewport().mapToGlobal(position))
        menu.deleteLater()

    def lock_selected_price(self):
        code = self.active_concept
        if code not in self.budget.concepts or not any(r.parent_code == code for r in self.budget.relations):
            return
        value, accepted = QInputDialog.getText(self, 'Bloquear precio',
            'Precio manual compartido por todas las apariciones del concepto:',
            text=str(BudgetCalculator(self.budget).price(code)))
        if not accepted:
            return
        self._execute('budget.price.lock', code=code, value=value.strip().replace(',', '.'))

    def unlock_selected_price(self):
        code = self.active_concept
        if code in self.budget.locked_prices:
            self._execute('budget.price.lock', code=code)

    def configure_indirect_costs(self):
        current = self.budget.indirect_config
        mode, accepted = QInputDialog.getItem(self, 'Costes indirectos',
            'Configura capítulos y tipo. El motor económico seleccionado determina las reglas de valoración.',
            ['Configurar', 'Desactivar'], 0, False)
        if not accepted:
            return
        if mode == 'Desactivar':
            self._execute('budget.indirect.set')
            return
        chapters, accepted = QInputDialog.getText(self, 'Capítulos',
            'Códigos exactos de los capítulos separados por coma (incluido # si existe):',
            text=', '.join(current['chapter_codes']) if current else ', '.join(c.code for c in self.budget.concepts.values() if c.nature.casefold() in ('capítulo','capitulo')))
        if not accepted:
            return
        rate, accepted = QInputDialog.getText(self, 'Tipo de indirectos',
            'Porcentaje no negativo (el perfil histórico limita su precisión):', text=current['rate'] if current else '5.00')
        if not accepted:
            return
        option, accepted = QInputDialog.getItem(self, 'Partidas simples',
            'Aplicación a partidas sin descomposición:', ['Incluir', 'Excluir'],
            1 if current and current['exclude_undecomposed'] else 0, False)
        if accepted:
            config = {'profile': 'presto88_default',
                'chapter_codes': [code.strip() for code in chapters.split(',')],
                'rate': rate.strip().replace(',', '.'), 'exclude_undecomposed': option == 'Excluir'}
            self._execute('budget.indirect.set', config=config)

    def configure_root_precision(self):
        value, accepted = QInputDialog.getInt(
            self, 'Precisión de cantidades de la raíz',
            'Decimales para cantidades directamente bajo la raíz.\n'
            '−1 mantiene la precisión general (3 decimales).',
            -1 if self.budget.root_quantity_decimals is None else self.budget.root_quantity_decimals,
            -1, 12)
        if accepted:
            self._execute('budget.root.precision.set', value=None if value == -1 else value)

    def duplicate_active_concept(self):
        self.flush_text()
        if not self.active_concept:
            return
        code, ok = QInputDialog.getText(self, 'Duplicar concepto y descomposición', 'Código nuevo:')
        if ok and code.strip():
            before=self._snapshot
            self._execute('budget.concept.duplicate', code=self.active_concept, new_code=code.strip())
            if self._snapshot!=before:
                row=list(self.budget.concepts).index(code.strip())
                self.section_ui.tabs.setCurrentIndex(0);self.show_panel('conceptos')
                self.concepts_table.setCurrentCell(row,0);self.select_concept()
                self.concepts_table.scrollToItem(self.concepts_table.item(row,0))

    def move_active_relation(self):
        self.flush_text()
        if not self.selected_relation:
            self._error('Selecciona una relación en Precios')
            return
        rid=self.selected_relation
        parent, ok = QInputDialog.getItem(self, 'Mover relación', 'Superior de destino:', sorted(self.budget.concepts), 0, False)
        if not ok:
            return
        position, ok = QInputDialog.getInt(self, 'Mover relación', 'Posición:', 1, 1, 1000000)
        if ok:
            before=self._snapshot
            self._execute('budget.relation.move', relation_id=rid, parent_code=parent, position=position)
            if self._snapshot!=before:self._reveal_relation(rid)

    def replace_project_text(self):
        from .editing_services import replace_text
        search, ok = QInputDialog.getText(self, 'Reemplazar en toda la obra', 'Buscar en resúmenes y textos:')
        if not ok or not search:
            return
        replacement, ok = QInputDialog.getText(self, 'Reemplazar', 'Sustituir por:')
        if ok:
            self._execute('budget.text.replace', search=search, replacement=replacement)

    def sort_current_level(self):
        from .editing_services import reorder_children
        labels = {'Código': 'code', 'Resumen': 'summary', 'Precio': 'price', 'Cantidad': 'quantity'}
        label, ok = QInputDialog.getItem(self, 'Ordenar nivel actual', 'Campo:', list(labels), 0, False)
        if ok and self.current_code:
            self._execute('budget.children.reorder', parent=self.current_code, key=labels[label])

    def copy_relation_measurements(self):
        self.flush_text()
        relations = {f'{r.parent_code} → {r.child_code} [{r.id}]': r.id for r in self.budget.relations}
        if len(relations) < 2:
            self._error('Se necesitan dos relaciones para copiar mediciones')
            return
        source, ok = QInputDialog.getItem(self, 'Copiar mediciones', 'Origen:', list(relations), 0, False)
        if not ok:
            return
        targets = [label for label in relations if label != source]
        destination, ok = QInputDialog.getItem(self, 'Sustituir mediciones del destino', 'Destino (se sustituirán sus líneas):', targets, 0, False)
        if ok:
            rid=relations[destination];before=self._snapshot
            self._execute('budget.measurement.copy', source=relations[source], destination=rid)
            if self._snapshot!=before:
                self._reveal_relation(rid);self.show_panel('mediciones')
                row=next((i for i in range(self.measurements_table.rowCount()) if not self.measurements_table.isRowHidden(i)),None)
                if row is not None:
                    self.measurements_table.setCurrentCell(row,0)
                    self.measurements_table.scrollToItem(self.measurements_table.item(row,0))
                else:
                    self.measurements_table.clearSelection()
                    self.measurements_table.setCurrentIndex(self.measurements_table.model().index(-1,-1))

    def _workspace_setting(self, operation):
        try:
            operation(self)
        except (ValueError, OSError, TypeError) as exc:
            self._error(exc)

    def _execute(self, command, **params):
        from .commands import execute
        self._transaction(lambda: setattr(self, 'budget', execute(self.budget, command, params)))

    def _transaction(self,operation):
        self.flush_text()
        from .history_snapshots import capture_snapshot as dumps, restore_snapshot as loads
        before = dumps(self.budget)
        try:
            operation()
            self._changed()
        except (ValueError,ArithmeticError,RecursionError,KeyError,TypeError) as exc:
            self.budget = loads(before)
            self._error(exc)
            self.refresh()

    def edit_price_cell(self,item):
        if self._refreshing:
            return
        rid = item.data(Qt.ItemDataRole.UserRole)
        column,value = item.column(),item.text()
        if column in (5,6,8):
            value = input_number(value)
        relation = self.budget._relation(rid)
        if column == 6 and '%' not in relation.child_code and any(r.parent_code == relation.child_code for r in self.budget.relations):
            from decimal import Decimal
            from .locked_prices import LockedPriceCalculator
            self.flush_text()
            try:
                target = Decimal(value.strip().replace(',', '.'))
                if not target.is_finite() or target < 0:
                    raise BudgetError('El precio debe ser finito y no negativo.')
                option, accepted = QInputDialog.getItem(self, 'Precio calculado',
                    'Elige cómo aplicar el precio introducido.\n'
                    'Ajustar modifica los recursos y muestra el resultado antes de aplicarlo.',
                    ['Precio bloqueado', 'Ajustar recursos'], 0, False)
                if accepted and option == 'Precio bloqueado':
                    locks = dict(self.budget.locked_prices)
                    locks[relation.child_code] = target
                    LockedPriceCalculator(self.budget, locks).total()
                    self._execute('budget.price.lock', code=relation.child_code, value=str(target))
                elif accepted and option == 'Ajustar recursos':
                    self._apply_price_adjustment(relation.child_code, target)
            except (ValueError, ArithmeticError) as exc:
                self._error(exc)
            self.refresh()
            return
        if column in (5, 8):
            self._execute('budget.relation.edit', relation_id=rid,
                field='quantity' if column == 5 else 'factor', value=value)
        elif column in (1, 3, 4, 6):
            self._execute('budget.concept.edit', code=relation.child_code,
                changes={{1:'nature', 3:'unit', 4:'summary', 6:'base_price'}[column]:value})
        else:
            self._error('Campo de consulta.')


    def edit_measurement_cell(self,item):
        if self._refreshing:
            return
        row,column,value = item.row(),item.column(),item.text()
        key,identity = self._measurement_keys[row]
        if column in (1,2,3,4):
            value = input_number(value)
        if key == 'native':
            field = {0:'comment',1:'n_lines',2:'length',3:'width',4:'height',5:'formula'}.get(column)
            if field:
                self._execute('budget.measurement.edit', measurement_id=identity, field=field,
                    value=None if column in (2,3,4) and not value.strip() else value)
        else:
            field = {0:'description',1:'a',2:'b',3:'c',4:'d',5:'formula',8:'kind'}.get(column)
            if field:
                self._execute('budget.measurement.bc3.edit', relation_id=key, index=identity, field=field, value=value)

    def queue_text(self):
        if self._text_code is not None and not self._refreshing:
            self._text_pending = True
            self._text_timer.start()
            self._sync_actions()

    def flush_text(self):
        if not self._text_pending:
            return
        self._text_pending = False
        self._text_timer.stop()
        code,value = self._text_code,self.text_editor.toPlainText()
        if code in self.budget.concepts and self.budget.concepts[code].text != value:
            from .commands import execute
            self.budget = execute(self.budget, 'budget.concept.edit', {'code':code, 'changes':{'text':value}})
            self._changed()

    def _selected_table(self):
        if self._selection_override is not None:
            return self._selection_override
        sub = self.mdi.activeSubWindow()
        if sub is None:
            return None
        table = self.prices if sub.widget() is self.prices_widget else sub.widget()
        if table is self.prices and self.budget_stack.currentWidget() is self.budget_structure and self.selected_relation is None:return None
        if table is self.measurements_widget:table=self.measurements_table
        if table in (self.prices,self.concepts_table,self.relations_table,self.measurements_table) and table.currentRow() >= 0 and not table.isRowHidden(table.currentRow()):
            return table
        return None

    def edit_selected(self):
        self.flush_text()
        if self._selected_table() is self.prices:
            if self.budget_stack.currentWidget() is self.budget_structure:self.set_budget_view('precios')
            item = self.prices.currentItem()
            if item and item.flags() & Qt.ItemFlag.ItemIsEditable:
                self.prices.editItem(item)
            else:
                self.statusBar().showMessage('Elige Ud, Resumen, CanPres manual o PrPres; un precio calculado requiere confirmar el bloqueo.',5000)
            return
        if self._selected_table() is self.relations_table:
            old = self.budget.relations[self.relations_table.currentRow()]
            if '%' in old.child_code:
                self._error('La base porcentual es calculada; edita el tipo en Precios.')
                return
            dialog = RelationDialog(list(self.budget.concepts),self)
            dialog.setWindowTitle('Editar relación')
            dialog.parent_code.setCurrentText(old.parent_code)
            dialog.child_code.setCurrentText(old.child_code)
            dialog.quantity.setText(str(old.quantity))
            dialog.position.setText(str(old.position))
            measured = self.has_measurements(old.id) or self.budget.has_certification(old.id)
            for widget in (dialog.parent_code,dialog.child_code,dialog.position,dialog.quantity):
                widget.setEnabled(not measured)
                if measured:
                    widget.setToolTip('Esta relación tiene mediciones. Edita sus líneas para modificar la cantidad.')
            if dialog.exec() == QDialog.DialogCode.Accepted:
                from dataclasses import asdict
                self._execute_model('budget.relation.replace', dialog.get_relation, relation_id=old.id)
            return
        super().edit_selected()

    def delete_selected(self):
        table=self._selected_table()
        if table is None:return
        rows=sorted({i.row() for i in table.selectedIndexes() if not table.isRowHidden(i.row())})
        if not rows:return
        first=rows[0]
        ordinal=sum(not table.isRowHidden(i) for i in range(first))
        if table is self.measurements_table:
            params=dict(keys=[self._measurement_keys[i] for i in rows]);command='budget.measurement.remove'
        elif table is self.concepts_table:
            params=dict(codes=[table.item(i,0).text() for i in rows]);command='budget.concepts.remove'
        elif table in (self.prices,self.relations_table):
            relations=self._visible_relations if table is self.prices else self.budget.relations
            params=dict(relation_ids=[relations[i].id for i in rows]);command='budget.relations.remove'
        else:return
        self.flush_text();before=self._snapshot
        self._execute(command,**params)
        if self._snapshot==before:return
        visible=[i for i in range(table.rowCount()) if not table.isRowHidden(i)]
        if visible:
            row=visible[min(ordinal,len(visible)-1)];table.setCurrentCell(row,0);table.scrollToItem(table.item(row,0))
        else:
            table.setCurrentCell(-1,-1);table.clearSelection()
        if table is self.prices:self.select_price()
        elif table is self.concepts_table:self.select_concept()
        elif table is self.relations_table:self.select_relation()
        self._sync_actions()

    def move_measurement_line(self, delta):
        self.flush_text()
        row=self.measurements_table.currentRow()
        if not 0<=row<len(self._measurement_keys) or self.measurements_table.isRowHidden(row):return
        key,identity=self._measurement_keys[row]
        if key=='native':
            line=next(m for m in self.budget.measurements if m.id==identity);rid=line.relation_id;target=('native',identity)
        else:rid=key;target=(key,identity+delta) if type(delta) is int else (key,identity)
        before=self._snapshot
        self._execute('budget.measurement.move',kind=key,identity=identity,delta=delta)
        if self._snapshot!=before:self._reveal_measurement(target,rid)

    def add_measurement_subtotal(self, accumulated):
        from .measurement_operations import insert_subtotal
        if not self.selected_relation:
            self._error('Selecciona una relación para insertar el subtotal')
            return
        rid=self.selected_relation;before=set(self._measurement_keys)
        self._execute('budget.measurement.subtotal', relation_id=rid, accumulated=accumulated)
        added=[key for key in self._measurement_keys if key not in before]
        if added:self._reveal_measurement(added[-1],rid)

    def add_concept(self):
        self.flush_text()
        dialog=ConceptDialog(self)
        parent=self.current_code if self.current_code in self.budget.concepts else self.budget.root_code
        insert=None
        if parent is not None:
            insert=QCheckBox(f'Añadir también al presupuesto de {parent}')
            insert.setObjectName('insert-concept-in-budget')
            insert.setChecked(self._selection_origin!='conceptos')
            dialog.layout().insertRow(dialog.layout().rowCount()-1,insert)
        status=QLabel();status.setWordWrap(True);dialog.layout().insertRow(dialog.layout().rowCount()-1,status)
        fields=(dialog.unit,dialog.summary,dialog.nature,dialog.price,dialog.measurement_decimals)
        was_known=[False]
        def identify(code):
            known=self.budget.concepts.get(code.strip())
            for widget in fields:widget.setEnabled(known is None)
            if known is not None:
                for widget,value in ((dialog.unit,known.unit),(dialog.summary,known.summary),(dialog.nature,known.nature),(dialog.price,known.base_price)):widget.setText(str(value))
                dialog.measurement_decimals.setValue(-1 if known.measurement_decimals is None else known.measurement_decimals)
                status.setText('El código ya existe. Se usará el concepto del catálogo sin cambiar sus datos. Si ya figura en este nivel, se seleccionará su línea.')
            else:
                status.setText('')
                if was_known[0]:
                    for widget in (dialog.unit,dialog.summary,dialog.nature):widget.clear()
                    dialog.price.setText('0');dialog.measurement_decimals.setValue(-1)
            was_known[0]=known is not None
        dialog.code.textChanged.connect(identify)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        code=dialog.code.text().strip();known=self.budget.concepts.get(code)
        try:concept=known or dialog.get_concept()
        except (ValueError,ArithmeticError,TypeError) as exc:self._error(exc);return
        from dataclasses import asdict
        target=parent if insert is not None and insert.isChecked() else None
        if known is None:
            self._execute('budget.concept.add',data=asdict(concept),parent_code=target)
            if concept.code not in self.budget.concepts:return
        elif target is not None and not any(r.parent_code==target and r.child_code==code for r in self.budget.relations):
            quantity=concept.base_price/100 if '%' in code else '1'
            position=max((r.position for r in self.budget.relations if r.parent_code==target),default=0)+1
            self._execute('budget.relation.add',data=asdict(BudgetRelation(target,code,quantity,position)))
        self.section_ui.tabs.setCurrentIndex(0)
        if target is not None:
            relation=next((r for r in self.budget.relations if r.parent_code==target and r.child_code==concept.code),None)
            if relation is None:return
            self.search.clear()
            row=next(i for i,r in enumerate(self._visible_relations) if r.id==relation.id)
            self.show_panel('precios');self.prices.setCurrentCell(row,0);self.select_price();self.prices.scrollToItem(self.prices.item(row,0))
        else:
            row=list(self.budget.concepts).index(concept.code)
            self.show_panel('conceptos');self.concepts_table.setCurrentCell(row,0);self.select_concept();self.concepts_table.scrollToItem(self.concepts_table.item(row,0))

    def _reveal_relation(self,relation_id):
        relation=self.budget._relations_by_id.get(relation_id)
        if relation is None:return
        self.flush_text()
        if self.current_code!=relation.parent_code:self._navigation=[]
        self.current_code=relation.parent_code;self.selected_relation=relation_id;self._selection_origin='precios'
        with QSignalBlocker(self.search):self.search.clear()
        self.refresh();self.section_ui.tabs.setCurrentIndex(0);self.show_panel('precios')
        row=next(i for i,r in enumerate(self._visible_relations) if r.id==relation_id)
        self.prices.setCurrentCell(row,0);self.select_price();self.prices.scrollToItem(self.prices.item(row,0))

    def _reveal_measurement(self,key,relation_id):
        if key not in self._measurement_keys:return
        self._reveal_relation(relation_id)
        row=self._measurement_keys.index(key);self.show_panel('mediciones')
        self.measurements_table.setCurrentCell(row,0);self.measurements_table.scrollToItem(self.measurements_table.item(row,0))

    def add_relation(self):
        self.flush_text()
        if len(self.budget.concepts)<2:
            self._error('Añade al menos dos conceptos antes de crear relaciones');return
        dialog=RelationDialog(list(self.budget.concepts),self)
        if self.current_code:
            dialog.parent_code.setCurrentText(self.current_code)
            dialog.position.setText(str(max((r.position for r in self.budget.relations if r.parent_code==self.current_code),default=0)+1))
        if self.active_concept and self.active_concept!=self.current_code:dialog.child_code.setCurrentText(self.active_concept)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        try:relation=dialog.get_relation()
        except (ValueError,ArithmeticError,TypeError) as exc:self._error(exc);return
        self._execute_model('budget.relation.add',lambda:relation)
        if relation.id in self.budget._relations_by_id:self._reveal_relation(relation.id)

    def add_measurement(self):
        self.flush_text();rid=self.selected_relation
        if not rid:self._error('Selecciona la partida en Precios para asociar su medición.');return
        if rid in self.budget.bc3_measurements:
            self.edit_bc3_line(rid);return
        dialog=MeasurementDialog(self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        try:line=dialog.get_measurement(rid)
        except (ValueError,ArithmeticError,TypeError) as exc:self._error(exc);return
        self._execute_model('budget.measurement.add',lambda:line)
        self._reveal_measurement(('native',line.id),rid)

    def edit_bc3_line(self,relation_id,index=None):
        before=self._snapshot
        super().edit_bc3_line(relation_id,index)
        if self._snapshot!=before:
            target=len(self.budget.bc3_measurements[relation_id].lines)-1 if index is None else index
            self._reveal_measurement((relation_id,target),relation_id)

    def enter_concept(self,row,column):
        if column not in (0,2) or not 0 <= row < len(self._visible_relations) or self.prices.isRowHidden(row):
            return
        self.flush_text()
        relation = self._visible_relations[row]
        if any(r.parent_code == relation.child_code for r in self.budget.relations):
            self._navigation.append((self.current_code,relation.id,self.search.text()))
            with QSignalBlocker(self.search):self.search.clear()
            self._selection_origin = 'precios'
            self.current_code = relation.child_code
            self.selected_relation = None
            self.refresh()

    def go_up(self):
        self.flush_text()
        self._selection_origin = 'precios'
        if self._navigation:
            step=self._navigation.pop()
            self.current_code,self.selected_relation = step[:2]
            query=step[2] if len(step)>2 else ''
        else:
            self.current_code = self.budget.root_code
            self.selected_relation = None
            query=''
        with QSignalBlocker(self.search):self.search.setText(query)
        self.refresh()

    def go_root(self):
        self._navigation = []
        self.go_up()

    def save(self):
        self.flush_text()
        saved = super().save()
        if saved:
            from .session_services import cleanup_recovery
            cleanup_recovery(self)
        return saved

    def _history_context(self):
        if not self._ready:return None
        item=self.concepts_table.item(self.concepts_table.currentRow(),0)
        row=self.measurements_table.currentRow()
        measurement=self._measurement_keys[row] if 0<=row<len(self._measurement_keys) else None
        active=self.mdi.activeSubWindow()
        pane=next((key for key,window in self.windows.items() if window is active),None)
        return _ViewState(self.current_code,item.text() if item else None,self.selected_relation,
                          self._selection_origin,tuple(self._navigation),self.search.text(),measurement,
                          self.section_ui.tabs.currentIndex(),pane,self.panels['gestion'][1].tabs.currentIndex())

    def _restore_history_context(self,context):
        if not isinstance(context,_ViewState):return
        self.current_code=context.parent if context.parent in self.budget.concepts else self.budget.root_code
        self.selected_relation=context.relation if context.relation in self.budget._relations_by_id else None
        self._selection_origin=context.origin
        self._navigation=[step for step in context.navigation if step[0] in self.budget.concepts and (step[1] is None or step[1] in self.budget._relations_by_id)]
        with QSignalBlocker(self.search):self.search.setText(context.search)
        self.refresh()
        if 0<=context.section<self.section_ui.tabs.count():self.section_ui.tabs.setCurrentIndex(context.section)
        if context.origin=='conceptos' and context.concept in self.budget.concepts:
            row=list(self.budget.concepts).index(context.concept);self.concepts_table.setCurrentCell(row,0);self.select_concept();self.concepts_table.scrollToItem(self.concepts_table.item(row,0))
        elif context.origin=='relaciones' and context.relation in self.budget._relations_by_id:
            row=next(i for i,r in enumerate(self.budget.relations) if r.id==context.relation);self.relations_table.setCurrentCell(row,0);self.select_relation();self.relations_table.scrollToItem(self.relations_table.item(row,0))
        elif context.origin=='precios':
            self.select_price()
            if self.prices.currentRow()>=0:self.prices.scrollToItem(self.prices.item(self.prices.currentRow(),0))
        if context.measurement in self._measurement_keys:
            row=self._measurement_keys.index(context.measurement)
            if not self.measurements_table.isRowHidden(row):self.measurements_table.setCurrentCell(row,0);self.measurements_table.scrollToItem(self.measurements_table.item(row,0))
        manager=self.panels['gestion'][1]
        if 0<=context.management_tab<manager.tabs.count():manager.tabs.setCurrentIndex(context.management_tab)
        from .section_workspace import AREAS
        matching=0<=context.section<len(AREAS) and context.pane==AREAS[context.section][1]
        if context.pane in self.panels and (context.section==0 or matching or (context.section==1 and context.pane in ('certificacion','certificacion-fases'))):self.show_panel(context.pane)
        self._sync_actions()

    def undo(self):
        self.flush_text()
        frame=self._undo[-1] if self._undo else None
        super().undo()
        if frame is not None:self._restore_history_context(getattr(frame,'context',None))

    def redo(self):
        self.flush_text()
        frame=self._redo[-1] if self._redo else None
        super().redo()
        if frame is not None:self._restore_history_context(getattr(frame,'context',None))

    def _confirm_discard(self):
        self.flush_text()
        return super()._confirm_discard()

    def recalculate(self):
        self.flush_text()
        try:
            self.refresh()
            self.statusBar().showMessage('Precios e importes recalculados con el perfil actual.',5000)
        except (ValueError,ArithmeticError) as exc:
            self._error(exc)

    def _about(self):
        QMessageBox.information(self,'OpenPresto',f'OpenPresto {__version__}\nPresupuestos, mediciones, certificación, planificación y gestión de obra.\nGPL-3.0-or-later. Versión de prueba; compatibilidad BC3 y PZH parcial.')
