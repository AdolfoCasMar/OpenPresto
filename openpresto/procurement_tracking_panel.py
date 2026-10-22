"""Explicit order/delivery fulfilment without automatic document matching."""
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QDateEdit,QCheckBox,QPushButton,QTabWidget,QTableWidget
from .planning_panel import fill
from .procurement_tracking import snapshot,order_rows,delivery_rows,ORDER_HEADERS,DELIVERY_HEADERS,LINK_HEADERS


class ProcurementTrackingPanel(QWidget):
    def __init__(self,host):
        super().__init__(host);self.host=host;layout=QVBoxLayout(self);bar=QHBoxLayout();bar.addWidget(QLabel('Fecha de corte'))
        self.cut=QDateEdit(QDate.currentDate());self.cut.setDisplayFormat('dd/MM/yyyy');self.cut.setCalendarPopup(True);bar.addWidget(self.cut)
        self.pending=QCheckBox('Solo pendientes');self.pending.setChecked(True);bar.addWidget(self.pending)
        export=QPushButton('Exportar vista…');export.clicked.connect(self.export);bar.addWidget(export);bar.addStretch();layout.addLayout(bar)
        note=QLabel('Solo documentos confirmados y vínculos explícitos. Una factura contra un albarán no vuelve a servir el pedido. Las facturas directas consumen cantidad del pedido sin crear un albarán ficticio. Los importes globales se muestran sin inventar cantidades. El corte usa los estados actuales; no reconstruye estados históricos.');note.setWordWrap(True);layout.addWidget(note)
        self.status=QLabel();layout.addWidget(self.status);self.tabs=QTabWidget();layout.addWidget(self.tabs)
        self.orders=QTableWidget();self.deliveries=QTableWidget();self.links=QTableWidget()
        for table,label in ((self.orders,'Pedidos'),(self.deliveries,'Albaranes'),(self.links,'Trazabilidad')):self.tabs.addTab(table,label)
        self.cut.dateChanged.connect(self.render);self.pending.toggled.connect(self.render)
    def render(self,*_):
        view=snapshot(self.host.budget,self.cut.date().toString('yyyy-MM-dd'));pending=self.pending.isChecked()
        fill(self.orders,ORDER_HEADERS,order_rows(view,pending));fill(self.deliveries,DELIVERY_HEADERS,delivery_rows(view,pending));fill(self.links,LINK_HEADERS,view['links'])
        self.status.setText(f"Borradores excluidos: {view['excluded_drafts']} · Proformas excluidas: {view['excluded_proformas']}. La trazabilidad muestra todos los vínculos incluidos, también con el filtro de pendientes activo.")
    def export(self):
        from .report_actions import export_report
        index=self.tabs.currentIndex();kind=('pedidos','albaranes','trazabilidad')[index]
        export_report(self.host,'seguimiento_compras:'+self.cut.date().toString('yyyy-MM-dd')+':'+kind+(':pendientes' if index<2 and self.pending.isChecked() else ''))
