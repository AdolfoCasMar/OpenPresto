"""Qt adapter for native text runs; paste accepts plain text, never resources."""
from PySide6.QtCore import QSignalBlocker,Qt
from PySide6.QtGui import QFont,QTextCharFormat,QTextCursor,QTextDocument,QColor,QBrush,QTextBlockFormat
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QTextEdit,QToolButton,QDoubleSpinBox,QLabel,QDialogButtonBox,QComboBox
from . import rich_documents


def char_format(run):
    fmt=QTextCharFormat();fmt.setFontWeight(QFont.Weight.Bold if run['bold'] else QFont.Weight.Normal)
    fmt.setFontItalic(run['italic']);fmt.setFontUnderline(run['underline']);fmt.setFontStrikeOut(run['strike']);fmt.setFontPointSize(run['size'])
    if 'color' in run:fmt.setForeground(QColor(run['color']))
    return fmt


def set_runs(editor,runs):
    rich_documents.validate(runs);editor.clear();cursor=editor.textCursor()
    for run in runs:
        block=QTextBlockFormat();block.setAlignment(ALIGNMENTS[run.get('alignment','left')])
        for index,text in enumerate(run['text'].split('\n')):
            if index:cursor.insertBlock()
            cursor.setBlockFormat(block);cursor.insertText(text,char_format(run))
    cursor.movePosition(QTextCursor.MoveOperation.Start);editor.setTextCursor(cursor)


def get_runs(editor):
    runs=[];block=editor.document().begin()
    def add(text,fmt,block_format):
        row=dict(text=text,bold=fmt.fontWeight()>=QFont.Weight.Bold,italic=fmt.fontItalic(),underline=fmt.fontUnderline(),strike=fmt.fontStrikeOut(),size=fmt.fontPointSize() or 12)
        if fmt.foreground().style()!=Qt.BrushStyle.NoBrush:row['color']=fmt.foreground().color().name()
        alignment=next((key for key,value in ALIGNMENTS.items() if block_format.alignment()&value),'left')
        if alignment!='left':row['alignment']=alignment
        if runs and all(runs[-1][k]==v for k,v in row.items() if k!='text'):runs[-1]['text']+=text
        else:runs.append(row)
    while block.isValid():
        iterator=block.begin();last=block.charFormat();block_format=block.blockFormat()
        while not iterator.atEnd():
            fragment=iterator.fragment()
            if fragment.isValid():last=fragment.charFormat();add(fragment.text(),last,block_format)
            iterator+=1
        block=block.next()
        if block.isValid():add('\n',last,block_format)
    return rich_documents.validate(runs)


class LocalTextDocument(QTextDocument):
    def loadResource(self,kind,url):return None


ALIGNMENTS={'left':Qt.AlignmentFlag.AlignLeft,'center':Qt.AlignmentFlag.AlignHCenter,
            'right':Qt.AlignmentFlag.AlignRight,'justify':Qt.AlignmentFlag.AlignJustify}


class RichTextEditor(QTextEdit):
    def __init__(self,parent=None):
        super().__init__(parent);self.setDocument(LocalTextDocument(self));self.setAcceptRichText(False)
        font=QFont();font.setPointSizeF(12);self.document().setDefaultFont(font)


