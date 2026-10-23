"""Treasury projection with explicit cut date and optional proformas."""
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QDateEdit,QCheckBox,QTabWidget,QTableWidget,QPushButton
from .planning_panel import fill
from .treasury import snapshot,detail_rows,month_rows
from .receivables_aging import from_treasury,HEADERS as AGING_HEADERS,DETAIL_HEADERS as AGING_DETAIL_HEADERS

DETAIL_HEADERS=('Fecha','Sentido','Clase','Documento','Entidad','Importe','Vencido','Detalle')
MONTH_HEADERS=('Mes','Cobros registrados','Pagos registrados','Neto registrado','Entradas previstas conocidas','Salidas previstas conocidas','Neto previsto conocido','Revisiones pendientes')


class TreasuryPanel(QWidget):
    def __init__(self,host):
        super().__init__(host);self.host=host;layout=QVBoxLayout(self);bar=QHBoxLayout()
        bar.addWidget(QLabel('Fecha de corte'));self.cut=QDateEdit(QDate.currentDate());self.cut.setDisplayFormat('dd/MM/yyyy');self.cut.setCalendarPopup(True);bar.addWidget(self.cut)
        self.proformas=QCheckBox('Incluir proformas en previsiones');bar.addWidget(self.proformas)
        button=QPushButton('Exportar vista…');bar.addWidget(button);button.clicked.connect(self.export)
        bar.addStretch();layout.addLayout(bar)
        note=QLabel('Solo facturas confirmadas; las proformas se incluyen expresamente. Vista calculada con los estados y calendarios actuales. Las liquidaciones cubren primero los vencimientos más antiguos. Las aperturas reducen pendientes, pero no son movimientos de caja. No representa un saldo bancario ni reconstruye estados históricos. Los datos sin fecha o sin revisar se muestran por separado.');note.setWordWrap(True);layout.addWidget(note)
        self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status)
        tabs=QTabWidget();self.months=QTableWidget();self.details=QTableWidget();tabs.addTab(self.months,'Resumen mensual');tabs.addTab(self.details,'Movimientos y previsiones');layout.addWidget(tabs)
        self.tabs=tabs;self.aging=QTableWidget();self.aging_details=QTableWidget();tabs.addTab(self.aging,'Antigüedad de saldos');tabs.addTab(self.aging_details,'Detalle de antigüedad')
        self.aging_status=QLabel();self.aging_status.setWordWrap(True);layout.addWidget(self.aging_status)
        self.cut.dateChanged.connect(self.render);self.proformas.toggled.connect(self.render)
    def render(self,*_):
        view=snapshot(self.host.budget,self.cut.date().toString('yyyy-MM-dd'),self.proformas.isChecked())
        fill(self.months,MONTH_HEADERS,month_rows(view));fill(self.details,DETAIL_HEADERS,detail_rows(view))
        aging=from_treasury(view);fill(self.aging,AGING_HEADERS,aging['rows']);fill(self.aging_details,AGING_DETAIL_HEADERS,aging['details'])
        incoming,outgoing=aging['totals']['in'],aging['totals']['out'];self.aging_status.setText(f"Vencido conocido: cobrar {incoming['overdue']} · pagar {outgoing['overdue']}. Sin fecha: cobrar {incoming['undated']} · pagar {outgoing['undated']}. Los importes por revisar no se consideran deuda cero ni se compensan cobros y pagos.")
        pending=sum(r['amount'] is None for r in view['events']);undated=sum(r['date'] is None for r in view['events'])
        self.status.setText(f'{pending} partidas requieren revisión · {undated} partidas sin fecha. Las previsiones no se contabilizan como pagos o cobros.')
    def export(self):
        from .report_actions import export_report
        if self.tabs.currentIndex()>=2:
            export_report(self.host,'antiguedad:'+self.cut.date().toString('yyyy-MM-dd')+':'+('detalle' if self.tabs.currentIndex()==3 else 'resumen')+(':+proformas' if self.proformas.isChecked() else ''))
            return
        export_report(self.host,'tesoreria:'+self.cut.date().toString('yyyy-MM-dd')+(':+proformas' if self.proformas.isChecked() else ''))
