"""Navegación jerárquica por relaciones, conservando conceptos reutilizados."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QDialogButtonBox
from .calculations import calculator_for, calculation_batch


def show_tree(host):
    host.flush_text()
    dialog = QDialog(host)
    dialog.setWindowTitle('Estructura del presupuesto')
    dialog.resize(900,650)
    layout = QVBoxLayout(dialog)
    tree = QTreeWidget()
    tree.setHeaderLabels(['Código', 'Resumen', 'Cantidad', 'Precio', 'Importe'])
    layout.addWidget(tree)
    calculator = calculator_for(host.budget)
    children = {}
    for relation in host.budget.relations:
        children.setdefault(relation.parent_code, []).append(relation)
    def append(parent, code, ancestors):
        if code in ancestors:
            raise ValueError('Ciclo en la estructura')
        for relation in sorted(children.get(code,()),key=lambda r:r.position):
            concept = host.budget.concepts[relation.child_code]
            value = calculator.relation(relation.id)
            item = QTreeWidgetItem(parent,[concept.code,concept.summary,str(value.quantity),str(value.unit_price),str(value.amount)])
            item.setData(0,Qt.ItemDataRole.UserRole,relation.id)
            append(item,concept.code,ancestors | {code})
    root = host.budget.root_code
    with calculation_batch(calculator):
        if root:
            concept = host.budget.concepts[root]
            total=str(calculator.total())
            item = QTreeWidgetItem(tree,[root,concept.summary,'',total,total])
            append(item,root,set())
    tree.expandToDepth(1)
    tree.setColumnWidth(0,200)
    tree.setColumnWidth(1,350)
    def navigate(item,column):
        rid = item.data(0,Qt.ItemDataRole.UserRole)
        if rid:
            path=[]
            parent=item.parent()
            while parent is not None:
                parent_rid=parent.data(0,Qt.ItemDataRole.UserRole)
                if parent_rid:
                    relation=host.budget._relation(parent_rid)
                    path.append((relation.parent_code,parent_rid,''))
                parent=parent.parent()
            host._reveal_relation(rid)
            host._navigation=list(reversed(path))
        else:
            host.go_root()
        host.show_panel('precios')
        dialog.accept()
    tree.itemDoubleClicked.connect(navigate)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    dialog.exec()
