"""Party directory adapter; native edits preserve original source properties."""
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QLabel,QTableWidget,QDialog,QFormLayout,QLineEdit,QSpinBox,QScrollArea,QComboBox
from .planning_panel import fill,buttons
from .entities import validate
from .reports import report_table

LABELS={'code':'Código','name':'Nombre','contact':'Persona de contacto','address':'Dirección','city':'Localidad','postal_code':'Código postal','province':'Provincia','phone':'Teléfono','phone_alt':'Otro teléfono','fax':'Fax','email':'Correo','tax_id':'Identificación fiscal','note':'Nota','title':'Titulación','college':'Colegio profesional','registration':'Número de colegiado'}


class EntitiesPanel(QWidget):
    def __init__(self,host):
        super().__init__(host);self.host=host;layout=QVBoxLayout(self);bar=QHBoxLayout()
        for text,callback in (('Nueva entidad…',lambda:self.edit(True)),('Editar entidad…',self.edit),('Copiar entidades del PZH',lambda:host._execute('pzh.entities.copy'))):
            button=QPushButton(text);button.clicked.connect(callback);bar.addWidget(button)
        layout.addLayout(bar)
        note=QLabel('Directorio editable de participantes y contactos. Conserva las propiedades del PZH original. Editar una entidad no cambia proveedores, clientes, documentos ni saldos ya creados.');note.setWordWrap(True);layout.addWidget(note)
        self.search=QLineEdit();self.search.setPlaceholderText('Buscar entidad, contacto, teléfono o dirección…');self.search.textChanged.connect(self.filter);layout.addWidget(self.search)
        self.table=QTableWidget();layout.addWidget(self.table);self.table.cellDoubleClicked.connect(lambda *_:self.edit());self.ids=[]
    def render(self):
        self.ids=[r['id'] for r in validate(self.host.budget)]
        fill(self.table,*report_table(self.host.budget,'entidades'));self.table.setColumnHidden(0,True);self.filter()
    def filter(self):
        query=self.search.text().strip().casefold()
        for row in range(self.table.rowCount()):
            visible=not query or any(query in self.table.item(row,col).text().casefold() for col in range(1,self.table.columnCount()) if self.table.item(row,col))
            self.table.setRowHidden(row,not visible)
    def edit(self,new=False):
        selected=self.table.currentRow();rows=validate(self.host.budget)
        old=next((r for r in rows if not new and 0<=selected<len(self.ids) and r['id']==self.ids[selected]),None)
        if not new and old is None:self.host._error('Selecciona una entidad.');return
        dialog=QDialog(self);dialog.setWindowTitle('Entidad y datos de contacto');dialog.resize(520,620);layout=QVBoxLayout(dialog)
        scroll=QScrollArea();scroll.setWidgetResizable(True);body=QWidget();form=QFormLayout(body);editors={}
        for key,label in LABELS.items():
            editor=QLineEdit(old[key] if old else '');editor.setObjectName('entity-'+key);editors[key]=editor;form.addRow(label,editor)
        role=QSpinBox();role.setObjectName('entity-role');role.setRange(0,255);role.setValue(old['role'] if old else 0);form.addRow('Tipo de entidad de origen',role)
        properties=old.get('properties',{}) if old else {};property_editors={}
        for key,label in (('quantity','Cantidad de la entidad'),('gross_area','Superficie construida total'),('path','Ruta de referencia (no se abre)'),('date','Fecha de entidad (AAAA-MM-DD)')):
            editor=QLineEdit(properties.get(key) or '');editor.setObjectName('entity-property-'+key);property_editors[key]=editor;form.addRow(label,editor)
        active=QComboBox();active.setObjectName('entity-property-active')
        for label,value in (('Sin indicar',None),('Sí',True),('No',False)):active.addItem(label,value)
        active.setCurrentIndex(0 if properties.get('active') is None else 1 if properties['active'] else 2);form.addRow('Entidad activa',active)
        scroll.setWidget(body);layout.addWidget(scroll);bottom=QFormLayout();layout.addLayout(bottom);buttons(dialog,bottom)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            values={k:v.text() for k,v in editors.items()};values['role']=role.value()
            extra={k:v.text().strip() or None for k,v in property_editors.items()};extra['active']=active.currentData()
            for key in ('quantity','gross_area'):
                if extra[key] is not None:extra[key]=extra[key].replace(',','.')
            if (old and 'properties' in old) or any(v is not None for v in extra.values()):values['properties']=extra
            self.host._execute('entities.set',values=values,entity_id=old['id'] if old else None)
