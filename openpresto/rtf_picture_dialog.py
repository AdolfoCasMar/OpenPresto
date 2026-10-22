"""Consult and export source RTF pictures without activating embedded objects."""
from pathlib import Path
import struct
from PySide6.QtCore import QObject,QRunnable,QThreadPool,Signal,Slot,Qt,QByteArray,QBuffer,QIODevice,QSize
from PySide6.QtGui import QImageReader,QImage,QPainter,QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTableWidget,QFileDialog
from .budget import BudgetError
from . import rtf_pictures,wmf_vector
from .planning_panel import fill
from .vector_preview_dialog import VectorPreviewDialog


def decode_picture(row):
    result=dict(image=None,vector=None,warning='',size=None)
    try:
        payload=row['data'];fmt=row['format']
        if fmt=='wmf':
            vector=wmf_vector.preview(rtf_pictures.wmf_stream(payload));renderer=QSvgRenderer(QByteArray(vector['svg']))
            if not renderer.isValid():raise BudgetError('Vista WMF no representable')
            size=renderer.defaultSize();size.scale(1200,1200,Qt.AspectRatioMode.KeepAspectRatio);size.setWidth(max(1,size.width()));size.setHeight(max(1,size.height()));image=QImage(size,QImage.Format.Format_ARGB32);image.fill(Qt.GlobalColor.white);painter=QPainter(image)
            try:renderer.render(painter)
            finally:painter.end()
            result.update(image=image,vector=vector,warning='Vista WMF aproximada'+(': '+'; '.join(vector['warnings']) if vector['warnings'] else ''))
        elif fmt in ('png','jpg','dib'):
            if fmt=='dib':payload=rtf_pictures.dib_bitmap(payload)
            buffer=QBuffer();buffer.setData(QByteArray(payload));buffer.open(QIODevice.OpenModeFlag.ReadOnly);reader=QImageReader(buffer);size=reader.size()
            if fmt=='dib':
                width,height=struct.unpack_from('<ii',row['data'],4);size=QSize(width,abs(height))
            if not size.isValid() or size.width()>20000 or size.height()>20000 or not 0<size.width()*size.height()<=16000000:raise BudgetError('La imagen no declara dimensiones admitidas para la vista previa')
            result['size']=(size.width(),size.height())
            if size.width()>1200 or size.height()>1200:size.scale(1200,1200,Qt.AspectRatioMode.KeepAspectRatio);reader.setScaledSize(size)
            image=reader.read()
            if image.isNull():raise BudgetError('No se ha podido representar la imagen; puedes exportar sus bytes originales')
            result['image']=image
        else:result['warning']='Formato sin vista previa. El contenido original puede exportarse.'
    except Exception as exc:result['warning']='Vista previa no disponible: '+str(exc)
    return result


class _Signals(QObject):ready=Signal(int,object)


class _Decode(QRunnable):
    def __init__(self,generation,row):
        super().__init__();self.generation=generation;self.row=row;self.signals=_Signals()
    def run(self):self.signals.ready.emit(self.generation,decode_picture(self.row))


class RTFPictureDialog(QDialog):
    def __init__(self,report,parent=None):
        super().__init__(parent);self.setWindowTitle('Imágenes del RTF original');self.resize(950,740);self.report=report;self.rows=report['pictures'];self.current=None;self.generation=0;self.pool=QThreadPool(self);self.pool.setMaxThreadCount(1)
        box=QVBoxLayout(self);self.notice=QLabel(f"Imágenes disponibles: {len(self.rows)}. Objetos en el documento de origen: {report['objects']}. Las imágenes alternativas se muestran por separado. La copia de texto editable no las inserta automáticamente. Los objetos permanecen en el original y no se activan.");self.notice.setWordWrap(True);box.addWidget(self.notice);bar=QHBoxLayout();box.addLayout(bar)
        for title,name,callback in (('Exportar imagen original…','rtf-picture-export',self.export_original),('Exportar vista PNG…','rtf-picture-png',self.export_view),('Ampliar dibujo…','rtf-picture-vector',self.open_vector),('Cerrar','rtf-picture-close',self.accept)):
            button=QPushButton(title);button.setObjectName(name);button.clicked.connect(callback);bar.addWidget(button)
        self.table=QTableWidget();self.table.setObjectName('rtf-picture-list');box.addWidget(self.table)
        def role(row):return 'Vista de objeto' if row['object_preview'] else {'normal':'Imagen','shppict':'Principal','nonshppict':'Alternativa'}.get(row['role'],'Imagen')
        fill(self.table,('N.º','Formato','Bytes originales','Origen','Observaciones'),[(row['id'],row['format'],len(row['data']),role(row),'; '.join(row['warnings'])) for row in self.rows]);self.status=QLabel('Selecciona una imagen para consultarla.');self.status.setWordWrap(True);box.addWidget(self.status);self.image=QLabel();self.image.setAlignment(Qt.AlignmentFlag.AlignCenter);box.addWidget(self.image,1);self.table.currentCellChanged.connect(self.select)
        if self.rows:self.table.setCurrentCell(0,0)
    def selected(self):
        index=self.table.currentRow()
        return self.rows[index] if 0<=index<len(self.rows) else None
    def select(self,*_):
        self.generation+=1;self.pool.clear();self.current=None;self.image.clear();row=self.selected()
        if row is None:return
        self.status.setText('Leyendo la imagen seleccionada…');worker=_Decode(self.generation,row);worker.signals.ready.connect(self.ready);self.pool.start(worker)
    @Slot(int,object)
    def ready(self,generation,result):
        if generation!=self.generation:return
        self.current=result;row=self.selected()
        if row is None:return
        text=f"Imagen {row['id']} · {row['format']} · {len(row['data'])} bytes originales"
        if result['size']:text+=f" · {result['size'][0]} × {result['size'][1]} píxeles"
        if result['warning']:text+=' · '+result['warning']
        self.status.setText(text)
        if result['image'] is not None:self.image.setPixmap(QPixmap.fromImage(result['image']).scaled(800,400,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
    def export_original(self):
        row=self.selected()
        if row is None:return
        ext=row['format'];path,_=QFileDialog.getSaveFileName(self,'Exportar imagen original',f"imagen-{row['id']}.{ext}",f'Archivo (*.{ext})')
        if path:
            try:Path(path).write_bytes(row['data']);self.status.setText('Imagen original exportada sin modificar sus bytes.')
            except OSError as exc:self.status.setText(str(exc))
    def export_view(self):
        if not self.current or self.current['image'] is None:self.status.setText('Espera a que haya una vista previa disponible.');return
        path,_=QFileDialog.getSaveFileName(self,'Exportar vista; puede estar reducida o ser aproximada','vista-imagen.png','Vista PNG (*.png)')
        if path and not self.current['image'].save(path,'PNG'):self.status.setText('No se ha podido guardar la vista PNG.')
    def open_vector(self):
        if not self.current or self.current['vector'] is None:self.status.setText('La imagen seleccionada no tiene una vista vectorial disponible.');return
        dialog=VectorPreviewDialog(self.current['vector'],self)
        try:dialog.exec()
        finally:dialog.deleteLater()
    def done(self,result):
        self.generation+=1;self.pool.clear();super().done(result)
