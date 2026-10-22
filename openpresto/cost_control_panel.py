"""Current-price comparison of confirmed documents without accounting guesses."""
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QDateEdit,QPushButton,QTabWidget,QTableWidget
from .planning_panel import fill
from .cost_control import snapshot,summary_rows,concept_rows,document_rows,SUMMARY_HEADERS,CONCEPT_HEADERS,DOCUMENT_HEADERS



class CostControlPanel(QWidget):
    def __init__(self,host):
        super().__init__(host);self.host=host;layout=QVBoxLayout(self);bar=QHBoxLayout();bar.addWidget(QLabel('Fecha de corte'))
        self.cut=QDateEdit(QDate.currentDate());self.cut.setDisplayFormat('dd/MM/yyyy');self.cut.setCalendarPopup(True);bar.addWidget(self.cut)
        export=QPushButton('Exportar vista…');export.clicked.connect(self.export);bar.addWidget(export);bar.addStretch();layout.addLayout(bar)
        note=QLabel('Solo documentos confirmados. Pedidos, albaranes y facturas son etapas separadas: no se suman como costes independientes. La referencia es el precio actual de la misma cantidad facturada. Esta comparación no acredita producción ejecutada ni beneficio de la obra.');note.setWordWrap(True);layout.addWidget(note)
        self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status);self.tabs=QTabWidget();layout.addWidget(self.tabs)
        self.summary=QTableWidget();self.concepts=QTableWidget();self.documents=QTableWidget()
        for widget,title in ((self.summary,'Resumen'),(self.concepts,'Precios facturados'),(self.documents,'Documentos incluidos')):self.tabs.addTab(widget,title)
        self.cut.dateChanged.connect(self.render)
    def render(self,*_):
        view=snapshot(self.host.budget,self.cut.date().toString('yyyy-MM-dd'))
        fill(self.summary,SUMMARY_HEADERS,summary_rows(view));fill(self.concepts,CONCEPT_HEADERS,concept_rows(view));fill(self.documents,DOCUMENT_HEADERS,document_rows(view))
        self.status.setText(f"Borradores excluidos: {view['excluded_drafts']} · Proformas excluidas: {view['excluded_proformas']} · Líneas sin cantidad comparable: {view['unknown_lines']}. Los pagos y cobros se muestran separados de las bases facturadas.")
    def export(self):
        from .report_actions import export_report
        suffix=('',':conceptos',':documentos')[self.tabs.currentIndex()]
        export_report(self.host,'control_economico:'+self.cut.date().toString('yyyy-MM-dd')+suffix)
