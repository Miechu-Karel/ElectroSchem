"""Apply one shared presentation preference to editor and simulation."""
def show_window(window, settings):
    mode=getattr(settings,"window_mode","maximized")
    if mode=="fullscreen": window.showFullScreen()
    elif mode=="windowed": window.showNormal()
    else: window.showMaximized()
