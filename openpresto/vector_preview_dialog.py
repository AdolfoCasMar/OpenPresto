"""Zoomable native SVG preview of generated geometry only."""
from PySide6.QtCore import QByteArray,Qt,QTimer
from PySide6.QtGui import QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtSvgWidgets import QGraphicsSvgItem
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QGraphicsScene,QGraphicsView


class VectorView(QGraphicsView):
    def zoom(self,factor):
        current=self.transform().m11()
        if current<=0:return
        target=max(.02,min(50,current*factor));self.scale(target/current,target/current)
    def wheelEvent(self,event):
        delta=event.angleDelta().y()
        if delta:self.zoom(1.25 if delta>0 else .8);event.accept()
        else:super().wheelEvent(event)


class VectorPreviewDialog(QDialog):
    def __init__(self,vector,parent=None,repaired=False):
        super().__init__(parent);self.setWindowTitle('Vista de dibujo');self.resize(1000,760);box=QVBoxLayout(self)
        text='Vista geométrica aproximada. No sustituye al dibujo original.'
        if repaired:text+=' Se muestra la copia con el cierre WMF corregido.'
        if vector['warnings']:text+=' Vista parcial: '+'; '.join(vector['warnings'])
        self.notice=QLabel(text);self.notice.setWordWrap(True);box.addWidget(self.notice);bar=QHBoxLayout();box.addLayout(bar)
        self.renderer=QSvgRenderer(QByteArray(vector['svg']),self);self.scene=QGraphicsScene(self);self.item=QGraphicsSvgItem();self.item.setSharedRenderer(self.renderer);self.scene.addItem(self.item);self.view=VectorView(self.scene,self);self.view.setObjectName('vector-view');self.view.setBackgroundBrush(Qt.GlobalColor.white);self.view.setRenderHint(QPainter.RenderHint.Antialiasing);self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag);self.view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        for title,name,callback in (('Acercar','vector-zoom-in',lambda:self.view.zoom(1.25)),('Alejar','vector-zoom-out',lambda:self.view.zoom(.8)),('Ajustar','vector-fit',self.fit),('Cerrar','vector-close',self.accept)):
            button=QPushButton(title);button.setObjectName(name);button.clicked.connect(callback);bar.addWidget(button)
        box.addWidget(self.view);QTimer.singleShot(0,self.fit)
    def fit(self):self.view.fitInView(self.item.boundingRect(),Qt.AspectRatioMode.KeepAspectRatio)
