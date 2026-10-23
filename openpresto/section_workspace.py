"""Task sections, contextual actions and persistent tree around the MDI client."""
from PySide6.QtCore import Qt,QSignalBlocker,QSize,QSettings
from PySide6.QtWidgets import (QToolBar,QTabBar,QDockWidget,QTreeWidget,QTreeWidgetItem,
    QStackedWidget,QWidget,QVBoxLayout,QPushButton,QLabel)
from .ui_icons import icon

AREAS=(('Presupuesto','precios'),('Certificaciones','certificacion-fases'),('Planificación','planificacion'),('Gestión','gestion'),('Informes','informes'))


class SectionWorkspace:
    def __init__(self,host):
        self.host=host;self.active=0;self.fingerprint=None;self.was_open=False
        bar=host.findChildren(QToolBar)[0]
        for action in list(bar.actions()):bar.removeAction(action)
        bar.setWindowTitle('Acceso rápido');bar.setIconSize(QSize(16,16));bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly);bar.setMovable(False);bar.setFixedHeight(27)
        bar.setStyleSheet('QToolBar { background: #c5cfde; padding: 0 5px; spacing: 2px; } QToolButton { padding: 2px; }')
        for key in ('Guardar','Preferencias…','Deshacer','Rehacer','Nuevo','Abrir…','importar','Presto PZH · experimental…','Buscar'):
            if key not in host.commands:continue
            if key in ('Deshacer','Buscar'):bar.addSeparator()
            action=host.commands[key][0];action.setIconText({'Abrir…':'Abrir','importar':'BC3','Presto PZH · experimental…':'PZH'}.get(key,key));bar.addAction(action)
        bar.addSeparator()
        for key,label,symbol in (('precios','Precios','calculate'),('conceptos','Conceptos','work'),('arbol','Árbol','tree'),('capitulos','Capítulos','chapters'),('capitulos-partidas','Capítulos y partidas','chapter-items')):
            action=host.commands['ver-'+key][0];action.setIcon(icon(symbol));action.setIconText(label)
            bar.addAction(action)
        from .ribbon import ReferenceRibbon
        self.ribbon = ReferenceRibbon(host)
        host.addToolBarBreak()
        host.addToolBar(self.ribbon)
        area=QToolBar('Secciones',host);area.setObjectName('secciones');area.setMovable(False);host.addToolBar(Qt.ToolBarArea.BottomToolBarArea,area);self.tabs=QTabBar();self.tabs.setExpanding(False)
        area.setStyleSheet('QToolBar { padding: 0; spacing: 0; } QTabBar::tab { padding: 3px 8px; }')
        for title,key in AREAS:self.tabs.addTab(icon({'precios':'calculate','certificacion-fases':'calendar','planificacion':'calendar','gestion':'open','informes':'text'}[key]),title)
        area.addWidget(self.tabs);self.tabs.currentChanged.connect(self.activate)
        self.context=QToolBar('Herramientas de la sección',host);self.context.setObjectName('herramientas-seccion');self.context.setIconSize(QSize(14,14));self.context.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon);self.context.setMovable(False);host.addToolBar(Qt.ToolBarArea.BottomToolBarArea,self.context)
        host.menuBar().hide()
        host.addActions([entry[0] for entry in host.commands.values()])
        self.tree=QTreeWidget();self.tree.setHeaderLabels(('Código','Capítulo / partida'));self.tree.setColumnWidth(0,105);self.tree.itemClicked.connect(self.navigate)
        self.dock=QDockWidget('Estructura de la obra',host);self.dock.setObjectName('estructura-obra');self.dock.setWidget(self.tree);self.dock.hide();host.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea,self.dock);host.resizeDocks([self.dock],[265],Qt.Orientation.Horizontal)
        host.menus['Ver'].addAction(self.dock.toggleViewAction())
        self.stack=QStackedWidget();host.takeCentralWidget();self.stack.addWidget(host.mdi)
        welcome=QWidget();layout=QVBoxLayout(welcome);layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title=QLabel('OpenPresto\nPresupuestos, certificación, planificación y gestión');title.setWordWrap(True);title.setAlignment(Qt.AlignmentFlag.AlignCenter);layout.addWidget(title)
        for text,symbol,callback in (('Nueva obra','new',host.new_budget),('Abrir proyecto','open',host.open_budget),('Importar Presto PZH','import',host.import_pzh_budget),('Importar BC3','import',host.import_budget),('Probar planificación y gestión','calendar',host.open_modules_demo)):
            b=QPushButton(text);b.setIcon(icon(symbol));b.clicked.connect(callback);layout.addWidget(b)
        self.stack.addWidget(welcome);host.setCentralWidget(self.stack);self.configure_context()

    def configure_context(self):
        for action in list(self.context.actions()):self.context.removeAction(action)
        keys={0:('Añadir concepto…','Insertar relación…','Introducir medición…','Calcular todo','ver-texto','ver-mediciones'),1:('ver-certificacion-fases','ver-certificacion'),2:(),3:(),4:()}.get(self.active,())
        for key in keys:
            action=self.host.commands[key][0];action.setIconText({'ver-texto':'Texto','ver-mediciones':'Mediciones','ver-certificacion-fases':'Por periodos','ver-certificacion':'A origen'}.get(key,action.iconText()));self.context.addAction(action)

    def activate(self,index):
        if not self.host.project_open:return
        if self.active==0 and not self.host._reference_layout:
            self._budget_geometry={key:window.geometry() for key,window in self.host.windows.items() if key in ('precios','conceptos','mediciones','texto')}
        self.host.flush_text();self.active=index;self.configure_context()
        for window in self.host.windows.values():window.hide()
        if index==0:
            saved=getattr(self,'_budget_geometry',{})
            if not self.host._reference_layout and all(key in saved for key in ('precios','conceptos','mediciones','texto')):
                for key,rect in saved.items():
                    self.host.show_panel(key);self.host.windows[key].showNormal();self.host.windows[key].setGeometry(rect)
            else:self.host.default_layout()
        else:
            key=AREAS[index][1];self.host.show_panel(key);self.host.windows[key].showMaximized()
        self.render_active()

    def render_active(self):
        if not self.host.project_open:return
        key=AREAS[self.active][1]
        if key in ('planificacion','gestion','informes'):
            panel=self.host.panels[key][1]
            stamp=(self.host.budget,self.host._snapshot,QSettings().value('numbers/decimal_separator','.',type=str))
            previous=getattr(panel,'_rendered_project',None)
            if previous is None or previous[0] is not stamp[0] or previous[1:]!=stamp[1:]:
                panel.render()
                panel._rendered_project=stamp

    def refresh(self):
        host=self.host;self.ribbon.set_project_open(host.project_open);self.tabs.setEnabled(host.project_open);self.context.setVisible(host.project_open);self.stack.setCurrentIndex(0 if host.project_open else 1)
        if host.project_open != self.was_open:
            self.dock.hide();self.was_open=host.project_open
        if not host.project_open:self.fingerprint=None;self.tree.clear();return
        fingerprint=(host.budget.root_code,tuple((c.code,c.summary,c.nature) for c in host.budget.concepts.values()),tuple((r.id,r.parent_code,r.child_code,r.position) for r in host.budget.relations))
        if fingerprint!=self.fingerprint:
            expanded={self.tree.topLevelItem(i).data(0,Qt.ItemDataRole.UserRole) for i in range(self.tree.topLevelItemCount()) if self.tree.topLevelItem(i).isExpanded()}
            blocker=QSignalBlocker(self.tree);self.tree.clear();children={}
            for relation in host.budget.relations:children.setdefault(relation.parent_code,[]).append(relation)
            root=host.budget.root_code;count=[0]
            def append(parent,code,visiting):
                if code in visiting or len(visiting)>128:return
                for relation in sorted(children.get(code,()),key=lambda r:r.position):
                    if count[0]>=30000:return
                    count[0]+=1;concept=host.budget.concepts[relation.child_code];item=QTreeWidgetItem(parent,[concept.code,concept.summary]);item.setData(0,Qt.ItemDataRole.UserRole,relation.id)
                    from .concept_appearance import style_code
                    style_code(item,concept,host.budget.root_code,0);append(item,concept.code,visiting|{code})
            if root:
                concept=host.budget.concepts[root];item=QTreeWidgetItem(self.tree,[root,concept.summary]);item.setData(0,Qt.ItemDataRole.UserRole,None);append(item,root,set());self.tree.expandToDepth(1)
                from .concept_appearance import style_code
                style_code(item,concept,root,0)
                if count[0]>=30000:item.setToolTip('Árbol limitado a 30.000 apariciones; navega el resto desde la tabla de presupuesto.')
            self.fingerprint=fingerprint;del blocker
        self.render_active()

    def navigate(self,item,column):
        host=self.host;rid=item.data(0,Qt.ItemDataRole.UserRole);host.flush_text()
        if rid:
            relation=host.budget._relation(rid);host.current_code=relation.parent_code;host.selected_relation=rid
        else:host.current_code=host.budget.root_code;host.selected_relation=None
        host._selection_origin='precios';host._navigation=[];host.refresh()
        if self.active==1 and rid in host.certification_phase_panel.ids:
            host.certification_phase_panel.table.setCurrentCell(host.certification_phase_panel.ids.index(rid),0)
        if self.active in (2,3,4):return
        if self.active==0:host.show_panel('precios')
