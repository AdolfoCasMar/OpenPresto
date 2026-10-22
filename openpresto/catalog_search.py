"""Búsqueda y clasificación del catálogo de conceptos del proyecto."""
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLineEdit,QComboBox,QTableWidget,QTableWidgetItem,QDialogButtonBox
from .calculations import calculator_for


def show_catalog(host):
    host.flush_text()
    dialog=QDialog(host)
    dialog.setWindowTitle('Buscar conceptos y recursos')
    dialog.resize(900,600)
    layout=QVBoxLayout(dialog)
    controls=QHBoxLayout()
    search=QLineEdit()
    search.setPlaceholderText('Código, resumen, texto o unidad…')
    nature=QComboBox()
    nature.addItem('Todas las naturalezas',None)
    for value in sorted({c.nature for c in host.budget.concepts.values()}):
        nature.addItem(value or '(sin clasificar)',value)
    controls.addWidget(search)
    controls.addWidget(nature)
    layout.addLayout(controls)
    table=QTableWidget(0,5)
    table.setHorizontalHeaderLabels(['Código','Unidad','Resumen','Naturaleza','Precio'])
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    table.setSortingEnabled(False)
    calculator=calculator_for(host.budget)
    concepts=list(host.budget.concepts.values())
    from .concept_keywords import validate as keyword_state
    keywords=keyword_state(host.budget)
    table.setRowCount(len(concepts))
    for index,concept in enumerate(concepts):
        for column,value in enumerate((concept.code,concept.unit,concept.summary,concept.nature,calculator.price(concept.code))):
            table.setItem(index,column,QTableWidgetItem(str(value)))
    table.setColumnWidth(2,400)
    layout.addWidget(table)
    def filter_rows():
        query=search.text().casefold().strip()
        selected=nature.currentData()
        for index,concept in enumerate(concepts):
            text=' '.join((concept.code,concept.unit,concept.summary,concept.text,*keywords.get(concept.code,{}).get('terms',()))).casefold()
            table.setRowHidden(index,query not in text or (selected is not None and selected != concept.nature))
    search.textChanged.connect(filter_rows)
    nature.currentIndexChanged.connect(filter_rows)
    def navigate(row,column):
        code=concepts[row].code
        target=next(i for i,c in enumerate(host.budget.concepts) if c==code)
        host.show_panel('conceptos')
        host.concepts_table.setCurrentCell(target,0)
        host.select_concept()
        dialog.accept()
    table.cellDoubleClicked.connect(navigate)
    buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    dialog.exec()
