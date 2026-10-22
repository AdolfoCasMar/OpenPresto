"""Cutoff stock balances and movement traceability without mutating the ledger."""
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QDateEdit,QCheckBox,QPushButton,QTabWidget,QTableWidget
from .planning_panel import fill
from .inventory_control import snapshot,HEADERS,MOVEMENT_HEADERS


class InventoryControlPanel(QWidget):
    def __init__(self,host):
        super().__init__(host);self.host=host;layout=QVBoxLayout(self);bar=QHBoxLayout();bar.addWidget(QLabel('Existencias a fecha'))
        self.cut=QDateEdit(QDate.currentDate());self.cut.setCalendarPopup(True);self.cut.setDisplayFormat('dd/MM/yyyy');bar.addWidget(self.cut);self.zero=QCheckBox('Incluir saldos cero');bar.addWidget(self.zero);button=QPushButton('Exportar vista…');button.clicked.connect(self.export);bar.addWidget(button);bar.addStretch();layout.addLayout(bar)
        note=QLabel('Saldos derivados de entradas y consumos nativos hasta la fecha elegida. La valoración sigue el coste medio del libro de existencias. Una factura vinculada a un albarán no añade otra entrada. No se sustituyen costes registrados por precios actuales.');note.setWordWrap(True);layout.addWidget(note)
        self.status=QLabel();layout.addWidget(self.status);self.tabs=QTabWidget();layout.addWidget(self.tabs);self.table=QTableWidget();self.movements=QTableWidget();self.tabs.addTab(self.table,'Saldos');self.tabs.addTab(self.movements,'Movimientos')
        note=QLabel('Se aplica el estado actual de los documentos; no se reconstruyen confirmaciones ni anulaciones históricas. La importación de borradores PZH no acredita existencias antiguas. Los recursos sin movimientos registrados no aparecen como existencias cero comprobadas.');note.setWordWrap(True);layout.addWidget(note)
        self.cut.dateChanged.connect(self.render);self.zero.toggled.connect(self.render)
    def render(self,*_):
        view=snapshot(self.host.budget,self.cut.date().toString('yyyy-MM-dd'),self.zero.isChecked());fill(self.table,HEADERS,view['rows']);fill(self.movements,MOVEMENT_HEADERS,view['movements']);self.status.setText(f"Recursos visibles: {len(view['rows'])} · Valor de existencias registrado: {view['total_value']}")
    def export(self):
        from .report_actions import export_report
        export_report(self.host,'inventario:'+self.cut.date().toString('yyyy-MM-dd')+':'+('movimientos' if self.tabs.currentIndex() else 'todos' if self.zero.isChecked() else 'saldos'))
