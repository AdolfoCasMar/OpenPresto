"""Editable native text and asynchronous, read-only PZH document previews."""
from PySide6.QtCore import QObject,QRunnable,QThreadPool,Signal,Slot,QSignalBlocker,Qt
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QLabel,QTableWidget,QTabWidget,QPlainTextEdit,QDialog,QFormLayout,QLineEdit,QFileDialog
from .planning_panel import fill,buttons
from . import technical_documents as documents,pzh_entity_texts


class _Signals(QObject):
    ready=Signal(int,str,object,str)


class _Read(QRunnable):
    def __init__(self,generation,kind,budget,code=None,parent=None):
        super().__init__();self.generation=generation;self.kind=kind;self.budget=budget;self.code=code;self.signals=_Signals(parent)
    def run(self):
        try:
            result=pzh_entity_texts.catalogue(self.budget) if self.kind=='catalogue' else pzh_entity_texts.read(self.budget,self.code)
            self.signals.ready.emit(self.generation,self.kind,result,'')
        except Exception as exc:self.signals.ready.emit(self.generation,self.kind,None,str(exc))
        finally:self.signals.deleteLater()


class TechnicalDocumentsPanel(QWidget):
    def __init__(self,host):
        super().__init__(host);self.host=host;layout=QVBoxLayout(self);bar=QHBoxLayout()
        for label,callback in (('Nuevo texto…',lambda:self.edit(True)),('Editar copia…',self.edit),('Retirar copia',self.remove),('Copiar texto PZH',self.copy),('Exportar textos…',self.export)):
            button=QPushButton(label);button.clicked.connect(callback);bar.addWidget(button)
        layout.addLayout(bar);note=QLabel('Documentos editables independientes del presupuesto. Origen PZH permite consultar textos vinculados por el índice de entidades y crear copias de texto plano. El original conserva su formato; editar la copia no modifica el PZH.');note.setWordWrap(True);layout.addWidget(note)
        originals=QHBoxLayout();layout.addLayout(originals)
        for label,callback in (('Conservar original PZH',self.attach_original),('Exportar original…',self.export_original)):
            button=QPushButton(label);button.clicked.connect(callback);originals.addWidget(button)
        self.tabs=QTabWidget();layout.addWidget(self.tabs)
        native=QWidget();box=QVBoxLayout(native);self.table=QTableWidget();box.addWidget(self.table);self.text=QPlainTextEdit();self.text.setReadOnly(True);box.addWidget(self.text);self.tabs.addTab(native,'Copias editables')
        source=QWidget();box=QVBoxLayout(source);self.source_status=QLabel();self.source_status.setWordWrap(True);box.addWidget(self.source_status);self.source_table=QTableWidget();box.addWidget(self.source_table);self.source_text=QPlainTextEdit();self.source_text.setReadOnly(True);box.addWidget(self.source_text);self.tabs.addTab(source,'Origen PZH · textos de entidades')
        self.ids=[];self.source_rows=[];self._source_key=None;self._generation=0;self.pool=QThreadPool(self);self.pool.setMaxThreadCount(1)
        self.table.currentCellChanged.connect(self.select_native);self.table.cellDoubleClicked.connect(lambda *_:self.edit());self.source_table.currentCellChanged.connect(self.select_source)
        from .project_assets_panel import ProjectAssetsPanel
        self.assets=ProjectAssetsPanel(host);self.tabs.addTab(self.assets,'Adjuntos y textos PZH')
    def render(self):
        self.assets.render()
        current=self.ids[self.table.currentRow()] if 0<=self.table.currentRow()<len(self.ids) else None;rows=documents.validate(self.host.budget);self.ids=[r['id'] for r in rows];block=QSignalBlocker(self.table);fill(self.table,documents.HEADERS,documents.report_rows(self.host.budget));self.table.setColumnHidden(0,True);del block
        if self.ids:self.table.setCurrentCell(self.ids.index(current) if current in self.ids else 0,1)
        else:self.text.clear()
        self.select_native()
        archive=self.host.budget.project_metadata.get('pzh_source_archive_v1');key=(self.host.budget.project_metadata.get('import_sha256'),archive)
        if key!=self._source_key:
            self._source_key=key;self._generation+=1;self.pool.clear();self.source_rows=[];self.source_text.clear();fill(self.source_table,('Código','Título','Bytes de texto'),[])
            if archive:self.source_status.setText('Leyendo índice de textos…');self._start('catalogue')
            else:self.source_status.setText('Este proyecto no conserva textos de un PZH original.')
    def _start(self,kind,code=None):
        worker=_Read(self._generation,kind,self.host.budget,code,self);worker.signals.ready.connect(self._ready,Qt.ConnectionType.QueuedConnection);self.pool.start(worker)
    @Slot(int,str,object,str)
    def _ready(self,generation,kind,result,error):
        if generation!=self._generation:return
        if error:
            self.source_status.setText('Texto de origen no disponible: '+error);self.source_text.clear();return
        if kind=='catalogue':
            self.source_rows=result;block=QSignalBlocker(self.source_table);fill(self.source_table,('Código','Título','Bytes de texto'),[(r['code'],r['title'],r['unpacked']) for r in result]);del block;self.source_status.setText(f'Textos de entidades disponibles: {len(result)}. Se descomprime solo el texto seleccionado.')
            if result:self.source_table.setCurrentCell(0,0)
        else:self.source_text.setPlainText(result['text']);self.source_status.setText('Texto de origen consultado; crea una copia para editarlo.')
    def select_native(self,*_):
        i=self.table.currentRow();rows=documents.validate(self.host.budget)
        row=next((r for r in rows if 0<=i<len(self.ids) and r['id']==self.ids[i]),None);self.text.setPlainText(row['text'] if row else '')
    def select_source(self,*_):
        i=self.source_table.currentRow()
        if not 0<=i<len(self.source_rows):return
        self._generation+=1;self.pool.clear();self.source_text.setPlainText('Cargando texto…');self._start('text',self.source_rows[i]['code'])
    def edit(self,new=False):
        i=self.table.currentRow();old=None if new else next((r for r in documents.validate(self.host.budget) if 0<=i<len(self.ids) and r['id']==self.ids[i]),None)
        if not new and (self.tabs.currentIndex()!=0 or old is None):self.host._error('Selecciona una copia editable.');return
        dialog=QDialog(self);dialog.setWindowTitle('Documento técnico');dialog.resize(780,620);form=QFormLayout(dialog);reference=QLineEdit(old['reference'] if old else '');reference.setObjectName('technical-reference');form.addRow('Referencia',reference);title=QLineEdit(old['title'] if old else '');title.setObjectName('technical-title');form.addRow('Título',title);text=QPlainTextEdit(old['text'] if old else '');text.setObjectName('technical-text');form.addRow('Texto plano',text);buttons(dialog,form)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.host._execute('technical.document.set',reference=reference.text(),title=title.text(),text=text.toPlainText(),document_id=old['id'] if old else None)
    def remove(self):
        i=self.table.currentRow()
        if self.tabs.currentIndex()!=0 or not 0<=i<len(self.ids):self.host._error('Selecciona una copia editable.');return
        self.host._execute('technical.document.remove',document_id=self.ids[i])
    def copy(self):
        i=self.source_table.currentRow()
        if self.tabs.currentIndex()!=1 or not 0<=i<len(self.source_rows):self.host._error('Selecciona un texto en Origen PZH.');return
        code=self.source_rows[i]['code'];self.host._execute('technical.document.copy_pzh',code=code)
        matches=[r for r in documents.validate(self.host.budget) if r['source'] and r['source']['code']==code]
        if matches:self.tabs.setCurrentIndex(0);self.table.setCurrentCell(self.ids.index(matches[-1]['id']),1)
    def export(self):
        from .report_actions import export_report
        export_report(self.host,'documentos_tecnicos_contenido')
    def attach_original(self):
        i=self.table.currentRow()
        if self.tabs.currentIndex()!=0 or not 0<=i<len(self.ids):self.host._error('Selecciona una copia editable.');return
        self.host._execute('technical.document.attach_original',document_id=self.ids[i])
    def export_original(self):
        from pathlib import Path
        i=self.table.currentRow()
        if self.tabs.currentIndex()!=0 or not 0<=i<len(self.ids):self.host._error('Selecciona una copia editable.');return
        try:
            payload=documents.original_payload(self.host.budget,self.ids[i]);extension='rtf' if payload.startswith(b'{\\rtf') else 'txt'
            path,_=QFileDialog.getSaveFileName(self,'Exportar documento original','documento-original.'+extension,'Documento original (*.'+extension+')')
            if path:Path(path).write_bytes(payload)
        except Exception as exc:self.host._error(str(exc))
