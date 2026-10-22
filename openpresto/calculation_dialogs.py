"""Qt adapters for calculation settings; all mutations go through commands."""
from .economic_summary import KEYS

def configure_engine(host):
    from PySide6.QtWidgets import QInputDialog
    current=host.budget.project_metadata.get('engine')=='native-v1'
    choice,ok=QInputDialog.getItem(host,'Motor económico',
        'El motor nativo combina porcentajes por prefijo, bloqueos e indirectos con reglas propias. Cambiar puede modificar los importes.',
        ['Perfiles históricos','Motor nativo combinado'],1 if current else 0,False)
    if not ok:
        return
    host._execute('budget.engine.set', engine='native-v1' if choice == 'Motor nativo combinado' else None)


def configure_summary(host):
    from PySide6.QtWidgets import QDialog,QFormLayout,QLineEdit,QDialogButtonBox
    dialog=QDialog(host)
    dialog.setWindowTitle('Porcentajes del resumen económico')
    layout=QFormLayout(dialog)
    edits={}
    for key,label in zip(KEYS,('Gastos generales (%)','Beneficio industrial (%)','Impuestos (%)')):
        edits[key]=QLineEdit(host.budget.project_metadata.get(key,'0'))
        layout.addRow(label,edits[key])
    buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addRow(buttons)
    if dialog.exec()==QDialog.DialogCode.Accepted:
        host._execute('budget.summary.set', **{key:edit.text().replace(',','.') for key,edit in edits.items()})
