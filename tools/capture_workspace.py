"""Capturas reproducibles de 0.3; solo usa el ejemplo propio incluido."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QFontDatabase
from openpresto.presto_workspace import PrestoWorkspace

app = QApplication([])
if os.name == 'nt':
    font = Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts/segoeui.ttf'
    if font.exists():
        identifier = QFontDatabase.addApplicationFont(str(font))
        families = QFontDatabase.applicationFontFamilies(identifier)
        if families:
            app.setFont(QFont(families[0],10))
window = PrestoWorkspace()
window.show()
app.processEvents()
ROOT.joinpath('dist').mkdir(exist_ok=True)
assert window.grab().save(str(ROOT/'dist/openpresto-03-vacio.png'))
window.load_path(ROOT/'openpresto/data/presupuesto-demo.bc3')
app.processEvents()
assert window.grab().save(str(ROOT/'dist/openpresto-03-mdi.png'))
window.dirty = False
window.close()
