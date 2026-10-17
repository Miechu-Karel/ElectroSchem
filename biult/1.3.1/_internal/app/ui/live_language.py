"""Translate existing simulator widgets without restarting their circuit."""
from PySide6.QtWidgets import QLabel,QAbstractButton,QComboBox,QTabWidget,QTableWidget,QPlainTextEdit
from app.core.messages import localize


def phrase(owner,en,pl):
    if not hasattr(owner,"_phrases"): owner._phrases={}
    owner._phrases[en]=(en,pl)
    return pl if owner.pl else en


def refresh(owner,language):
    old=owner.pl; owner.pl=language=="pl"
    pairs=list(getattr(owner,"_phrases",{}).values())
    from app.libraries.built_in import AVAILABLE_ITEMS,item_name
    pairs += [(item_name(d,"en"),item_name(d,"pl")) for d in AVAILABLE_ITEMS]
    translations={pair[old]:pair[owner.pl] for pair in pairs}
    def text(value):
        if value in translations: return translations[value]
        for source,target in sorted(translations.items(),key=lambda p:len(p[0]),reverse=True):
            if source and source!=target: value=value.replace(source,target)
        return localize(value,language)
    owner.setWindowTitle(text(owner.windowTitle()))
    for widget in owner.findChildren(QLabel)+owner.findChildren(QAbstractButton): widget.setText(text(widget.text()))
    for widget in owner.findChildren(QComboBox):
        for i in range(widget.count()): widget.setItemText(i,text(widget.itemText(i)))
    for widget in owner.findChildren(QTabWidget):
        for i in range(widget.count()): widget.setTabText(i,text(widget.tabText(i)))
    for widget in owner.findChildren(QTableWidget):
        for col in range(widget.columnCount()):
            header=widget.horizontalHeaderItem(col)
            if header: header.setText(text(header.text()))
            for row in range(widget.rowCount()):
                item=widget.item(row,col)
                if item: item.setText(text(item.text())); item.setToolTip(text(item.toolTip()))
    for widget in owner.findChildren(LocalizedLog): widget.setPlainText(text(widget.toPlainText()))


class LocalizedLog(QPlainTextEdit):
    def __init__(self,language):
        super().__init__(); self.language=language
    def setPlainText(self,text): super().setPlainText(localize(text,self.language()))
    def appendPlainText(self,text): super().appendPlainText(localize(text,self.language()))