class RichTextDialog(QDialog):
    def __init__(self,runs,parent=None):
        super().__init__(parent);self.setWindowTitle('Texto con formato');self.resize(780,600);box=QVBoxLayout(self);bar=QHBoxLayout();box.addLayout(bar)
        self.editor=RichTextEditor(self);self.editor.setObjectName('asset-rich-text');self.styles={}
        for key,label in (('bold','Negrita'),('italic','Cursiva'),('underline','Subrayado'),('strike','Tachado')):
            button=QToolButton(self);button.setText(label);button.setCheckable(True);button.setObjectName('rich-'+key);button.clicked.connect(lambda checked,k=key:self.apply_style(k,checked));bar.addWidget(button);self.styles[key]=button
        self.size=QDoubleSpinBox(self);self.size.setObjectName('rich-size');self.size.setRange(1,200);self.size.setDecimals(1);self.size.setSingleStep(.5);self.size.setSuffix(' pt');self.size.setValue(12);self.size.valueChanged.connect(self.apply_size);bar.addWidget(self.size);box.addWidget(self.editor)
        self.color=QComboBox(self);self.color.setObjectName('rich-color');self.color.addItem('Color automático',None)
        for label,value in (('Negro','#000000'),('Azul','#245a9b'),('Rojo','#b32d35'),('Verde','#287445'),('Gris','#626970')):self.color.addItem(label,value)
        self.color.currentIndexChanged.connect(self.apply_color);bar.addWidget(self.color)
        self.alignment=QComboBox(self);self.alignment.setObjectName('rich-alignment')
        for label,value in (('Izquierda','left'),('Centrado','center'),('Derecha','right'),('Justificado','justify')):self.alignment.addItem(label,value)
        self.alignment.currentIndexChanged.connect(self.apply_alignment);bar.addWidget(self.alignment)
        info=QLabel('Copia editable: estilos, color de letra y alineación de párrafos. Las tablas, imágenes y objetos incrustados permanecen en el RTF original.');info.setWordWrap(True);box.addWidget(info)
        actions=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel,self);actions.accepted.connect(self.accept);actions.rejected.connect(self.reject);box.addWidget(actions)
        set_runs(self.editor,runs);self.editor.currentCharFormatChanged.connect(self.sync);self.sync(self.editor.currentCharFormat())
        self.editor.cursorPositionChanged.connect(lambda:self.sync(self.editor.currentCharFormat()))
    def apply_color(self,index):
        value=self.color.itemData(index);fmt=QTextCharFormat();fmt.setForeground(QColor(value) if value else QBrush())
        self.editor.mergeCurrentCharFormat(fmt);self.editor.setFocus()
    def apply_alignment(self,index):
        fmt=QTextBlockFormat();fmt.setAlignment(ALIGNMENTS[self.alignment.itemData(index)])
        cursor=self.editor.textCursor();cursor.mergeBlockFormat(fmt);self.editor.setTextCursor(cursor);self.editor.setFocus()
    def apply_style(self,key,checked):
        fmt=QTextCharFormat()
        if key=='bold':fmt.setFontWeight(QFont.Weight.Bold if checked else QFont.Weight.Normal)
        else:getattr(fmt,{'italic':'setFontItalic','underline':'setFontUnderline','strike':'setFontStrikeOut'}[key])(checked)
        self.editor.mergeCurrentCharFormat(fmt);self.editor.setFocus()
    def apply_size(self,value):
        rounded=round(value*2)/2
        if rounded!=value:
            block=QSignalBlocker(self.size);self.size.setValue(rounded);del block
        fmt=QTextCharFormat();fmt.setFontPointSize(rounded);self.editor.mergeCurrentCharFormat(fmt)
    def sync(self,fmt):
        values=dict(bold=fmt.fontWeight()>=QFont.Weight.Bold,italic=fmt.fontItalic(),underline=fmt.fontUnderline(),strike=fmt.fontStrikeOut())
        for key,button in self.styles.items():
            block=QSignalBlocker(button);button.setChecked(values[key]);del block
        block=QSignalBlocker(self.size);self.size.setValue(fmt.fontPointSize() or 12);del block
        value=fmt.foreground().color().name() if fmt.foreground().style()!=Qt.BrushStyle.NoBrush else None
        block=QSignalBlocker(self.color);index=self.color.findData(value)
        if index<0:self.color.addItem(value,value);index=self.color.count()-1
        self.color.setCurrentIndex(index);del block
        alignment=self.editor.textCursor().blockFormat().alignment()
        value=next((key for key,flag in ALIGNMENTS.items() if alignment&flag),'left')
        block=QSignalBlocker(self.alignment);self.alignment.setCurrentIndex(self.alignment.findData(value));del block
    def runs(self):return get_runs(self.editor)
