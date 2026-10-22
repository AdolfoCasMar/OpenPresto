"""Office-style compact ribbon backed by existing commands and views."""
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (QToolBar, QWidget, QVBoxLayout, QHBoxLayout,
    QToolButton, QLabel, QScrollArea, QFrame, QTabWidget)
from .ui_icons import icon


class ReferenceRibbon(QToolBar):
    def __init__(self, host):
        super().__init__('Cinta de herramientas', host)
        self.host = host
        self.setObjectName('cinta-vistas'); self.setMovable(False)
        self.pages = QTabWidget(); self.pages.setDocumentMode(True)
        self.pages.setFixedHeight(121)
        # Entries: label, original icon, command key or panel[:tab index].
        definitions = (
            ('Inicio', (
                ('Editar', (('Pegar','copy','Pegar'), ('Copiar','copy','Copiar'), ('Eliminar','delete','Eliminar'))),
                ('Deshacer', (('Deshacer','undo','Deshacer'), ('Rehacer','redo','Rehacer'))),
                ('Añadir', (('Concepto','add','Añadir concepto…'), ('Relación','link','Insertar relación…'), ('Medición','measure','Introducir medición…'))),
                ('Localizar', (('Buscar','search','Buscar'),)),
                ('Calcular', (('Recalcular','calculate','Calcular todo'),)),
                ('Informes', (('Informes','text','informes'),)),
            )),
            ('Ver', (
                ('Obra', (('Propiedades','settings','Propiedades obra'),)),
                ('Presupuesto', (('Precios','calculate','precios'), ('Conceptos','work','conceptos'), ('Árbol','tree','arbol'), ('Capítulos','chapters','capitulos'), ('Capítulos y partidas','chapter-items','capitulos-partidas'), ('Relaciones','link','relaciones'))),
                ('Gestión', (('Entidades','tree','gestion:10'),)),
                ('Planificación', (('Fechas','calendar','planificacion:0'), ('Diagrama','calendar','planificacion:3'), ('Precedencias','link','planificacion:4'), ('Recursos','tree','planificacion:2'), ('Fases e importes','calculate','planificacion:6'), ('Valor ganado','calculate','planificacion:7'))),
                ('Listas', (('Mediciones','measure','mediciones'), ('Texto','text','texto'))),
                ('Certificación', (('Por fases','calendar','certificacion-fases'), ('A origen','calculate','certificacion'))),
                ('Documentos', (('Contratos','open','gestion:1'), ('Ofertas','calculate','gestion:2'), ('Documentos','copy','gestion:3'), ('Suministros','tree','gestion:4'), ('Vencimientos','calendar','gestion:7'), ('Emitidos','copy','gestion:9'))),
                ('Mensajes', (('Avisos','help','avisos'),)),
            )),
            ('Herramientas', (
                ('Intercambio', (('Importar BC3','import','importar'), ('Importar PZH','import','Presto PZH · experimental…'), ('Exportar BC3','export','exportar'))),
                ('Obra', (('Documentos','link','Vincular documento…'), ('Preferencias','settings','Preferencias…'))),
            )),
            ('Seguimiento', (
                ('Ejecución', (('Partes de obra','measure','gestion:production'),('Horas y equipos','calendar','gestion:resource_hours'),('Rendimientos','calculate','gestion:productivity'))),
                ('Calidad', (('Controles','calculate','gestion:quality_control'),('No conformidades','link','gestion:nonconformities'),('Incidencias','text','gestion:site_issues'),('Documentación','text','gestion:technical_documents'))),
                ('Control económico', (('Líneas base','copy','gestion:budget_baselines'),('Mediciones por fases','measure','gestion:budget_phase_measurements'),('Costes','calculate','gestion:cost_control'),('Inventario','tree','gestion:inventory_control'),('Tesorería','calendar','gestion:treasury'),('Retenciones','calendar','gestion:retention_openings'),('Compras','open','gestion:procurement_tracking'))),
            )),
        )
        for title, groups in definitions:
            scroll = QScrollArea(); scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            body = QWidget(); row = QHBoxLayout(body)
            row.setContentsMargins(3, 0, 3, 0); row.setSpacing(3)
            for group_title, entries in groups:
                group = QWidget(); column = QVBoxLayout(group)
                column.setContentsMargins(3, 0, 3, 0); column.setSpacing(0)
                buttons = QHBoxLayout(); buttons.setSpacing(1)
                for label, symbol, key in entries:
                    button = QToolButton(); button.setIconSize(QSize(22,22))
                    button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
                    button.setMinimumHeight(54)
                    if key in host.commands:
                        action = host.commands[key][0]
                        button.setText(label); button.setIcon(icon(symbol))
                        button.setEnabled(action.isEnabled())
                        button.clicked.connect(lambda checked=False, action=action: action.trigger())
                        action.changed.connect(lambda button=button, action=action: button.setEnabled(action.isEnabled()))
                    else:
                        button.setText(label); button.setIcon(icon(symbol))
                        button.clicked.connect(lambda checked=False, key=key:self.show_view(key))
                    button.setToolTip(label); buttons.addWidget(button)
                column.addLayout(buttons)
                caption = QLabel(group_title); caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
                caption.setStyleSheet('color: #596575; font-size: 10px;')
                column.addWidget(caption); row.addWidget(group)
                divider=QFrame(); divider.setFrameShape(QFrame.Shape.VLine)
                divider.setStyleSheet('color: #c9cdd3;'); row.addWidget(divider)
            row.addStretch(); scroll.setWidget(body); self.pages.addTab(scroll,title)
        self.pages.setCurrentIndex(1)
        self.addWidget(self.pages)

    def show_view(self, target):
        key, _, tab = target.partition(':')
        area = {'planificacion':2, 'gestion':3, 'informes':4, 'certificacion-fases':1, 'certificacion':1}.get(key,0)
        self.host.section_ui.tabs.setCurrentIndex(area)
        self.host.show_panel(key)
        if area: self.host.windows[key].showMaximized()
        if tab:
            panel=self.host.panels[key][1]
            if tab.isdecimal():panel.tabs.setCurrentIndex(int(tab))
            else:panel.tabs.setCurrentWidget(getattr(panel,tab))
