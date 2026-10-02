"""User interface and canvas colours; exported pages always use light ink."""
from PySide6.QtGui import QColor,QPalette,QIcon,QPixmap,QPainter
from PySide6.QtCore import QSize


def application_icon(directory):
    """Let Qt select the supplied logo resolution for each window and DPI."""
    icon = QIcon()
    for size in (72,144,432,576):
        path = directory / f"Ikonka ElektroSchema {size}x{size}.png"
        if path.is_file():
            icon.addFile(str(path),QSize(size,size))
    # Support older installations that still have the original single logo.
    if icon.isNull():
        icon.addFile(str(directory / "Ikonka ElektroSchema.png"))
    return icon


def themed_icon(path,dark=False):
    icon=QIcon(str(path))
    if not dark or icon.isNull(): return icon
    return tint_icon(icon)


def tint_icon(icon):
    result=QIcon()
    for size in (24,36,48,96):
        source=icon.pixmap(size,size)
        pixmap=QPixmap(source.size()); pixmap.fill(QColor(0,0,0,0))
        painter=QPainter(pixmap); painter.drawPixmap(0,0,source)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(),QColor("#dce8f3")); painter.end()
        result.addPixmap(pixmap)
    return result


def canvas_colors(settings):
    if getattr(settings,"theme","light")=="dark":
        # sRGB #dadada is approximately 70% of white's linear luminance.
        # This affects the sheet only, never monitor brightness or exports.
        return dict(paper="#dadada",faint_paper="#d6d6d6",outside="#0f161f",
                    ink="#102536",wire="#126432",grid="#c7ccd1",dots="#87929b",
                    frame="#4b5660",table="#dadada",selected="#873400")
    return dict(paper="#ffffff",faint_paper="#faf9f6",outside="#e5ebf0",
                ink="#163247",wire="#167d3d",grid="#e7edf1",dots="#939b9f",
                frame="#667786",table="#ffffff",selected="#df6b45")


def apply_theme(window,settings):
    dark=getattr(settings,"theme","light")=="dark"
    bg,base,ink,border,hover,selected,muted=(
        ("#17212d","#202c3a","#e0e9f2","#415469","#2c4155","#315772","#899aab") if dark else
        ("#f6f9fc","#ffffff","#162a3a","#d6e1ea","#e6f3f7","#ccecf5","#8a98a2"))
    palette=QPalette(window.palette())
    for role,value in ((QPalette.ColorRole.Window,bg),(QPalette.ColorRole.Base,base),
                       (QPalette.ColorRole.AlternateBase,hover),(QPalette.ColorRole.WindowText,ink),
                       (QPalette.ColorRole.Text,ink),(QPalette.ColorRole.Button,base),
                       (QPalette.ColorRole.ButtonText,ink),(QPalette.ColorRole.ToolTipBase,base),
                       (QPalette.ColorRole.ToolTipText,ink),(QPalette.ColorRole.Highlight,selected),
                       (QPalette.ColorRole.HighlightedText,ink),(QPalette.ColorRole.Link,"#56b9ee" if dark else "#096b92"),
                       (QPalette.ColorRole.PlaceholderText,muted)):
        palette.setColor(role,QColor(value))
    for role in (QPalette.ColorRole.Text,QPalette.ColorRole.ButtonText,QPalette.ColorRole.WindowText):
        palette.setColor(QPalette.ColorGroup.Disabled,role,QColor(muted))
    window.setPalette(palette)
    window.setStyleSheet(f"""
        QWidget {{background:{bg};color:{ink};}}
        QLabel {{background:transparent;}}
        QMenuBar,QMenu,QStatusBar,QToolBar {{background:{base};color:{ink};}}
        QMenu::item:selected,QComboBox QAbstractItemView::item:selected {{background:{selected};color:{ink};}}
        QToolBar {{border:1px solid {border};spacing:6px;padding:5px;}}
        QToolButton {{min-width:38px;min-height:38px;border-radius:5px;}}
        QToolButton:hover,QPushButton:hover {{background:{hover};}}
        QToolButton:checked,QPushButton:pressed {{background:{selected};}}
        QAbstractButton:disabled {{color:{muted};}}
        QPushButton {{background:{base};border:1px solid {border};border-radius:4px;padding:5px 9px;}}
        QLineEdit,QTextEdit,QPlainTextEdit,QTextBrowser,QTableWidget,QComboBox,QSpinBox,QDoubleSpinBox {{
            background:{base};color:{ink};selection-background-color:{selected};border:1px solid {border};
        }}
        QComboBox QAbstractItemView {{background:{base};color:{ink};}}
        QHeaderView::section {{background:{hover};color:{ink};border:1px solid {border};padding:4px;}}
        QTabBar::tab {{background:{base};color:{ink};padding:6px 10px;}}
        QTabBar::tab:selected {{background:{selected};}}
        QTabWidget::pane {{border:0;}}
        QDialogButtonBox QPushButton {{min-width:80px;}}
        QToolTip {{background:{base};color:{ink};border:1px solid {border};}}
    """)
