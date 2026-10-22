"""Read-only production/resource comparisons for an explicit inclusive interval."""
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QDateEdit,QPushButton,QTabWidget,QTableWidget
from .planning_panel import fill
from .productivity import snapshot,WORK_HEADERS,RESOURCE_HEADERS,UNASSIGNED_HEADERS


class ProductivityPanel(QWidget):
    def __init__(self,host):
        super().__init__(host);self.host=host;layout=QVBoxLayout(self);bar=QHBoxLayout();today=QDate.currentDate()
        self.start=QDateEdit(QDate(today.year(),today.month(),1));self.end=QDateEdit(today)
        for label,editor in (('Desde',self.start),('Hasta',self.end)):
            bar.addWidget(QLabel(label));editor.setCalendarPopup(True);editor.setDisplayFormat('dd/MM/yyyy');bar.addWidget(editor)
        button=QPushButton('Exportar vista…');button.clicked.connect(self.export);bar.addWidget(button);bar.addStretch();layout.addLayout(bar)
        note=QLabel('Compara partes de producción y horas actualmente confirmados dentro del mismo intervalo. Usa las tarifas guardadas en los registros de horas. Los datos ausentes quedan en blanco; no se estiman horas ni cantidades.');note.setWordWrap(True);layout.addWidget(note)
        self.status=QLabel();layout.addWidget(self.status);self.tabs=QTabWidget();layout.addWidget(self.tabs);self.work=QTableWidget();self.resources=QTableWidget();self.unassigned=QTableWidget()
        for table,label in ((self.work,'Por partida'),(self.resources,'Por recurso y partida'),(self.unassigned,'Horas sin asignar')):self.tabs.addTab(table,label)
        note=QLabel('Los cocientes describen el periodo registrado, no una productividad normativa. En el detalle por recurso, la producción de una partida se repite como denominador: no sumes esa columna. El coste incluye solo estas horas; no facturas ni materiales. Se usan estados actuales, sin reconstrucción histórica.');note.setWordWrap(True);layout.addWidget(note)
        self.start.dateChanged.connect(self.render);self.end.dateChanged.connect(self.render)
    def render(self,*_):
        start=self.start.date().toString('yyyy-MM-dd');end=self.end.date().toString('yyyy-MM-dd')
        if start>end:
            self.status.setText('Selecciona un inicio anterior o igual al fin.');fill(self.work,WORK_HEADERS,[]);fill(self.resources,RESOURCE_HEADERS,[]);fill(self.unassigned,UNASSIGNED_HEADERS,[]);return
        view=snapshot(self.host.budget,start,end);fill(self.work,WORK_HEADERS,view['work_items']);fill(self.resources,RESOURCE_HEADERS,view['resources']);fill(self.unassigned,UNASSIGNED_HEADERS,view['unassigned'])
        self.status.setText(f"Partidas con registros: {len(view['work_items'])} · Sin producción: {sum(r[-1]=='Sin producción registrada' for r in view['work_items'])} · Sin horas: {sum(r[-1]=='Sin horas registradas' for r in view['work_items'])} · Coste de horas sin asignar: {view['unassigned_cost']}")
    def export(self):
        from .report_actions import export_report
        if self.start.date()>self.end.date():self.host._error('Revisa el intervalo de fechas.');return
        export_report(self.host,'rendimientos:'+self.start.date().toString('yyyy-MM-dd')+':'+self.end.date().toString('yyyy-MM-dd')+':'+('partidas','recursos','sin_asignar')[self.tabs.currentIndex()])
