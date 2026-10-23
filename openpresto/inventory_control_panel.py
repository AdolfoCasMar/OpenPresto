"""Cutoff stock balances and movement traceability without mutating the ledger."""
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QDateEdit,QCheckBox,QPushButton,QTabWidget,QTableWidget
from .planning_panel import fill
from .inventory_control import period,HEADERS,MOVEMENT_HEADERS,PERIOD_HEADERS,abc_from_snapshot,ABC_HEADERS,ABC_SUMMARY_HEADERS


class InventoryControlPanel(QWidget):
    def __init__(self,host):
        super().__init__(host);self.host=host;layout=QVBoxLayout(self);bar=QHBoxLayout();bar.addWidget(QLabel('Existencias a fecha'))
        self.cut=QDateEdit(QDate.currentDate());self.cut.setCalendarPopup(True);self.cut.setDisplayFormat('dd/MM/yyyy');bar.addWidget(self.cut);self.zero=QCheckBox('Incluir saldos cero');bar.addWidget(self.zero);button=QPushButton('Exportar vista…');button.clicked.connect(self.export);bar.addWidget(button);bar.addStretch();layout.addLayout(bar)
        note=QLabel('Saldos derivados de entradas y consumos nativos hasta la fecha elegida. La valoración sigue el coste medio del libro de existencias. Una factura vinculada a un albarán no añade otra entrada. No se sustituyen costes registrados por precios actuales.');note.setWordWrap(True);layout.addWidget(note)
        self.status=QLabel();layout.addWidget(self.status);self.tabs=QTabWidget();layout.addWidget(self.tabs);self.table=QTableWidget();self.movements=QTableWidget();self.tabs.addTab(self.table,'Saldos');self.tabs.addTab(self.movements,'Movimientos')
        period_bar=QHBoxLayout();period_bar.addWidget(QLabel('Período desde'))
        self.start=QDateEdit(QDate.currentDate().addDays(1-QDate.currentDate().day()));self.start.setCalendarPopup(True);self.start.setDisplayFormat('dd/MM/yyyy');period_bar.addWidget(self.start)
        period_bar.addWidget(QLabel('hasta la fecha de existencias'));period_bar.addStretch();layout.insertLayout(3,period_bar)
        self.period_table=QTableWidget();self.period_movements=QTableWidget();self.tabs.addTab(self.period_table,'Balance del período');self.tabs.addTab(self.period_movements,'Movimientos del período')
        self.abc_table=QTableWidget();self.abc_summary=QTableWidget();self.tabs.addTab(self.abc_table,'Clasificación ABC');self.tabs.addTab(self.abc_summary,'Resumen ABC')
        self.abc_note=QLabel('ABC por valor de existencias: A hasta alcanzar el 80 %, B hasta el 95 % y C el resto. El recurso que cruza el umbral permanece en su grupo; los valores cero son C. No mide consumo ni criticidad.');self.abc_note.setWordWrap(True);layout.addWidget(self.abc_note)
        self.abc_note.setVisible(False);self.tabs.currentChanged.connect(lambda index:self.abc_note.setVisible(index>=4))
        self.period_status=QLabel();self.period_status.setWordWrap(True);layout.addWidget(self.period_status)
        note=QLabel('Se aplica el estado actual de los documentos; no se reconstruyen confirmaciones ni anulaciones históricas. La importación de borradores PZH no acredita existencias antiguas. Los recursos sin movimientos registrados no aparecen como existencias cero comprobadas.');note.setWordWrap(True);layout.addWidget(note)
        self.cut.dateChanged.connect(self.render);self.zero.toggled.connect(self.render)
        self.start.dateChanged.connect(self.render)
    def render(self,*_):
        from PySide6.QtCore import QSignalBlocker
        block=QSignalBlocker(self.start);self.start.setMaximumDate(self.cut.date());del block
        interval=period(self.host.budget,self.start.date().toString('yyyy-MM-dd'),self.cut.date().toString('yyyy-MM-dd'),self.zero.isChecked());view=interval['cutoff']
        fill(self.table,HEADERS,view['rows']);fill(self.movements,MOVEMENT_HEADERS,view['movements']);fill(self.period_table,PERIOD_HEADERS,interval['rows']);fill(self.period_movements,MOVEMENT_HEADERS,interval['movements']);self.status.setText(f"Recursos visibles: {len(view['rows'])} · Valor de existencias registrado: {view['total_value']}")
        ranking=abc_from_snapshot(view);fill(self.abc_table,ABC_HEADERS,ranking['rows']);fill(self.abc_summary,ABC_SUMMARY_HEADERS,ranking['summary'])
        totals=interval['totals'];self.period_status.setText(f"Valor inicial {totals['opening_value']} + entradas {totals['incoming_value']} − consumos {totals['consumed_value']} = valor final {totals['closing_value']}. No se suman cantidades de recursos con unidades diferentes.")
    def export(self):
        from .report_actions import export_report
        if self.tabs.currentIndex()>=4:
            export_report(self.host,'inventario_abc:'+self.cut.date().toString('yyyy-MM-dd')+':'+('resumen' if self.tabs.currentIndex()==5 else 'detalle')+':'+('todos' if self.zero.isChecked() else 'saldos'))
            return
        if self.tabs.currentIndex()>=2:
            mode='movimientos' if self.tabs.currentIndex()==3 else 'todos' if self.zero.isChecked() else 'saldos'
            export_report(self.host,'inventario_periodo:'+self.start.date().toString('yyyy-MM-dd')+':'+self.cut.date().toString('yyyy-MM-dd')+':'+mode)
            return
        export_report(self.host,'inventario:'+self.cut.date().toString('yyyy-MM-dd')+':'+('movimientos' if self.tabs.currentIndex() else 'todos' if self.zero.isChecked() else 'saldos'))
