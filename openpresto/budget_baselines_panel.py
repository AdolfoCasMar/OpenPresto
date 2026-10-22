"""Immutable budget references and current graph comparison."""
from PySide6.QtCore import QDate,QSignalBlocker
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QComboBox,QCheckBox,QTableWidget,QDialog,QFormLayout,QLineEdit,QDateEdit
from .planning_panel import fill,buttons
from . import budget_baselines as baselines


class BudgetBaselinesPanel(QWidget):
    def __init__(self,host):
        super().__init__(host);self.host=host;layout=QVBoxLayout(self);bar=QHBoxLayout()
        for text,callback in (('Guardar línea base…',self.freeze),('Retirar línea base',self.remove),('Exportar comparación…',self.export)):
            button=QPushButton(text);button.clicked.connect(callback);bar.addWidget(button)
        layout.addLayout(bar);bar=QHBoxLayout();self.choice=QComboBox();bar.addWidget(self.choice);self.changed=QCheckBox('Solo cambios');bar.addWidget(self.changed);layout.addLayout(bar)
        note=QLabel('Referencia inmutable de cantidades, precios, factores e importes calculados. Compara por identificador de relación; no empareja por código. El total compara las raíces calculadas. Las filas incluyen capítulos y descomposiciones: sus variaciones no se suman al total de la obra.');note.setWordWrap(True);layout.addWidget(note)
        self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status);self.table=QTableWidget();layout.addWidget(self.table)
        note=QLabel('El precio mostrado es el precio calculado del concepto. El importe de la relación también puede incluir factores e indirectos según el motor activo. Una línea base guarda valores, no una copia completa para restaurar la obra.');note.setWordWrap(True);layout.addWidget(note)
        self.choice.currentIndexChanged.connect(self.render);self.changed.toggled.connect(self.render)
    def render(self,*_):
        old=self.choice.currentData();blocker=QSignalBlocker(self.choice);self.choice.clear()
        for row in baselines.validate(self.host.budget):self.choice.addItem(row['reference']+' · '+row['date'],row['id'])
        if old is not None and self.choice.findData(old)>=0:self.choice.setCurrentIndex(self.choice.findData(old))
        del blocker
        if not self.choice.count() or self.host.budget.root_code is None:
            fill(self.table,baselines.HEADERS,[]);self.status.setText('Guarda una línea base para comparar.' if not self.choice.count() else 'Establece una raíz para calcular el presupuesto actual.');return
        view=baselines.comparison(self.host.budget,self.choice.currentData(),self.changed.isChecked());fill(self.table,baselines.HEADERS,view['rows'])
        self.status.setText(f"Base {view['reference']}: {view['base_total']} · Actual: {view['current_total']} · Variación total: {view['delta_total']} · Raíz base: {view['old_root']} · Raíz actual: {view['root']}. Comparación de valores calculados con la configuración de cada momento.")
    def freeze(self):
        dialog=QDialog(self);dialog.setWindowTitle('Guardar línea base de presupuesto');form=QFormLayout(dialog);reference=QLineEdit();reference.setObjectName('baseline-reference');form.addRow('Referencia única',reference);day=QDateEdit(QDate.currentDate());day.setCalendarPopup(True);day.setDisplayFormat('dd/MM/yyyy');form.addRow('Fecha de referencia',day);note=QLineEdit();form.addRow('Nota',note);buttons(dialog,form)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.host._execute('budget.baseline.freeze',reference=reference.text(),date=day.date().toString('yyyy-MM-dd'),note=note.text())
    def remove(self):
        if self.choice.currentData() is None:self.host._error('Selecciona una línea base.');return
        self.host._execute('budget.baseline.remove',baseline_id=self.choice.currentData())
    def export(self):
        from .report_actions import export_report
        if self.choice.currentData() is None:self.host._error('Selecciona una línea base.');return
        export_report(self.host,'comparacion_base:'+self.choice.currentData()+(':cambios' if self.changed.isChecked() else ''))
