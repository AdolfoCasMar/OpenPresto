"""Read-only structural views over the current native budget."""
from PySide6.QtCore import Qt, QSettings, QSignalBlocker
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem, QHeaderView, QApplication
from .calculations import calculator_for, calculation_batch
from .concept_appearance import code_kind, style_code
from .number_format import formatter
from .ui_icons import nature_icon


class BudgetStructureView(QWidget):
    def __init__(self, host, mode, embedded=False):
        super().__init__(host)
        self.host=host; self.mode=mode; self._stamp=None;self.embedded=embedded;self.items={};self._paths_by_relation={};self._selecting=False
        layout=QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0);layout.setSpacing(0)
        self.note=QLabel('Doble clic para abrir el concepto en Precios. Los colores identifican el tipo de concepto.')
        self.note.setWordWrap(True); layout.addWidget(self.note)
        self.note.setVisible(not embedded)
        self.tree=QTreeWidget(); self.tree.setHeaderLabels(('Código','Nat','Resumen','CanPres','Ud','Pres','ImpPres'))
        self.tree.setColumnWidth(0,190);self.tree.setColumnWidth(1,34);self.tree.setColumnWidth(3,78);self.tree.setColumnWidth(4,42);self.tree.setColumnWidth(5,78);self.tree.setColumnWidth(6,98)
        self.tree.header().setStretchLastSection(False);self.tree.header().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch)
        self.tree.setUniformRowHeights(True); self.tree.setAlternatingRowColors(True)
        self.tree.setStyleSheet('QTreeView::item { min-height: 25px; }')
        self.tree.itemDoubleClicked.connect(self.navigate); layout.addWidget(self.tree)
        self.tree.currentItemChanged.connect(self.select)

    def render(self):
        host=self.host
        stamp=(host.budget, host._snapshot, QSettings().value('numbers/decimal_separator','.',type=str))
        if self._stamp and self._stamp[0] is stamp[0] and self._stamp[1:]==stamp[1:]:return
        display=formatter(stamp[2])
        current=self.tree.currentItem();selected=current.data(0,Qt.ItemDataRole.UserRole) if current else None
        expanded={path for path,item in self.items.items() if item.isExpanded()}
        first=self._stamp is None
        if first:selected=None;expanded=set();self._filter_query=''
        blocker=QSignalBlocker(self.tree); self.tree.clear();self.items={};self._paths_by_relation={}
        budget=host.budget; root=budget.root_code; children={}
        for relation in budget.relations:children.setdefault(relation.parent_code,[]).append(relation)
        for rows in children.values():rows.sort(key=lambda r:r.position)
        calc=calculator_for(budget); count=0; limited=False
        def add(parent,code,ancestors,path):
            nonlocal count,limited
            if code in ancestors or len(ancestors)>=128:return
            for relation in children.get(code,()):
                concept=budget.concepts[relation.child_code]; kind=code_kind(concept,root)
                allowed=self.mode=='arbol' or kind=='capitulo' or (self.mode=='capitulos-partidas' and kind=='partida')
                next_path=path+(relation.id,)
                if not allowed:
                    # Traverse unclassified grouping nodes without presenting them
                    # as a verified chapter or work item.
                    if kind=='otro':add(parent,concept.code,ancestors|{code},next_path)
                    continue
                if count>=30000:limited=True;return
                count+=1; value=calc.relation(relation.id)
                item=QTreeWidgetItem(parent,(concept.code,'',concept.summary,
                    display(value.quantity),concept.unit,display(value.unit_price),display(value.amount)))
                item.setData(0,Qt.ItemDataRole.UserRole,next_path)
                self.items[next_path]=item
                self._paths_by_relation.setdefault(relation.id,[]).append(next_path)
                item.setIcon(1,nature_icon(concept.nature));item.setToolTip(1,concept.nature);style_code(item,concept,root,0)
                from PySide6.QtGui import QColor
                if kind=='capitulo':
                    for col in range(7):
                        item.setBackground(col,QColor('#cbd4e2'));font=item.font(col);font.setBold(True);item.setFont(col,font)
                for col in (3,5):item.setForeground(col,QColor('#c445cc'))
                item.setBackground(6,QColor('#fffde5'))
                for col in (3,5,6):item.setTextAlignment(col,Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
                # Work-item resources only belong in the complete tree.
                if self.mode=='arbol' or kind=='capitulo':add(item,concept.code,ancestors|{code},next_path)
        with calculation_batch(calc):
            if root:
                if self.mode=='arbol':
                    concept=budget.concepts[root]
                    item=QTreeWidgetItem(self.tree,(root,'',concept.summary,'1','','',display(calc.total())))
                    item.setData(0,Qt.ItemDataRole.UserRole,());style_code(item,concept,root,0)
                    self.items[()]=item
                    add(item,root,set(),())
                else:add(self.tree,root,set(),())
        if first:self.tree.expandToDepth(1)
        else:
            for path in expanded:
                if path in self.items:self.items[path].setExpanded(True)
        if selected in self.items:self.tree.setCurrentItem(self.items[selected])
        self.note.setText(('Vista limitada a 30.000 apariciones. ' if limited else '')+
            'Doble clic para abrir en Precios. Vista de consulta; edita desde el presupuesto.')
        self.note.setVisible(not self.embedded or limited)
        self._stamp=stamp;del blocker

    def select(self,item,previous=None):
        if self._selecting or item is None or not self.host.project_open:return
        path=item.data(0,Qt.ItemDataRole.UserRole)
        if path is None:return
        self._selecting=True
        try:
            host=self.host;host.flush_text();host._selection_origin='precios'
            if path:
                relation=host.budget._relation(path[-1]);host.current_code=relation.parent_code;host.selected_relation=relation.id
                host._navigation=[(host.budget._relation(rid).parent_code,rid,'') for rid in path[:-1]]
                host.refresh()
            else:
                host.current_code=host.budget.root_code;host.selected_relation=None;host.active_concept=host.budget.root_code;host._navigation=[];host.sync_secondary()
        finally:self._selecting=False

    def sync_selection(self):
        rid=self.host.selected_relation
        current=self.tree.currentItem();path=current.data(0,Qt.ItemDataRole.UserRole) if current else None
        if path and path[-1]==rid:return
        if rid:
            prefix=tuple(row[1] for row in self.host._navigation)
            paths=self._paths_by_relation.get(rid,())
            preferred=next((p for p in paths if p[:-1]==prefix),paths[0] if paths else None)
            if preferred:
                block=QSignalBlocker(self.tree);self.tree.setCurrentItem(self.items[preferred]);del block

    def filter(self,query):
        query=query.strip().casefold()
        stamp=(self._stamp,query)
        if getattr(self,'_filter_stamp',None)==stamp:return
        if query and not getattr(self,'_filter_query',''):
            self._filter_expanded={path for path,item in self.items.items() if item.isExpanded()}
        matches=set()
        if query:
            for path,item in self.items.items():
                words=' '.join(self.host._budget_search_terms.get(item.text(0),()))
                if query in (item.text(0)+' '+item.text(2)+' '+words).casefold():matches.add(path)
        visible=set(matches)
        self._matching_paths=[path for path in self.items if path in matches]
        for path in matches:
            for depth in range(len(path)):visible.add(path[:depth])
        for path,item in self.items.items():
            show=not query or path in visible or any(path[:depth] in matches for depth in range(len(path)))
            item.setHidden(not show)
            if query and path in visible:item.setExpanded(True)
            elif not query and getattr(self,'_filter_query',''):item.setExpanded(path in getattr(self,'_filter_expanded',set()))
        self._filter_stamp=stamp;self._filter_query=query

    def navigate(self,item,column):
        path=item.data(0,Qt.ItemDataRole.UserRole)
        if path is None:return
        host=self.host;host.flush_text()
        if not path:host.go_root()
        else:
            host._reveal_relation(path[-1])
            host._navigation=[(host.budget._relation(rid).parent_code,rid,'') for rid in path[:-1]]
        host.show_panel('precios')
        if self.embedded:host.set_budget_view('precios')
