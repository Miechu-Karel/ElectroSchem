"""Large, honest supply-only previews for displays without image protocols."""
from PySide6.QtCore import QRectF,Qt
from PySide6.QtGui import QColor,QPen,QFont


def preview_rect(item):
    profile=item.display_profile
    r=item._hit_rect
    return QRectF(r.center().x()-profile.panel_width/2,
                  r.top()-profile.panel_height-12,
                  profile.panel_width,profile.panel_height)


def paint_preview(item,painter):
    profile=item.display_profile
    state=item.display_state or {}
    powered=bool(state.get("powered",False))
    panel=preview_rect(item)
    painter.save()
    painter.setPen(QPen(QColor("#59736d"),2))
    painter.setBrush(QColor("#18352d")); painter.drawRoundedRect(panel,4,4)
    available=panel.adjusted(12,12,-12,-28)
    ratio=profile.columns/profile.rows
    width=min(available.width(),available.height()*ratio)
    height=width/ratio
    screen=QRectF(available.center().x()-width/2,available.center().y()-height/2,width,height)
    painter.setPen(QPen(QColor("#536168"),1))
    background={"oled":"#030609","tft":"#10131b" if powered else "#080a0d",
                "epaper":"#e4e2d8","led_matrix":"#08090b","rgb_matrix":"#10151a"}[profile.kind]
    painter.setBrush(QColor(background)); painter.drawRect(screen)
    if profile.kind in {"led_matrix","rgb_matrix"}:
        painter.setPen(Qt.PenStyle.NoPen)
        for row in range(profile.rows):
            for col in range(profile.columns):
                cell=QRectF(screen.left()+col*screen.width()/profile.columns,
                            screen.top()+row*screen.height()/profile.rows,
                            screen.width()/profile.columns,screen.height()/profile.rows)
                inset=cell.width()*.19
                led=cell.adjusted(inset,inset,-inset,-inset)
                if profile.kind=="led_matrix":
                    painter.setBrush(QColor("#371418")); painter.drawEllipse(led)
                else:
                    painter.setBrush(QColor("#a6a9a0")); painter.drawRect(led)
                    painter.setBrush(QColor("#393d3b")); painter.drawEllipse(led.adjusted(inset,inset,-inset,-inset))
    # Do not light LEDs or invent a bitmap when the electrical model has no
    # image decoder. Make that limitation visible below the screen itself.
    label=("Model zasilania" if item.language=="pl" else "Supply-only model")
    label+=f" | {profile.columns}x{profile.rows}"
    painter.setPen(QColor("#c5d5df"))
    font=QFont("Segoe UI"); font.setPixelSize(11); painter.setFont(font)
    painter.drawText(QRectF(panel.left()+18,panel.bottom()-24,panel.width()-26,20),
                     Qt.AlignmentFlag.AlignCenter,label)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#47b975" if powered else "#4c535a"))
    painter.drawEllipse(QRectF(panel.left()+6,panel.bottom()-17,6,6))
    painter.restore()
