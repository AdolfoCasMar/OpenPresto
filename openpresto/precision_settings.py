"""Configuración explícita de precisión económica por proyecto."""
from PySide6.QtWidgets import QDialog, QFormLayout, QSpinBox, QDialogButtonBox, QComboBox
from .budget import BudgetError


def configure(host):
    if (host.budget.project_metadata.get('engine') != 'native-v1'
            and (host.budget.percentage_profile or host.budget.indirect_config or host.budget.locked_prices)):
        host._error('La precisión personalizada se configura en el perfil económico nativo sin porcentajes ni bloqueos')
        return
    dialog = QDialog(host)
    dialog.setWindowTitle('Precisión económica del proyecto')
    form = QFormLayout(dialog)
    fields = {}
    for key, default, label in [('quantity_decimals',3,'Cantidad'), ('price_decimals',2,'Precio'), ('amount_decimals',2,'Importe')]:
        spin = QSpinBox()
        spin.setRange(0,12)
        spin.setValue(int(host.budget.project_metadata.get(key,str(default))))
        fields[key] = spin
        form.addRow(label, spin)
    rounding = QComboBox()
    rounding.addItems(['ROUND_HALF_UP','ROUND_HALF_EVEN','ROUND_DOWN'])
    rounding.setCurrentText(host.budget.project_metadata.get('economic_rounding','ROUND_HALF_UP'))
    form.addRow('Redondeo económico',rounding)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    form.addRow(buttons)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        host._execute('budget.precision.set', **{key:spin.value() for key,spin in fields.items()}, rounding=rounding.currentText())
