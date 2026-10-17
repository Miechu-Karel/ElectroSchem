"""Read-only conversation cards; provider text is always HTML-escaped."""
from html import escape
from PySide6.QtWidgets import QTextBrowser

class Conversation(QTextBrowser):
    def __init__(self):
        super().__init__(); self.setOpenLinks(False)
    def appendPlainText(self,text):
        user=text.startswith(('You:','Ty:'))
        colour='#174566' if user else '#263747'
        self.append('<table width="100%" cellspacing="8"><tr><td bgcolor="'+colour+'" style="color:#f1f5f8;padding:12px">'+escape(text).replace('\n','<br>')+'</td></tr></table>')
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
