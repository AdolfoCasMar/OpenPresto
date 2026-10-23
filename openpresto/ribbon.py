"""Office-style compact ribbon backed by existing commands and views."""
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (QToolBar, QWidget, QVBoxLayout, QHBoxLayout,
    QToolButton, QLabel, QScrollArea, QFrame, QTabWidget, QMenu)
from .ui_icons import icon


class ReferenceRibbon(QToolBar):
    def __init__(self, host):
        super().__init__('Cinta de herramientas', host)
        self.host = host
        self.setObjectName('cinta-vistas'); self.setMovable(False)
        self.pages = QTabWidget(); self.pages.setDocumentMode(True)
        self.pages.setFixedHeight(120);self.pages.setObjectName('cinta-2026');self.project_groups=[];self.buttons={}
        # Entries: label, original icon, command key or panel[:tab index].
        definitions = (
            ('Inicio', (
                ('Editar', (('Pegar','copy','Pegar'), ('Eliminar','delete','Eliminar'), ('Copiar','copy','Copiar'))),
                ('Deshacer', (('Deshacer','undo','Deshacer'), ('Rehacer','redo','Rehacer'))),
                ('Añadir', (('Concepto','add','Añadir concepto…'), ('Relación','link','Insertar relación…'), ('Medición','measure','Introducir medición…'))),
                ('Localizar', (('Buscar','search','Buscar'),)),
                ('Calcular', (('Recalcular','calculate','Calcular todo'),)),
                ('Informes', (('Informes','text','informes'),)),
            )),
            ('Ver', (
                ('Obra', (('Propiedades','settings','Propiedades obra'),)),
                ('Presupuesto', (('Árbol','tree','budget:arbol'), ('Presupuesto','budget','budget:precios'), ('Conceptos','concepts','conceptos'), ('Capítulos','chapters','budget:capitulos'), ('Capítulos y partidas','chapter-items','budget:capitulos-partidas'))),
                ('Gestión', (('Entidades','parties','gestion:entities'),)),
                ('Planificación', (('Agenda','agenda','planificacion:agenda'),('Fechas','calendar','planificacion:0'), ('Diagrama de barras','gantt','planificacion:3'), ('Precedencias','precedence','planificacion:4'), ('Recursos','resources','planificacion:2'), ('Fechas e importes','phases','planificacion:6'))),
                ('Listas', (('Archivos','attachments','gestion:technical_documents:assets'),('Relaciones','link','relaciones'),('Mediciones','measure','mediciones'), ('Texto','text','texto'),('Certificaciones','calendar','certificacion-fases'))),
                ('Documentos', (('Contratos','contract','gestion:1'), ('Ofertas','offer','gestion:2'), ('Pedidos','orders','purchase:order'), ('Entregas','deliveries','purchase:delivery'), ('Partes de obra','phases','gestion:production'),('Facturas','invoices','purchase:invoice'),('Suministros','supplies','gestion:4'), ('Vencimientos','dues','gestion:7'))),
                ('Mensajes', (('Avisos','help','avisos'),)),
            )),
            ('Herramientas', (
                ('Intercambio', (('Importar BC3','import','importar'), ('Importar PZH','import','Presto PZH · experimental…'), ('Exportar BC3','export','exportar'))),
                ('Obra', (('Documentos','link','Vincular documento…'), ('Preferencias','settings','Preferencias…'))),
            )),
            ('Seguimiento', (
                ('Ejecución', (('Partes de obra','measure','gestion:production'),('Horas y equipos','calendar','gestion:resource_hours'),('Rendimientos','calculate','gestion:productivity'))),
                ('Calidad', (('Controles','calculate','gestion:quality_control'),('No conformidades','link','gestion:nonconformities'),('Incidencias','text','gestion:site_issues'),('Documentación','text','gestion:technical_documents'))),
                ('Control económico', (('Líneas base','copy','gestion:budget_baselines'),('Mediciones por fases','measure','gestion:budget_phase_measurements'),('Costes','calculate','gestion:cost_control'),('Inventario','tree','gestion:inventory_control'),('Tesorería','calendar','gestion:treasury'),('Retenciones','calendar','gestion:retention_openings'),('Compras','open','gestion:procurement_tracking'),('Emitidos','invoices','gestion:9'),('Valor ganado','calculate','planificacion:7'))),
            )),
        )
        for title, groups in definitions:
            scroll = QScrollArea(); scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            body = QWidget(); row = QHBoxLayout(body)
            row.setContentsMargins(3, 0, 3, 0); row.setSpacing(0)
            self.project_groups.append(body)
            for group_title, entries in groups:
                group = QWidget(); column = QVBoxLayout(group)
                column.setContentsMargins(3, 0, 3, 0); column.setSpacing(0)
                buttons = QHBoxLayout(); buttons.setSpacing(1)
                for label, symbol, key in entries:
                    button = QToolButton(); button.setIconSize(QSize(22,22))
                    button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
                    button.setFixedHeight(65);button.setObjectName('ribbon-'+key);button.setAccessibleName(label)
                    if key in host.commands:
                        action = host.commands[key][0]
                        button.setText(label); button.setIcon(icon(symbol))
                        button.setEnabled(action.isEnabled())
                        button.clicked.connect(lambda checked=False, action=action: action.trigger())
                        action.changed.connect(lambda button=button, action=action: button.setEnabled(action.isEnabled()))
                    else:
                        button.setText(label); button.setIcon(icon(symbol))
                        button.clicked.connect(lambda checked=False, key=key:self.show_view(key))
                    words=label.split();lines=['']
                    for word in words:
                        if lines[-1] and len(lines[-1]+' '+word)>12:lines.append(word)
                        else:lines[-1]=(lines[-1]+' '+word).strip()
                    button.setText('\n'.join(lines));button.setFixedWidth(max(44,min(82,max(button.fontMetrics().horizontalAdvance(line) for line in lines)+10)))
                    button.setToolTip(label);buttons.addWidget(button);self.buttons[key]=button
                    if key.startswith('budget:') or key=='conceptos':button.setCheckable(True)
                column.addLayout(buttons)
                caption = QLabel(group_title); caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
                caption.setStyleSheet('color: #596575; font-size: 10px;')
                column.addWidget(caption); row.addWidget(group)
                divider=QFrame(); divider.setFrameShape(QFrame.Shape.VLine)
                divider.setStyleSheet('color: #c9cdd3;'); row.addWidget(divider)
            row.addStretch(); scroll.setWidget(body); self.pages.addTab(scroll,title)
        self.pages.setCurrentIndex(1)
        file=QToolButton();file.setText('Archivo');file.setMenu(host.menus['Archivo']);file.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup);self.pages.setCornerWidget(file,Qt.Corner.TopLeftCorner)
        menus=QWidget();menu_row=QHBoxLayout(menus);menu_row.setContentsMargins(0,0,3,0);menu_row.setSpacing(1)
        for label,name in (('Menús',None),('Informes','Informes'),('Ventanas','Ventana'),('Ayuda','?')):
            button=QToolButton();button.setText(label);button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            if name:button.setMenu(host.menus[name])
            else:
                more=QMenu(button)
                for menu_name,menu in host.menus.items():
                    if menu_name not in ('Archivo','Informes','Ventana','?'):more.addMenu(menu)
                button.setMenu(more)
            menu_row.addWidget(button)
        self.pages.setCornerWidget(menus,Qt.Corner.TopRightCorner)
        self.addWidget(self.pages)

    def set_project_open(self,opened):
        for body in self.project_groups:body.setEnabled(opened)
        self.sync_views()

    def sync_views(self):
        for key,button in self.buttons.items():
            if key.startswith('budget:'):button.setChecked(self.host.project_open and self.host.section_ui.active==0 and key.split(':')[1]==self.host.budget_view.currentData())
            elif key=='conceptos':button.setChecked('conceptos' in self.host.windows and self.host.windows['conceptos'].isVisible())

    def show_view(self, target):
        if target.startswith('budget:'):
            self.host.section_ui.tabs.setCurrentIndex(0);self.host.set_budget_view(target.split(':')[1]);self.host.show_panel('precios');return
        if target.startswith('purchase:'):
            self.show_view('gestion:3');self.host.management_panel.set_document_filter(target.split(':')[1]);return
        parts=target.split(':')
        key, _, tab = target.partition(':')
        area = {'planificacion':2, 'gestion':3, 'informes':4, 'certificacion-fases':1, 'certificacion':1}.get(key,0)
        self.host.section_ui.tabs.setCurrentIndex(area)
        self.host.show_panel(key)
        if area: self.host.windows[key].showMaximized()
        if tab:
            panel=self.host.panels[key][1]
            if len(parts)>2:
                panel.tabs.setCurrentWidget(getattr(panel,parts[1]));child=getattr(panel,parts[1]);child.tabs.setCurrentWidget(getattr(child,parts[2]));return
            if tab.isdecimal():panel.tabs.setCurrentIndex(int(tab))
            else:panel.tabs.setCurrentWidget(getattr(panel,tab))
