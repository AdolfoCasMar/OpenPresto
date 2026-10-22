"""Earned-value desktop adapter; all edits use transactional core commands."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPen, QBrush
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QLabel,QComboBox,
    QTableWidget,QDialog,QFormLayout,QLineEdit,QTabWidget,QGraphicsView,QGraphicsScene,QHeaderView)
from .planning_panel import fill,buttons
from . import earned_value as engine
from .reports import report_table
from .planning import iso


class EarnedValuePanel(QWidget):
    def __init__(self,host):
        super().__init__(host);self.host=host
        layout=QVBoxLayout(self);bar=QHBoxLayout()
        self.freeze=QPushButton('Congelar línea base…');self.freeze.clicked.connect(self.freeze_base);bar.addWidget(self.freeze)
        self.phase=QComboBox();bar.addWidget(self.phase)
        self.edit=QPushButton('Producción y coste real…');self.edit.clicked.connect(self.edit_period);bar.addWidget(self.edit)
        layout.addLayout(bar)
        note=QLabel('Elige un plan por fases cuyo reparto completo coincida con el objetivo. La línea base se congela. Producción y coste real son acumulados al cierre de cada fase; vacíos = desconocidos. No se deducen de certificaciones ni pagos. SV expresa importe, no días. Las previsiones dependen de la hipótesis indicada.');note.setWordWrap(True);layout.addWidget(note)
        self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status)
        tabs=QTabWidget();self.summary=QTableWidget();tabs.addTab(self.summary,'Indicadores por periodo')
        self.details=QTableWidget();tabs.addTab(self.details,'Producción y coste del periodo')
        self.chart=QGraphicsView();self.scene=QGraphicsScene(self.chart);self.chart.setScene(self.scene);tabs.addTab(self.chart,'Curvas S')
        layout.addWidget(tabs);self.phase.currentIndexChanged.connect(self.render_period)

    def render(self):
        data=engine.validate(self.host.budget);base=data['baseline'];old=self.phase.currentData()
        self.phase.blockSignals(True);self.phase.clear()
        if base:
            for i,end in enumerate(base['end_dates'],1):self.phase.addItem(str(i)+' · '+end,i)
        index=self.phase.findData(old);self.phase.setCurrentIndex(max(0,index));self.phase.blockSignals(False)
        self.freeze.setEnabled(base is None);self.edit.setEnabled(base is not None)
        self.status.setText('Sin línea base. Define el plan por fases antes de congelarlo.' if base is None else 'Línea base congelada · '+str(len(base['tasks']))+' partidas · '+base['note'])
        fill(self.summary,*report_table(self.host.budget,'valor_ganado'))
        self.render_period();self.draw_curves()

    def render_period(self,*_):
        phase=self.phase.currentData()
        rows=engine.activity_rows(self.host.budget,phase) if phase is not None else []
        fill(self.details,('Partida','Producción acumulada','BAC','PV','EV','Coste real acumulado','Nota'),[
            (r['code'],r['quantity'] if r['quantity'] is not None else 'Sin dato',r['BAC'],r['PV'],r['EV'] if r['EV'] is not None else 'Sin dato',r['actual_cost'] if r['actual_cost'] is not None else 'Sin dato',r['note']) for r in rows])

    def freeze_base(self):
        d=QDialog(self);d.setWindowTitle('Congelar línea base de control');form=QFormLayout(d)
        note=QLineEdit();form.addRow('Referencia / explicación',note)
        label=QLabel('Se conservarán las cantidades, precios, factores, reparto y precisión del plan actual. Las ediciones futuras del plan no cambian esta línea base. No se sobrescribe una base existente.');label.setWordWrap(True);form.addRow(label);buttons(d,form)
        if d.exec()==QDialog.DialogCode.Accepted:self.host._execute('earned_value.baseline.freeze',explanation=note.text())

    def edit_period(self):
        data=engine.validate(self.host.budget);base=data['baseline'];phase=self.phase.currentData()
        if base is None or phase is None:return
        records={r['relation_id']:r for r in data['progress'] if r['phase']==phase}
        d=QDialog(self);d.setWindowTitle('Acumulados al '+base['end_dates'][phase-1]);d.resize(950,560);layout=QVBoxLayout(d)
        label=QLabel('Introduce toda la producción y coste real acumulados a esta fecha. Escribe 0 cuando sea cero conocido; deja vacío cuando falte información. No se arrastran datos de periodos anteriores.');label.setWordWrap(True);layout.addWidget(label)
        table=QTableWidget(len(base['tasks']),4);table.setHorizontalHeaderLabels(('Partida / cantidad base','Producción acumulada','Coste real acumulado','Nota / evidencia'));layout.addWidget(table)
        for i,task in enumerate(base['tasks']):
            record=records.get(task['relation_id'],{})
            table.setCellWidget(i,0,QLabel(task['code']+' / '+task['quantity']))
            for col,key in ((1,'quantity'),(2,'actual_cost'),(3,'note')):
                field=QLineEdit('' if record.get(key) is None else str(record[key]));table.setCellWidget(i,col,field)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        form=QFormLayout();layout.addLayout(form);buttons(d,form)
        if d.exec()==QDialog.DialogCode.Accepted:
            rows=[]
            for i,task in enumerate(base['tasks']):
                quantity=table.cellWidget(i,1).text().strip().replace(',','.');cost=table.cellWidget(i,2).text().strip().replace(',','.')
                rows.append(dict(relation_id=task['relation_id'],quantity=quantity or None,actual_cost=cost or None,note=table.cellWidget(i,3).text()))
            self.host._execute('earned_value.period.set',phase=phase,rows=rows)

    def draw_curves(self):
        rows=engine.curve_rows(self.host.budget);self.scene.clear();self.scene.setBackgroundBrush(QColor('white'))
        if not rows:
            self.scene.addText('Congela una línea base para ver las curvas.');return
        left,top,width,height=100,55,850,330
        first=iso(rows[0]['date']);span=max(1,(iso(rows[-1]['date'])-first).days)
        maximum=max([float(r[key]) for r in rows for key in ('BAC','PV','EV','AC') if r[key] is not None]+[1.0])
        for n in range(6):
            y=top+height-n*height/5
            self.scene.addLine(left,y,left+width,y,QPen(QColor('#dce1e7')))
            label=self.scene.addText(format(maximum*n/5,',.2f'));label.setPos(0,y-12)
        for series,color in (('PV','#bf4db3'),('EV','#268b84'),('AC','#557cb3')):
            legend=self.scene.addText(series);legend.setDefaultTextColor(QColor(color));legend.setPos(left+('PV','EV','AC').index(series)*85,0)
            previous=None
            for row in rows:
                x=left+(iso(row['date'])-first).days/span*width
                if row[series] is None:previous=None;continue
                y=top+height-float(row[series])/maximum*height
                if previous:self.scene.addLine(previous[0],previous[1],x,y,QPen(QColor(color),2))
                self.scene.addEllipse(x-3,y-3,6,6,QPen(QColor(color)),QBrush(QColor(color)))
                previous=(x,y)
        step=max(1,len(rows)//8)
        for index,row in enumerate(rows):
            if index%step and index!=len(rows)-1:continue
            x=left+(iso(row['date'])-first).days/span*width
            label=self.scene.addText(row['date']);label.setPos(x-35,top+height+10)
        label=self.scene.addText('Los huecos EV/AC indican periodos sin datos completos. Sin interpolación de datos ausentes.');label.setPos(left,top+height+45)
        self.scene.setSceneRect(0,0,left+width+100,top+height+90)
