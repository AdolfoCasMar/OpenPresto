"""Review native budget phases before explicitly applying their quantities."""
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QLabel,QTableWidget,QComboBox,QDialog,QFormLayout,QLineEdit,QMessageBox
from .planning_panel import fill,buttons
from . import budget_phase_measurements as phases


class BudgetPhaseMeasurementsPanel(QWidget):
    def __init__(self,host):
        super().__init__(host);self.host=host;layout=QVBoxLayout(self);bar=QHBoxLayout()
        for title,callback in (('Copiar fases del PZH',self.copy),('Editar línea…',self.edit),('Vista previa…',self.preview),('Retirar copia…',self.clear),('Aplicar hasta la fase seleccionada…',self.apply),('Exportar…',self.export)):
            button=QPushButton(title);button.clicked.connect(callback);bar.addWidget(button)
        link=QPushButton('Vincular línea…');link.clicked.connect(self.link);bar.addWidget(link)
        layout.addLayout(bar);self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status);self.phase=QComboBox();layout.addWidget(self.phase);self.table=QTableWidget();layout.addWidget(self.table);self.phase.currentIndexChanged.connect(self.filter);self.table.cellDoubleClicked.connect(lambda *_:self.edit());self.rows=[]
    def render(self):
        data=phases.state(self.host.budget);current=self.phase.currentData();self.phase.blockSignals(True);self.phase.clear();self.phase.addItem('Todas las fases',None)
        if data:
            for phase in sorted({r['phase'] for r in data['lines']}):self.phase.addItem('Fase '+str(phase),phase)
            index=self.phase.findData(current);self.phase.setCurrentIndex(max(0,index));pending=sum(r['relation_id'] is None for r in data['lines']);self.status.setText(f"Límite aprobado en origen: {data['approved_through']}. Último límite aplicado desde estas copias: {data['active_through'] or 'sin aplicar'}. Líneas sin vincular: {pending}. Editar una copia no cambia el presupuesto activo hasta aplicarla. La aplicación sustituye las mediciones de las relaciones incluidas y puede deshacerse.")
        else:self.status.setText('No hay una copia nativa de las mediciones por fases. El PZH original permanece intacto.')
        self.phase.blockSignals(False);self.filter()
    def filter(self,*_):
        phase=self.phase.currentData();self.rows=[r for r in phases.report_rows(self.host.budget) if phase is None or r[1]==phase];fill(self.table,phases.HEADERS,self.rows)
    def copy(self):self.host._execute('budget.phases.copy_pzh')
    def edit(self):
        i=self.table.currentRow()
        if not 0<=i<len(self.rows):self.host._error('Selecciona una línea de fase.');return
        identity=self.rows[i][0];row=next(r for r in phases.state(self.host.budget)['lines'] if r['id']==identity)
        dialog=QDialog(self);dialog.setWindowTitle('Medición por fases');form=QFormLayout(dialog);widgets={}
        for key,title in zip(phases.FIELDS,('Comentario','N','Longitud','Anchura','Altura','Fórmula')):
            edit=QLineEdit(row[key] or '');edit.setObjectName('phase-'+key);form.addRow(title,edit);widgets[key]=edit
        buttons(dialog,form)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            changes={key:edit.text() if key in ('comment','formula','n_lines') else edit.text() or None for key,edit in widgets.items()};self.host._execute('budget.phases.line.edit',line_id=identity,changes=changes)
    def clear(self):
        if phases.state(self.host.budget) is None:return
        if QMessageBox.question(self,'Retirar copia de fases','Se retirará la copia editable de las fases y sus ediciones. Las cantidades actuales del presupuesto y el PZH original se conservan. Podrás deshacer la retirada. ¿Continuar?')==QMessageBox.StandardButton.Yes:self.host._execute('budget.phases.clear')
    def link(self):
        i=self.table.currentRow()
        if not 0<=i<len(self.rows):self.host._error('Selecciona una línea pendiente de vincular.');return
        row=next(r for r in phases.state(self.host.budget)['lines'] if r['id']==self.rows[i][0])
        if 'source_relation' not in row:self.host._error('Esta línea conserva su relación nativa de origen.');return
        dialog=QDialog(self);dialog.setWindowTitle('Revisar relación de la medición');form=QFormLayout(dialog);source=row['source_relation'];form.addRow(QLabel('Origen: '+source['parent']+' → '+source['child']+'. Selecciona expresamente el destino revisado.'));target=QComboBox();target.setObjectName('phase-link-target');target.addItem('Selecciona una relación…',None)
        for relation in self.host.budget.relations:target.addItem(relation.parent_code+' → '+relation.child_code+' · '+self.host.budget.concepts[relation.child_code].unit,relation.id)
        if row['relation_id'] is not None:target.setCurrentIndex(target.findData(row['relation_id']))
        form.addRow('Relación de destino',target);buttons(dialog,form)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.host._execute('budget.phases.line.link',line_id=row['id'],relation_id=target.currentData())
    def _preview(self):
        phase=self.phase.currentData()
        if phase is None:self.host._error('Selecciona una fase concreta.');return None
        try:return phases.preview(self.host.budget,phase)
        except (ValueError,ArithmeticError) as exc:self.host._error(str(exc));return None
    def _totals(self,data):
        from .number_format import display
        return 'Sin raíz presupuestaria' if data['before_total'] is None else f"Total actual: {display(data['before_total'])} · Total propuesto: {display(data['after_total'])} · Diferencia: {display(data['delta_total'])}"
    def preview(self):
        data=self._preview()
        if data is None:return
        dialog=QDialog(self);dialog.setWindowTitle('Vista previa de mediciones por fases');dialog.resize(1050,550);layout=QVBoxLayout(dialog)
        label=QLabel(self._totals(data));label.setObjectName('phase-preview-totals');layout.addWidget(label)
        note=QLabel('Los importes de las relaciones pueden solaparse en la jerarquía: no se suman para obtener la diferencia del presupuesto. Cerrar esta vista no aplica cambios.');note.setWordWrap(True);layout.addWidget(note)
        table=QTableWidget();table.setObjectName('phase-preview-table');fill(table,phases.PREVIEW_HEADERS,data['rows']);layout.addWidget(table);close=QPushButton('Cerrar');close.clicked.connect(dialog.accept);layout.addWidget(close);dialog.exec()
    def apply(self):
        data=self._preview()
        if data is None:return
        phase=data['phase'];text=self._totals(data)+f"\nRelaciones con cambios de cantidad o importe: {data['changed_relations']}.\nSe sustituirán las mediciones de las relaciones incluidas por las líneas hasta la fase {phase}. Podrás deshacer la operación. ¿Aplicar?"
        if QMessageBox.question(self,'Aplicar mediciones',text)==QMessageBox.StandardButton.Yes:self.host._execute('budget.phases.apply',phase=phase)
    def export(self):
        from .report_actions import export_report
        export_report(self.host,'mediciones_fases')
