"""Read-only structural views over the current native budget."""
from PySide6.QtCore import Qt, QSettings, QSignalBlocker
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem
from .calculations import calculator_for, calculation_batch
from .concept_appearance import code_kind, style_code
from .number_format import display
from .ui_icons import nature_icon


class BudgetStructureView(QWidget):
    def __init__(self, host, mode):
        super().__init__(host)
        self.host=host; self.mode=mode; self._stamp=None
        layout=QVBoxLayout(self)
        self.note=QLabel('Doble clic para abrir el concepto en Precios. Los colores identifican el tipo de concepto.')
        self.note.setWordWrap(True); layout.addWidget(self.note)
        self.tree=QTreeWidget(); self.tree.setHeaderLabels(('Código','Resumen','Ud','Cantidad','Precio','Importe'))
        self.tree.setColumnWidth(0,140); self.tree.setColumnWidth(1,360)
        self.tree.setUniformRowHeights(True); self.tree.setAlternatingRowColors(True)
        self.tree.itemDoubleClicked.connect(self.navigate); layout.addWidget(self.tree)

    def render(self):
        host=self.host
        stamp=(host.budget, host._snapshot, QSettings().value('numbers/decimal_separator','.',type=str))
        if self._stamp and self._stamp[0] is stamp[0] and self._stamp[1:]==stamp[1:]:return
        blocker=QSignalBlocker(self.tree); self.tree.clear()
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
                item=QTreeWidgetItem(parent,(concept.code,concept.summary,concept.unit,
                    display(value.quantity),display(value.unit_price),display(value.amount)))
                item.setData(0,Qt.ItemDataRole.UserRole,next_path)
                item.setIcon(0,nature_icon(concept.nature));style_code(item,concept,root,0)
                for col in (3,4,5):item.setTextAlignment(col,Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
                # Work-item resources only belong in the complete tree.
                if self.mode=='arbol' or kind=='capitulo':add(item,concept.code,ancestors|{code},next_path)
        with calculation_batch(calc):
            if root:
                if self.mode=='arbol':
                    concept=budget.concepts[root]
                    item=QTreeWidgetItem(self.tree,(root,concept.summary,'','','',display(calc.total())))
                    item.setData(0,Qt.ItemDataRole.UserRole,());style_code(item,concept,root,0)
                    add(item,root,set(),())
                else:add(self.tree,root,set(),())
        self.tree.expandToDepth(1)
        self.note.setText(('Vista limitada a 30.000 apariciones. ' if limited else '')+
            'Doble clic para abrir en Precios. Vista de consulta; edita desde el presupuesto.')
        self._stamp=stamp;del blocker

    def navigate(self,item,column):
        path=item.data(0,Qt.ItemDataRole.UserRole)
        if path is None:return
        host=self.host;host.flush_text()
        if not path:host.go_root()
        else:
            host._reveal_relation(path[-1])
            host._navigation=[(host.budget._relation(rid).parent_code,rid,'') for rid in path[:-1]]
        host.show_panel('precios')
