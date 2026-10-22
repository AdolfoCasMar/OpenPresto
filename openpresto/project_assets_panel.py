"""Attachment preview on demand; importing an index never decodes all streams."""
from pathlib import Path
from PySide6.QtCore import QObject,QRunnable,QThreadPool,Signal,Slot,QSignalBlocker,Qt,QBuffer,QByteArray,QIODevice
from PySide6.QtGui import QImageReader,QPixmap,QImage,QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget,QVBoxLayout,QGridLayout,QPushButton,QTableWidget,QLabel,QPlainTextEdit,QDialog,QFormLayout,QLineEdit,QFileDialog
from .planning_panel import fill,buttons
from . import project_assets as engine
from . import rich_documents
from .pzh_text import rtf_rich_runs
from .rich_text_editor import RichTextDialog,RichTextEditor,set_runs
from . import wmf_vector
from .vector_preview_dialog import VectorPreviewDialog
from .rtf_pictures import scan as scan_rtf_pictures
from .rtf_picture_dialog import RTFPictureDialog


class _Signals(QObject):ready=Signal(int,object,str)


class _Read(QRunnable):
    def __init__(self,generation,budget,identifier,parent=None):
        super().__init__();self.generation=generation;self.budget=budget;self.identifier=identifier;self.signals=_Signals(parent)
    def run(self):
        try:
            data=engine.read(self.budget,self.identifier);data['image']=None;data['vector']=None;data['vector_warning']=''
            data['runs']=None;data['format_warning']='';data['rtf_pictures']=None;data['picture_warning']=''
            if data['original']['format']=='rtf':
                try:data['rtf_pictures']=scan_rtf_pictures(data['original']['payload'])
                except Exception as exc:data['picture_warning']='No se ha podido interpretar el índice de imágenes del RTF: '+str(exc)
            if data['text'] is not None:
                try:
                    data['runs']=data.get('rich_text')
                    if data['runs'] is None:
                        data['runs']=rtf_rich_runs(data['original']['payload']) if data['text']==data['original']['text'] and data['original']['format']=='rtf' else rich_documents.from_plain(data['text'])
                    rich_documents.validate(data['runs'])
                except Exception:
                    data['runs']=None;data['format_warning']=' · Formato no proyectable: se muestra el texto disponible'
            if data['original']['format'] in ('jpg','bmp','png','gif'):
                buffer=QBuffer();buffer.setData(QByteArray(data['original']['export']));buffer.open(QIODevice.OpenModeFlag.ReadOnly);reader=QImageReader(buffer);size=reader.size()
                if size.isValid() and 0<size.width()*size.height()<=16000000:data['image']=reader.read()
            if data['original']['format'] in ('wmf','wmf-damaged'):
                try:
                    original=data['original'];stream=original['repair']['data'] if original['repair'] else original['export'];vector=wmf_vector.preview(stream);data['vector']=vector
                    renderer=QSvgRenderer(QByteArray(vector['svg']))
                    if not renderer.isValid():raise ValueError('La proyección SVG no es representable')
                    size=renderer.defaultSize();size.scale(1200,1200,Qt.AspectRatioMode.KeepAspectRatio);size.setWidth(max(1,size.width()));size.setHeight(max(1,size.height()));image=QImage(size,QImage.Format.Format_ARGB32);image.fill(Qt.GlobalColor.white);painter=QPainter(image)
                    try:renderer.render(painter)
                    finally:painter.end()
                    data['image']=image
                except Exception as exc:data['vector_warning']='Vista vectorial no disponible: '+str(exc)
            self.signals.ready.emit(self.generation,data,'')
        except Exception as exc:self.signals.ready.emit(self.generation,None,str(exc))
        finally:self.signals.deleteLater()


class ProjectAssetsPanel(QWidget):
    def __init__(self,host):
        super().__init__(host);self.host=host;box=QVBoxLayout(self);bar=QGridLayout();box.addLayout(bar)
        for i,(title,callback) in enumerate((('Copiar índice PZH',lambda:host._execute('assets.copy_pzh')),('Editar…',self.edit),('Texto con formato…',self.edit_rich),('Exportar copia RTF…',self.export_rich),('Exportar archivo…',self.export),('Exportar envoltura original…',lambda:self.export(True)),('Exportar copia WMF reparada…',self.export_repaired_wmf),('Exportar vista SVG…',self.export_vector),('Ampliar dibujo…',self.open_vector),('Imágenes RTF…',self.open_pictures))):
            button=QPushButton(title);button.clicked.connect(callback);bar.addWidget(button,i//3,i%3)
        self.status=QLabel('Textos, imágenes y dibujos del PZH. Se lee solo el adjunto seleccionado.');self.status.setWordWrap(True);box.addWidget(self.status);self.table=QTableWidget();box.addWidget(self.table);self.preview=RichTextEditor();self.preview.setReadOnly(True);box.addWidget(self.preview);self.image=QLabel();self.image.setAlignment(Qt.AlignmentFlag.AlignCenter);box.addWidget(self.image);self.ids=[];self._generation=0;self.current=None;self._signature=None;self.pool=QThreadPool(self);self.pool.setMaxThreadCount(1);self.table.currentCellChanged.connect(self.select)
    def render(self):
        signature=self.host.budget.project_metadata.get(engine.KEY),self.host.budget.project_metadata.get('pzh_source_archive_v1')
        if signature==self._signature:return
        self._signature=signature;current=self.ids[self.table.currentRow()] if 0<=self.table.currentRow()<len(self.ids) else None;self.ids=[r['id'] for r in engine.validate(self.host.budget)];block=QSignalBlocker(self.table);fill(self.table,engine.HEADERS,engine.report_rows(self.host.budget));self.table.setColumnHidden(0,True);del block
        if self.ids:self.table.setCurrentCell(self.ids.index(current) if current in self.ids else 0,1);self.select()
        else:self._generation+=1;self.current=None;self.preview.clear();self.image.clear()
    def select(self,*_):
        self._generation+=1;self.pool.clear();self.current=None;self.preview.clear();self.image.clear();i=self.table.currentRow()
        if not 0<=i<len(self.ids):return
        self.status.setText('Leyendo el adjunto seleccionado…');worker=_Read(self._generation,self.host.budget,self.ids[i],self);worker.signals.ready.connect(self.ready,Qt.ConnectionType.QueuedConnection);self.pool.start(worker)
    @Slot(int,object,str)
    def ready(self,generation,result,error):
        if generation!=self._generation:return
        if error:self.status.setText('Adjunto no disponible: '+error);return
        self.current=result;original=result['original'];self.status.setText(f"{result['title']} · {original['format']} · {original['bytes']} bytes. El archivo se exporta sin abrirlo ni ejecutarlo.");self.preview.setPlainText(result['text'] if result['text'] is not None else 'Documento binario. Exporta el archivo para utilizarlo en una aplicación compatible.')
        if result['runs'] is not None:
            set_runs(self.preview,result['runs'])
            self.status.setText(self.status.text()+' · Vista de formato básico; el original conserva el formato restante.')
        if result['format_warning']:self.status.setText(self.status.text()+result['format_warning'])
        if original.get('repair'):self.status.setText(self.status.text()+' · WMF con longitud de cierre cero. Puedes exportar una copia con el cierre corregido; el original no se modifica.')
        if result['vector'] is not None:
            vector=result['vector'];self.status.setText(self.status.text()+f' · Vista geométrica aproximada: {vector["elements"]} elementos.'+(' Vista parcial: '+ '; '.join(vector['warnings']) if vector['warnings'] else ''))
            if original.get('repair'):self.status.setText(self.status.text()+' La vista utiliza la copia con el cierre corregido.')
        if result['vector_warning']:self.status.setText(self.status.text()+' · '+result['vector_warning'])
        if result['rtf_pictures'] is not None:
            report=result['rtf_pictures'];self.status.setText(self.status.text()+f" · RTF original: {len(report['pictures'])} imágenes y {report['objects']} objetos. Consulta Imágenes RTF…")
        if result['picture_warning']:self.status.setText(self.status.text()+' · '+result['picture_warning'])
        if result['image'] is not None and not result['image'].isNull():self.image.setPixmap(QPixmap.fromImage(result['image']).scaled(600,320,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
    def edit(self):
        if not self.current:self.host._error('Selecciona un adjunto y espera a que termine de cargar.');return
        row=self.current;dialog=QDialog(self);dialog.setWindowTitle('Adjunto de la obra');dialog.resize(700,560);form=QFormLayout(dialog);title=QLineEdit(row['title']);note=QLineEdit(row['note']);title.setObjectName('asset-title');note.setObjectName('asset-note');form.addRow('Título',title);form.addRow('Nota',note);text=None
        if row['text'] is not None:text=QPlainTextEdit(row['text']);text.setObjectName('asset-text');form.addRow('Copia de texto editable · conserva el original',text)
        buttons(dialog,form)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.host._execute('assets.set',asset_id=row['id'],title=title.text(),note=note.text(),text=text.toPlainText() if text else None)
    def export(self,envelope=False):
        if not self.current:self.host._error('Selecciona un adjunto y espera a que termine de cargar.');return
        original=self.current['original'];ext='bin' if envelope or original['format']=='wmf-damaged' else original['format'];path,_=QFileDialog.getSaveFileName(self,'Exportar adjunto','adjunto.'+ext,'Archivo (*.'+ext+')')
        if path:
            try:Path(path).write_bytes(original['payload'] if envelope else original['export'])
            except OSError as exc:self.host._error(str(exc))
    def edit_rich(self):
        if not self.current or self.current['runs'] is None:self.host._error('Selecciona un texto compatible y espera a que termine de cargar.');return
        dialog=RichTextDialog(self.current['runs'],self)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            try:self.host._execute('assets.richtext.set',asset_id=self.current['id'],runs=dialog.runs())
            except Exception as exc:self.host._error(str(exc))
    def export_rich(self):
        if not self.current or self.current['runs'] is None:self.host._error('Selecciona un texto compatible y espera a que termine de cargar.');return
        path,_=QFileDialog.getSaveFileName(self,'Exportar copia con formato','texto-editado.rtf','Texto enriquecido (*.rtf)')
        if path:
            try:Path(path).write_bytes(rich_documents.to_rtf(self.current['runs']))
            except (OSError,ValueError) as exc:self.host._error(str(exc))
    def export_repaired_wmf(self):
        repair=self.current['original'].get('repair') if self.current else None
        if repair is None:self.host._error('El adjunto seleccionado no tiene una reparación de cierre WMF verificada.');return
        path,_=QFileDialog.getSaveFileName(self,'Exportar copia WMF con cierre corregido','dibujo-copia-reparada.wmf','Metarchivo (*.wmf)')
        if path:
            try:Path(path).write_bytes(repair['data'])
            except OSError as exc:self.host._error(str(exc))
    def export_vector(self):
        vector=self.current.get('vector') if self.current else None
        if vector is None:self.host._error('Selecciona un dibujo con una vista vectorial disponible.');return
        path,_=QFileDialog.getSaveFileName(self,'Exportar vista aproximada; no sustituye al original','vista-dibujo.svg','Vista vectorial (*.svg)')
        if path:
            try:Path(path).write_bytes(vector['svg'])
            except OSError as exc:self.host._error(str(exc))
    def open_vector(self):
        vector=self.current.get('vector') if self.current else None
        if vector is None:self.host._error('Selecciona un dibujo con una vista vectorial disponible.');return
        dialog=VectorPreviewDialog(vector,self,repaired=self.current['original'].get('repair') is not None)
        try:dialog.exec()
        finally:dialog.deleteLater()
    def open_pictures(self):
        report=self.current.get('rtf_pictures') if self.current else None
        if report is None:self.host._error('Selecciona un documento RTF y espera a que termine de cargar.');return
        dialog=RTFPictureDialog(report,self)
        try:dialog.exec()
        finally:dialog.deleteLater()
