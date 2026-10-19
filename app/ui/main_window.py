"""Główne okno ElectroSchem — integracja edytora, dokumentów i usług.

Warstwa okna nie rysuje symboli ani nie interpretuje odpowiedzi AI. Deleguje to
modułom, dzięki czemu testujemy zapis, geometrię i sieć niezależnie od GUI.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from datetime import datetime
import subprocess

from PySide6.QtCore import QSize, Qt, QTimer, QObject, QRunnable, QThreadPool, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QKeySequence, QCursor
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QDockWidget, QFileDialog, QColorDialog, QInputDialog, QLabel, QMainWindow,
    QMenu, QMessageBox, QProgressDialog, QStatusBar, QTabWidget, QToolBar, QToolButton,
    QVBoxLayout, QFormLayout, QLineEdit, QPushButton, QWidget, QComboBox,
)

from app.canvas.schematic_view import SchematicView
from app.core.models import Project, Sheet
from app.core.project_file import load_project, save_project
from app.core.settings import AppSettings, default_editor, load_settings, save_settings, file_dialog_directory, code_dialog_directory, default_code_directory
from app.libraries.built_in import BUILT_IN_ITEMS, AVAILABLE_ITEMS, get_definition, item_name
from app.libraries.menu_groups import subgroup, library_sort_key, secondary_locations
from app.core.features import AI_AVAILABLE
from app.ui.i18n import install_ui_language
from app.ui.component_dialogs import CustomComponentDialog, ProjectDialog
from app.ui.component_info_dialog import ComponentInfoDialog
from app.ui.properties_dialog import ComponentPropertiesDialog
from app.ui.settings_dialog import SettingsDialog
from app.canvas.page import drawing_regions, title_block_rect
from app.ui.sheet_tabs import SheetTabBar
from app.ui.shortcuts import EditorShortcuts

APP_VERSION = "1.4.0"
ICON_DIR = Path(__file__).resolve().parents[2] / "icons"


class _CloudOperationSignals(QObject):
    finished = Signal(object, object)


class _CloudOperationWorker(QRunnable):
    def __init__(self, settings, operation):
        super().__init__()
        self.settings = deepcopy(settings)
        self.operation = operation
        self.signals = _CloudOperationSignals()

    def run(self):
        try:
            result = self.operation(self.settings)
            self.signals.finished.emit((result, self.settings.cloud_tokens), None)
        except Exception as error:
            # Refresh-token rotation must survive even if the later API call
            # fails (for example, because a cloud file was moved meanwhile).
            self.signals.finished.emit((None, self.settings.cloud_tokens), error)


class _GitHubOperationSignals(QObject):
    finished = Signal(str, object, object)


class _GitHubOperationWorker(QRunnable):
    def __init__(self, settings, kind, file_path=None, project_name=""):
        super().__init__()
        self.settings = deepcopy(settings)
        self.kind = kind
        self.file_path = file_path
        self.project_name = project_name
        self.signals = _GitHubOperationSignals()

    def run(self):
        try:
            from app.services.github_sync import GitHubSync
            client = GitHubSync(
                self.settings.default_directory,
                self.settings.github_repository_url,
                self.settings.github_branch,
                noninteractive=self.kind == "startup_pull",
            )
            if self.kind in {"pull", "startup_pull"}:
                result = client.pull()
            elif self.kind == "push":
                result = client.push()
            else:
                result = client.commit_file(self.file_path, self.project_name)
            self.signals.finished.emit(self.kind, result, None)
        except Exception as error:
            self.signals.finished.emit(self.kind, None, error)

# Kolejność odpowiada szkicowi oraz literom E/S/I/C/M w skrótach.
LIBRARY_GROUPS = (
    ("Electronic components", "Elementy elektroniczne", "electronic_components.png",
     {"Elementy pasywne", "Półprzewodniki", "Zasilanie i połączenia"}),
    ("Sensors, modules and drives", "Czujniki, moduły i napędy", "sensor.png", {"Czujniki", "Moduły i interfejsy", "Napędy", "Dźwięk"}),
    ("Integrated circuits", "Układy scalone", "ic_library.png", {"Układy i sterowniki"}),
    ("Custom components", "Customowe elementy", "custom_components.png", {"Własne"}),
    ("Microcontrollers and computers", "Mikrokontrolery i mikrokomputery", "microcontrollers.png", {"Mikrokontrolery i SBC"}),
    ("Favorites", "Ulubione", "favorites.png", set()),
    ("Cables and connectors", "Kable i złącza", "cables.png", {"Kable"}),
    ("Measurement tools", "Narzędzia pomiarowe", "measurement_tool.png", {"Narzędzia pomiarowe"}),
    ("Interactive components", "Elementy interaktywne", "interactive_components.png", {"Elementy interaktywne"}),
)


class MainWindow(QMainWindow):
    """Jeden dokument, wiele arkuszy, wspólna historia i ustawienia użytkownika."""

    def __init__(self, settings: AppSettings | None = None, start_setup: bool = True):
        super().__init__()
        # Keep the pixel-art application logo in its original colours in both themes.
        from app.ui.theme import application_icon
        self.setWindowIcon(application_icon(ICON_DIR))
        self.settings = settings if settings is not None else load_settings()
        self.project = self._empty_project()
        self.current_file: Path | None = None
        self.current_cloud_file = None
        self.current_cloud_provider = ""
        self._cloud_busy = False
        self._github_busy = False
        self._github_queue = []
        self._github_worker = None
        self._github_progress = None
        self._history = []
        self._redo_history = []
        self._saved_state = deepcopy(self.project.to_dict())
        self._active_tool = "select"
        self._selected_component = None
        self._action_labels = {}
        self.ai_panel = None
        self.ai_dock = None
        self.resize(1440, 900)
        self.setStatusBar(QStatusBar(self))
        self._create_actions()
        from app.ui.effects import install_click_feedback
        install_click_feedback()
        self._create_component_library()
        self._create_workspace()
        self._create_tools()
        self._create_menu()
        self._reset_history()
        self.shortcuts = EditorShortcuts(self)
        self._translate_ui()
        from app.ui.theme import apply_theme
        apply_theme(self,self.settings)
        if self.settings.cloud_provider == "github" and self.settings.github_repository_url:
            QTimer.singleShot(0, lambda: self._queue_github_operation("startup_pull"))
        # Timer pokazuje konfigurację dopiero po uruchomieniu pętli zdarzeń.
        # Testy i narzędzia mogą jawnie wyłączyć ten jednorazowy dialog.
        if start_setup and not self.settings.setup_complete:
            QTimer.singleShot(0, lambda: self.show_settings(first_run=True))

    def t(self, en: str, pl: str) -> str:
        return pl if self.settings.language == "pl" else en

    def _empty_project(self):
        project = Project(name=self.t("New project", "Nowy projekt"), sheets=[
            Sheet(name=self.t("Sheet 1", "Arkusz 1"), paper_size=self.settings.paper_size,
                  orientation=self.settings.orientation, standard=self.settings.standard)])
        if self.settings.default_author:
            project.metadata["author"] = self.settings.default_author
        return project

    def _icon(self,filename):
        from app.ui.theme import themed_icon
        path=ICON_DIR/filename
        if filename=='cables.png' and not path.is_file():
            from app.ui.cable_icon import cable_icon
            return cable_icon(self.settings.theme=='dark')
        return themed_icon(path,self.settings.theme=="dark")

    def _action(self, en, pl, callback=None, shortcut=None, icon=None, checkable=False):
        action = QAction(self.t(en, pl), self)
        self._action_labels[action] = (en, pl)
        if callback:
            action.triggered.connect(callback)
        if shortcut:
            action.setShortcut(shortcut)
        if icon:
            action.setIcon(self._icon(icon))
            action.setProperty("iconFile",icon)
        action.setCheckable(checkable)
        return action

    def _create_actions(self):
        self.new_action = self._action("New project…", "Nowy projekt…", self.new_project, QKeySequence.StandardKey.New)
        self.open_action = self._action("Open project…", "Otwórz projekt…", self.open_project, QKeySequence.StandardKey.Open)
        self.save_action = self._action("Save", "Zapisz", self.save_project, QKeySequence.StandardKey.Save)
        self.save_as_action = self._action("Save as…", "Zapisz jako…", self.save_project_as, QKeySequence.StandardKey.SaveAs)
        self.quick_open_action = self._action("Open default project", "Otwórz domyślny projekt", self.open_default_location, "Alt+O")
        self.quick_save_action = self._action("Save default project", "Zapisz domyślny projekt", self.save_default_location, "Alt+S")
        self.github_pull_action = self._action("Pull from GitHub", "Pobierz z GitHuba", lambda: self._queue_github_operation("pull"))
        self.github_push_action = self._action("Push to GitHub", "Wyślij do GitHuba", lambda: self._queue_github_operation("push"))
        self.save_asset_action = self._action("Save as Asset…", "Zapisz jako Asset…", self.save_as_asset)
        self.export_pdf_action = self._action("PDF", "PDF", self.export_pdf)
        self.export_png_action = self._action("PNG", "PNG", lambda: self._export("png"))
        self.export_svg_action = self._action("SVG", "SVG", lambda: self._export("svg"))
        self.help_action = self._action("Usage Instructions", "Instrukcja Obsługi", self.show_help)
        self.component_help_action = self._action("Component help (H)", "Pomoc elementu (H)", self.show_component_info, icon="help.png")
        self.standard_actions = {}
        for standard in ("EN", "PN", "ISO", "IEEE/ANSI"):
            action = self._action(standard, standard, lambda checked=False, value=standard: self.set_sheet_standard(value), checkable=True)
            self.standard_actions[standard] = action
        self.add_sheet_action = self._action("Add sheet (Shift+A, S)", "Dodaj arkusz (Shift+A, S)", self.add_sheet, icon="add_sheet.png")
        self.ai_action = self._action("AI assistant (Shift+A, I)", "Asystent AI (Shift+A, I)", self.show_ai, icon="ai_features.png")
        self.datasheet_action = self._action("Analyse datasheet PDF…", "Analizuj dokumentację PDF…", self.show_datasheet_ai)
        self.clipboard_actions = [self._action(en, pl, lambda checked=False, op=op: self.selection_command(op))
                                  for en, pl, op in (
                                      ("Duplicate (Ctrl+D)", "Duplikuj (Ctrl+D)", "duplicate"),
                                      ("Cut (Ctrl+X)", "Wytnij (Ctrl+X)", "cut"),
                                      ("Copy (Ctrl+C)", "Kopiuj (Ctrl+C)", "copy"),
                                      ("Paste (Ctrl+V)", "Wklej (Ctrl+V)", "paste"))]
        self.fit_page_action = self._action("Fit sheet", "Dopasuj arkusz", self.fit_current_page, icon="reset_zoom.png")
        self.select_action = self._action("Select (S)", "Zaznaczanie (S)", lambda: self.set_active_tool("select"), icon="cursor.png", checkable=True)
        self.delete_action = self._action("Delete tool", "Narzędzie usuwania", lambda: self.set_active_tool("delete"), icon="delete.png", checkable=True)
        self.paint_wire_action = self._action("Paint connected wires", "Maluj połączone przewody", lambda: self.set_active_tool("wire_color"), icon="paint_wire.png", checkable=True)
        self.wire_action = self._action("Draw connections (D)", "Rysuj połączenia (D)", lambda: self.set_active_tool("wire"), icon="pencil.png", checkable=True)
        self.comment_action = self._action("Add comment (C)", "Dodaj komentarz (C)", lambda: self.set_active_tool("comment"), icon="type.png", checkable=True)
        self.tool_group = QActionGroup(self)
        self.tool_group.setExclusive(True)
        for action in (self.select_action, self.delete_action, self.paint_wire_action, self.wire_action, self.comment_action):
            self.tool_group.addAction(action)
        self.select_action.setChecked(True)
        self.undo_action = self._action("Undo", "Cofnij", self.undo, QKeySequence.StandardKey.Undo, "undo.png")
        self.redo_action = self._action("Redo", "Ponów", self.redo, icon="redo.png")
        self.redo_action.setShortcuts([QKeySequence("Ctrl+Y"), QKeySequence("Ctrl+Shift+Z")])
        self.properties_action = self._action("Component properties…", "Właściwości elementu…", self.edit_selected_properties, icon="properties.png")
        self.properties_action.setEnabled(False)
        self.custom_action = self._action("Create custom component…", "Utwórz customowy element…", self.create_custom_component, icon="custom_components.png")
        self.settings_action = self._action("Settings…", "Ustawienia…", lambda: self.show_settings())
        self.code_action = self._action("Edit code…", "Edytuj kod…", self.open_code, icon="edit_code.png")
        self.simulation_action = self._action("Simulation sandbox", "Sandbox symulacji", self.show_simulation, "F5", icon="run_simulation.png")
        self.add_component_action = self._action("Add component", "Dodaj element", self.open_add_menu, icon="add_component.png")
        self.search_action = self._action("Find component…", "Wyszukaj element…", self.search_components, icon="search.png")
        self.document_action = self._action("Drawing information…", "Dane tabliczki rysunkowej…", self.edit_document_info)
        self.exit_action = self._action("Exit", "Zakończ", self.close)
        self.library_actions = []
        for index, (en, pl, icon, _) in enumerate(LIBRARY_GROUPS):
            letter = "ESICMFPKT"[index]
            self.library_actions.append(self._action(
                en + f" (Ctrl+A, {letter})", pl + f" (Ctrl+A, {letter})",
                lambda checked=False, i=index: self.open_library(i), icon=icon))
            if index==5: self.library_actions[-1].setToolTip("F: " + self.t("add/remove selected favorite; Shift+F: reuse", "dodaj/usuń zaznaczony element z Ulubionych; Shift+F: użyj ponownie"))
            if index==5 and self.library_actions[-1].icon().isNull():
                from PySide6.QtWidgets import QStyle
                self.library_actions[-1].setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogYesButton))
                self.library_actions[-1].setProperty("iconFile",None)

    def _create_menu(self):
        self.menuBar().clear()
        file_menu = self.menuBar().addMenu(self.t("File", "Plik"))
        file_menu.addActions([self.new_action, self.open_action, self.save_action, self.save_as_action])
        file_menu.addSeparator()
        file_menu.addActions([self.quick_open_action, self.quick_save_action, self.save_asset_action])
        self.github_menu = file_menu.addMenu(self.t("GitHub", "GitHub"))
        self.github_menu.addActions([self.github_pull_action, self.github_push_action])
        file_menu.addSeparator()
        export_menu = file_menu.addMenu(self.t("Export…", "Eksportuj…"))
        export_menu.addActions([self.export_pdf_action, self.export_png_action, self.export_svg_action])
        file_menu.addSeparator()
        file_menu.addAction(self.document_action)
        file_menu.addAction(self.exit_action)
        self.github_menu.menuAction().setVisible(self.settings.cloud_provider == "github")
        edit_menu = self.menuBar().addMenu(self.t("Edit", "Edycja"))
        edit_menu.addActions(self.clipboard_actions)
        tools_menu = self.menuBar().addMenu(self.t("Tools", "Narzędzia"))
        library = tools_menu.addMenu(self.t("Add component", "Dodaj element"))
        library.setIcon(self._icon("add_component.png"))
        library.addActions(self.library_actions)
        tools_menu.addActions([self.custom_action, self.add_sheet_action, self.comment_action])
        tools_menu.addSeparator()
        tools_menu.addActions([self.select_action, self.delete_action, self.paint_wire_action, self.wire_action, self.properties_action])
        tools_menu.addSeparator()
        tools_menu.addActions([self.undo_action, self.redo_action])
        tools_menu.addSeparator()
        tools_menu.addActions([self.search_action, self.fit_page_action])
        tools_menu.addSeparator()
        tools_menu.addActions([self.code_action, self.simulation_action])
        tools_menu.addAction(self.ai_action)
        options_menu = self.menuBar().addMenu(self.t("Options", "Opcje"))
        options_menu.addActions([self.settings_action, self.help_action])
        standards = options_menu.addMenu(self.t("Sheet standard", "Norma arkusza"))
        standards.addActions(list(self.standard_actions.values()))

    def _create_component_library(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 8, 6, 8)
        layout.setSpacing(8)
        self.library_buttons = []
        for action in self.library_actions:
            button = QToolButton()
            button.setDefaultAction(action)
            button.setIconSize(QSize(36, 36))
            button.setFixedSize(52, 52)
            layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignHCenter)
            self.library_buttons.append(button)
        layout.addStretch()
        self.library_dock = QDockWidget(self)
        self.library_dock.setTitleBarWidget(QWidget())
        self.library_dock.setWidget(panel)
        self.library_dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.library_dock.setFixedWidth(68)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.library_dock)

    def _create_workspace(self):
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.South)
        self.sheet_tab_bar = SheetTabBar()
        self.sheet_tab_bar.add_requested.connect(self.add_sheet)
        self.sheet_tab_bar.rename_requested.connect(self.rename_sheet)
        self.tabs.setTabBar(self.sheet_tab_bar)
        self.tabs.currentChanged.connect(self._load_current_sheet)
        self.setCentralWidget(self.tabs)
        self._rebuild_tabs()

    def _create_tools(self):
        self.toolbar = QToolBar(self)
        self.toolbar.setMovable(False)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.toolbar.setIconSize(QSize(34, 34))
        self.tools_heading = QLabel()
        self.tools_heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tools_heading.setWordWrap(True)
        self.tools_heading.setFixedWidth(102)
        self.tools_heading.setStyleSheet("font-size: 10px; font-weight: bold; padding: 4px 0;")
        self.toolbar.addWidget(self.tools_heading)
        self.toolbar.addActions([self.select_action, self.delete_action, self.paint_wire_action, self.wire_action, self.comment_action])
        self.toolbar.addSeparator()
        self.toolbar.addActions([self.undo_action, self.redo_action])
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.fit_page_action)
        self.toolbar.addAction(self.search_action)
        self.toolbar.addAction(self.component_help_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.simulation_action)
        self.toolbar.addAction(self.ai_action)
        self.addToolBar(Qt.ToolBarArea.RightToolBarArea, self.toolbar)

    def _translate_ui(self):
        install_ui_language(self.settings.language)
        for action, (en, pl) in self._action_labels.items():
            action.setText(self.t(en, pl))
            action.setToolTip(self.t(en, pl))
            if action.property("iconFile"): action.setIcon(self._icon(action.property("iconFile")))
        self.ai_action.setVisible(AI_AVAILABLE and self.settings.ai_provider != "none")
        self.datasheet_action.setVisible(AI_AVAILABLE)
        self.ai_action.setEnabled(AI_AVAILABLE and self.settings.ai_provider != "none")
        if self.settings.ai_provider == "none" and self.ai_panel is not None:
            self.ai_panel.cancel()
            self.ai_dock.hide()
        self.datasheet_action.setEnabled(AI_AVAILABLE and self.settings.ai_provider != "none" and bool(self.settings.api_key))
        if not (self.settings.openai_api_key if self.settings.ai_provider == "openai" else self.settings.api_key):
            self.ai_action.setToolTip(self.t("Configure the selected provider's API key in Settings to enable AI.",
                                             "Ustaw klucz API wybranego dostawcy w ustawieniach, aby włączyć AI."))
        self.tools_heading.setText(self.t("BASIC TOOLS", "PODSTAWOWE NARZĘDZIA"))
        self.toolbar.setWindowTitle(self.t("Basic tools", "Podstawowe narzędzia"))
        if self.project.sheets:
            current_standard = getattr(self.project.sheets[self.tabs.currentIndex()], "standard", self.settings.standard)
            for value, action in self.standard_actions.items():
                action.setChecked(value == current_standard)
        self._create_menu()
        self._refresh_title()
        self.statusBar().showMessage(self.t("Ready — double-click a component to edit its properties.",
                                            "Gotowe — dwuklik elementu otwiera jego właściwości."))

    def _make_view(self, sheet):
        view = SchematicView(project=self.project, settings=self.settings)
        view.on_change = self.record_history
        view.on_routes_updated = self.refresh_last_route_snapshot
        view.on_selection = self._selection_changed
        view.on_edit_properties = self.show_component_properties
        view.load_sheet(sheet)
        view.set_tool(self._active_tool, getattr(self.settings, "wire_paint_color", "#167d3d"))
        return view

    def _rebuild_tabs(self, selected=None):
        # QTabWidget.clear() nie usuwa obiektów widoków. Jawne deleteLater
        # zapobiega wyciekom scen przy wielokrotnym undo/redo.
        old_index = self.tabs.currentIndex() if selected is None else selected
        self.tabs.blockSignals(True)
        while self.tabs.count():
            widget = self.tabs.widget(0)
            self.tabs.removeTab(0)
            widget.deleteLater()
        for sheet in self.project.sheets:
            self.tabs.addTab(self._make_view(sheet), sheet.name)
        self.tabs.setCurrentIndex(max(0, min(old_index, self.tabs.count()-1)))
        self.tabs.blockSignals(False)
        self._selection_changed(None)

    def _current_view(self):
        return self.tabs.currentWidget()

    def _load_current_sheet(self, index):
        if index >= 0:
            self._current_view().set_tool(self._active_tool)
            self._selection_changed(None)
            self._current_view().setFocus()

    def open_library(self, index, global_pos=None):
        if not 0 <= index < len(LIBRARY_GROUPS):
            return
        menu_pos = global_pos or QCursor.pos()
        menu = QMenu(self)
        self._populate_library_menu(menu, index, menu_pos)
        try:
            menu.exec(menu_pos)
        finally:
            menu.deleteLater()

    def open_add_menu(self):
        """Ctrl+A, A: całe dodawanie w jednym menu przy kursorze."""
        menu_pos = QCursor.pos()
        menu = QMenu(self)
        for index, (en, pl, _, _) in enumerate(LIBRARY_GROUPS):
            branch = menu.addMenu(self.t(en, pl))
            self._populate_library_menu(branch, index, menu_pos)
        menu.addSeparator()
        menu.addAction(self.t("Add sheet", "Dodaj arkusz"), self.add_sheet)
        menu.addAction(self.t("Add comment", "Dodaj komentarz"),
                       lambda: self.set_active_tool("comment"))
        try:
            menu.exec(menu_pos)
        finally:
            menu.deleteLater()

    def _populate_library_menu(self, menu, index, menu_pos):
        """Jedno źródło struktury dla ikon kategorii i wspólnego menu."""
        categories = LIBRARY_GROUPS[index][3]
        from app.simulation.jumper import CABLE_IDS
        connector_ids={item.id for item in AVAILABLE_ITEMS if item.id in CABLE_IDS or item.symbol=='goldpin' or 'Goldpin' in item.name or item.name.startswith(('Port USB','Port Lightning','Terminale Śrubowe','Gniazdo'))}
        entries = [item for item in AVAILABLE_ITEMS if item.category in categories and item.id not in connector_ids]
        if index==6: entries=[item for item in AVAILABLE_ITEMS if item.id in connector_ids]
        secondary={item.id:group for item in AVAILABLE_ITEMS for category,group in secondary_locations(item)
                   if category in categories}
        entries += [item for item in AVAILABLE_ITEMS if item.id in secondary and item not in entries]
        if index==5:
            entries=[get_definition(identity,self.project.custom_components) for identity in self.settings.favorite_components]
            entries=[item for item in entries if item is not None]
        if index == 3:
            entries = list(self.project.custom_components)
            try:
                from app.core.assets import load_assets
                seen={d["id"] for d in entries}; entries += [d for d in load_assets() if d["id"] not in seen]
            except (OSError,ValueError) as error: self.statusBar().showMessage(str(error),8000)
            entries = [get_definition(entry["id"], entries) for entry in entries]
            entries = [item for item in entries if item is not None]
        if not entries:
            menu.addAction(self.t("[NONE]", "[BRAK]")).setEnabled(False)
        submenus = {}
        if index==6:
            from app.ui.library_menu_style import LibrarySubMenu
            for en,pl in (("USB ports","Porty USB"),("Gold pins","Goldpiny"),("Cables","Kable"),("Terminals","Terminale")):
                submenu=LibrarySubMenu(self.t(en,pl),menu)
                submenus[(en,pl)]=submenu
                menu.addMenu(submenu)
        if index in {3,5}:
            menu.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            from app.ui.library_menu_style import CustomMenuInput
            menu._custom_input=CustomMenuInput(menu); menu.installEventFilter(menu._custom_input)
            def custom_context(pos):
                action=menu.actionAt(pos)
                if not action or not action.data(): return
                identity=action.data(); popup=QMenu(menu)
                if index==5:
                    def remove():
                        if self.remove_favorite(identity): menu.removeAction(action)
                    popup.addAction(self.t('Remove from favorites','Usuń z Ulubionych'),remove)
                else:
                    popup.addAction(self.t("Edit definition…", "Edytuj definicję…"),lambda:self.edit_custom_component(identity))
                    popup.addAction(self.t("Delete from library…", "Usuń z biblioteki…"),lambda:self.delete_custom_component(identity))
                popup.exec(menu.mapToGlobal(pos)); popup.deleteLater()
            menu.customContextMenuRequested.connect(custom_context)
        placements=[]
        for item in sorted(entries,key=library_sort_key):
            primary=item.category in categories or index in {3,5,6,7}
            if primary: placements.append((item,subgroup(item),False))
            if item.id in secondary: placements.append((item,secondary[item.id],True))
        for item,group,is_secondary in placements:
            if index==6:
                if item.id in CABLE_IDS:
                    group=('Cables','Kable')
                elif item.symbol=='goldpin' or 'Goldpin' in item.name:
                    group=('Gold pins','Goldpiny')
                elif item.name.startswith(('Port USB','Port Lightning')):
                    group=('USB ports','Porty USB')
                elif item.name.startswith("Terminale Śrubowe"):
                    group=('Terminals','Terminale')
                else:
                    group=None
                target=submenus[group] if group in submenus else menu
            elif index in {3,5,7,8}:
                target = menu
            else:
                if group not in submenus:
                    from app.ui.library_menu_style import LibrarySubMenu
                    submenus[group]=LibrarySubMenu(self.t(*group),menu)
                    menu.addMenu(submenus[group])
                target = submenus[group]
            action = target.addAction(item_name(item, self.settings.language))
            action.setData(item.id)
            action.setProperty("secondaryEntry",is_secondary)
            from app.libraries.catalog_text import catalog_text
            action.setToolTip(catalog_text(item.variant,self.settings.language))
            # Pozycja jest przechwycona przed otwarciem menu. Przejście przez
            # podkategorie nie przesuwa miejsca wstawienia elementu.
            if index==5:
                action.triggered.connect(lambda checked=False, identity=item.id,pos=menu_pos:self.add_favorite(identity,pos))
            else:
                action.triggered.connect(lambda checked=False, identity=item.id, pos=menu_pos: self.add_component_from_id(identity, global_pos=pos))
        if index == 3:
            menu.addSeparator()
            menu.addAction(self.custom_action)

    def add_component_from_id(self, library_id, name=None, global_pos=None):
        try:
            from app.core.assets import load_assets, with_asset_dependencies
            raw=next((d for d in self.project.custom_components if d["id"]==library_id),None)
            if library_id.startswith("asset_") and raw is None:
                raw=next((d for d in load_assets() if d["id"]==library_id),None)
                if raw: self.project.custom_components=with_asset_dependencies(self.project.custom_components+[raw])
            if raw and "asset" in raw and not raw["asset"]["boxed"]:
                return self.place_asset(raw,global_pos)
            component = self._current_view().add_component(library_id, global_pos=global_pos)
            default_name = self.settings.default_display_names.get(library_id, "").strip()
            if default_name:
                component.display_name = default_name
                self._current_view().refresh_component(component.id)
                self.record_history()
            self.select_action.setChecked(True)
            self.set_active_tool("select")
            self.statusBar().showMessage(self.t("Added: ", "Dodano: ") + component.reference, 2500)
            self._current_view().setFocus()
            return component
        except ValueError as error:
            self._error(str(error))

    def toggle_favorite(self):
        c=self._selected_component
        if c is None: return
        favorites=deepcopy(self.settings.favorite_components)
        if c.library_id in favorites:
            del favorites[c.library_id]
            message=self.t("Removed from favorites", "Usunięto z Ulubionych")
        else:
            props={k:v for k,v in c.properties.items() if k not in {"asset_group","usb_a_target","usb_b_target"} and not any(word in k for word in ("source","firmware","code_folder","usb_a_x","usb_a_y","usb_b_x","usb_b_y"))}
            favorites[c.library_id]={"value":c.value,"unit":c.unit,"display_name":c.display_name,"show_name":c.show_name,"show_value":c.show_value,"properties":props}
            message=self.t("Added to favorites", "Dodano do Ulubionych")
        previous=self.settings.favorite_components; self.settings.favorite_components=favorites
        try: save_settings(self.settings)
        except (OSError,ValueError) as error:
            self.settings.favorite_components=previous; self._error(str(error)); return
        self.statusBar().showMessage(message,3000)

    def remove_favorite(self,identity):
        previous=deepcopy(self.settings.favorite_components)
        self.settings.favorite_components.pop(identity,None)
        try: save_settings(self.settings)
        except (OSError,ValueError) as error:
            self.settings.favorite_components=previous; self._error(str(error)); return False
        self.statusBar().showMessage(self.t('Removed from favorites','Usunięto z Ulubionych'),3000)
        return True

    def add_favorite(self,identity,pos=None):
        values=self.settings.favorite_components.get(identity,{})
        c=self.add_component_from_id(identity,global_pos=pos)
        if c is None: return
        for key in ("value","unit","display_name","show_name","show_value","properties"):
            if key in values and isinstance(values[key],type(getattr(c,key))): setattr(c,key,deepcopy(values[key]))
        self._current_view().refresh_component(c.id); self.record_history()
        return c

    def add_sheet(self):
        current = self.project.sheets[self.tabs.currentIndex()]
        sheet = Sheet(name=self.t("Sheet ", "Arkusz ") + str(len(self.project.sheets)+1),
                      paper_size=current.paper_size, orientation=current.orientation, standard=current.standard)
        self.project.sheets.append(sheet)
        self.tabs.addTab(self._make_view(sheet), sheet.name)
        self.tabs.setCurrentIndex(self.tabs.count()-1)
        self.sheet_tab_bar.updateGeometry()
        self.sheet_tab_bar.update()
        # Liczba arkuszy w tabliczkach starszych stron też wymaga odświeżenia.
        for index in range(self.tabs.count()):
            self.tabs.widget(index).viewport().update()
        self.record_history()

    def rename_sheet(self, index):
        if not 0 <= index < len(self.project.sheets):
            return
        sheet = self.project.sheets[index]
        dialog = QDialog(self)
        dialog.setWindowTitle(self.t("Sheet", "Arkusz"))
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        name_edit = QLineEdit(sheet.name)
        form.addRow(self.t("Name:", "Nazwa:"), name_edit)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        delete_button = QPushButton(self.t("Delete sheet", "Usuń arkusz"))
        delete_button.setEnabled(len(self.project.sheets) > 1)
        buttons.addButton(delete_button, QDialogButtonBox.ButtonRole.DestructiveRole)
        layout.addWidget(buttons)
        deleted = {"value": False}
        def delete_sheet():
            if len(self.project.sheets) <= 1:
                QMessageBox.information(dialog, dialog.windowTitle(), self.t("The last sheet cannot be deleted.", "Nie można usunąć ostatniego arkusza."))
                return
            if QMessageBox.question(dialog, dialog.windowTitle(), self.t("Delete this sheet and all its contents?", "Usunąć arkusz wraz z całą zawartością?")) == QMessageBox.StandardButton.Yes:
                deleted["value"] = True
                dialog.done(2)
        delete_button.clicked.connect(delete_sheet)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        result = dialog.exec()
        if deleted["value"]:
            self.project.sheets.pop(index)
            self._rebuild_tabs(selected=min(index, len(self.project.sheets)-1))
            self.record_history()
        elif result == QDialog.DialogCode.Accepted:
            name = name_edit.text().strip()[:200]
            if name and name != sheet.name:
                sheet.name = name
                self.tabs.setTabText(index, sheet.name)
                self.tabs.widget(index).viewport().update()
                self.record_history()

    def new_project(self):
        if not self._confirm_discard():
            return
        dialog = ProjectDialog(self.settings, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if self.ai_panel:
            self.ai_panel.new_chat()
        if getattr(self, "command_panel", None): self.command_panel.reset()
        self.project = Project(name=dialog.name.text().strip() or self.t("New project", "Nowy projekt"),
                               sheets=[Sheet(name=self.t("Sheet 1", "Arkusz 1"),
                                             paper_size=dialog.paper.currentText(),
                                             orientation=dialog.orientation.currentData(), standard=self.settings.standard)])
        self.current_file = None
        self.current_cloud_file = None
        self.current_cloud_provider = ""
        if self.settings.default_author:
            self.project.metadata["author"] = self.settings.default_author
        self._rebuild_tabs(selected=0)
        self._reset_history()

    def open_project(self):
        if not self._confirm_discard():
            return
        filename, _ = QFileDialog.getOpenFileName(self, self.t("Open project", "Otwórz projekt"),
                                                  file_dialog_directory(self.settings), "ElectroSchem (*.els)")
        if not filename:
            return
        try:
            candidate = load_project(filename)
        except (OSError, ValueError, TypeError, OverflowError) as error:
            self._error(str(error))
            return
        self.project = candidate
        if self.ai_panel:
            self.ai_panel.new_chat()
        if getattr(self, "command_panel", None): self.command_panel.reset()
        self.current_file = Path(filename)
        self.current_cloud_file = None
        self.current_cloud_provider = ""
        self._rebuild_tabs(selected=0)
        self._reset_history()
        notice = self.project.metadata.get("migration_notice")
        if notice:
            QMessageBox.warning(self, self.t("Check migrated connections", "Sprawdź migrowane połączenia"), notice)

    def open_default_location(self):
        if self.settings.cloud_default_location == "cloud":
            if self.settings.cloud_provider == "github":
                return self.open_project()
            return self.open_cloud_project()
        return self.open_project()

    def save_default_location(self):
        if self.settings.cloud_default_location == "cloud":
            if self.settings.cloud_provider == "github":
                return self.save_github_project()
            return self.save_cloud_project()
        return self.save_project()

    def save_github_project(self):
        """Save into the configured local clone; the regular save hook commits it."""
        if self.current_file is not None:
            try:
                current = self.current_file.resolve()
                root = Path(self.settings.default_directory).expanduser().resolve()
                if current.is_relative_to(root):
                    return self._write_project(current)
            except (OSError, ValueError):
                pass
        # Save dialog starts at the configured clone folder. If the user picks
        # somewhere else the file still saves safely, but Git reports it was
        # outside the repository and does not stage it.
        return self.save_project_as()

    def open_cloud_project(self):
        if self._cloud_busy or not self._confirm_discard():
            return
        self._start_cloud_operation(lambda settings: __import__("app.services.cloud_storage", fromlist=["CloudStorageClient"]).CloudStorageClient(settings).list_projects(),
                                    self._choose_cloud_project,
                                    self.t("Loading cloud projects…", "Wczytywanie projektów z chmury…"))

    def save_cloud_project(self):
        if self._cloud_busy:
            return
        self._sync_positions()
        from app.core.file_names import project_filename
        existing = (self.current_cloud_file if self.current_cloud_provider == self.settings.cloud_provider else None)
        default_name = existing.name if existing else project_filename(self.project.name, "els")
        if existing:
            name = existing.name
        else:
            name, accepted = QInputDialog.getText(self, self.t("Save cloud project", "Zapisz projekt w chmurze"),
                                                  self.t("Project file name", "Nazwa pliku projektu"), text=default_name)
            if not accepted or not name.strip():
                return
        snapshot = deepcopy(self.project.to_dict())
        from app.core.models import Project
        project = Project.from_dict(snapshot)
        normalized_name = name.strip().replace("\\", "/").rsplit("/", 1)[-1]
        if not normalized_name.lower().endswith(".els"):
            normalized_name += ".els"
        file_id = existing.file_id if existing and normalized_name.casefold() == existing.name.casefold() else ""
        provider = self.settings.cloud_provider
        def upload(settings):
            from app.core.project_file import project_bytes
            from app.services.cloud_storage import CloudStorageClient
            return CloudStorageClient(settings).upload(name, project_bytes(project), file_id)
        def saved(entry):
            self.current_file = None
            self.current_cloud_file = entry
            self.current_cloud_provider = provider
            self._saved_state = snapshot
            self._refresh_title()
            self.statusBar().showMessage(self.t("Cloud project saved.", "Projekt zapisany w chmurze."), 3000)
        self._start_cloud_operation(upload, saved, self.t("Saving cloud project…", "Zapisywanie projektu w chmurze…"))

    def _choose_cloud_project(self, entries):
        if not entries:
            QMessageBox.information(self, self.t("Cloud projects", "Projekty w chmurze"),
                                    self.t("No ElectroSchem projects were found in this folder.", "W tym folderze nie znaleziono projektów ElectroSchem."))
            return
        labels = [f"{index + 1}. {entry.name}" + (f" — {entry.modified}" if entry.modified else "")
                  for index, entry in enumerate(entries)]
        selected, accepted = QInputDialog.getItem(self, self.t("Open cloud project", "Otwórz projekt z chmury"),
                                                  self.t("Choose a project", "Wybierz projekt"), labels, 0, False)
        if not accepted:
            return
        entry = entries[labels.index(selected)]
        provider = self.settings.cloud_provider
        def download(settings):
            from app.core.project_file import load_project_bytes
            from app.services.cloud_storage import CloudStorageClient
            client = CloudStorageClient(settings)
            payload = client.download(entry)
            return (load_project_bytes(payload), entry)
        self._start_cloud_operation(download, lambda result: self._finish_open_cloud(result[0], result[1], provider),
                                    self.t("Opening cloud project…", "Otwieranie projektu z chmury…"))

    def _finish_open_cloud(self, project, entry, provider):
        self.project = project
        if self.ai_panel:
            self.ai_panel.new_chat()
        if getattr(self, "command_panel", None):
            self.command_panel.reset()
        self.current_file = None
        self.current_cloud_file = entry
        self.current_cloud_provider = provider
        self._rebuild_tabs(selected=0)
        self._reset_history()
        notice = self.project.metadata.get("migration_notice")
        if notice:
            QMessageBox.warning(self, self.t("Check migrated connections", "Sprawdź migrowane połączenia"), notice)

    def _start_cloud_operation(self, operation, on_success, message):
        if self._cloud_busy:
            return
        self._cloud_busy = True
        progress = QProgressDialog(message, None, 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        self._cloud_progress = progress
        worker = _CloudOperationWorker(self.settings, operation)
        self._cloud_worker = worker
        worker.signals.finished.connect(lambda result, error: self._finish_cloud_operation(result, error, on_success))
        QThreadPool.globalInstance().start(worker)

    def _queue_github_operation(self, kind, file_path=None, project_name=""):
        if not self.settings.github_repository_url:
            QMessageBox.information(
                self, "GitHub",
                self.t("Set a GitHub repository URL in Settings → Cloud first.",
                       "Najpierw ustaw adres repozytorium GitHub w Ustawienia → Chmura."),
            )
            return
        self._github_queue.append((kind, file_path, project_name))
        self._start_next_github_operation()

    def _start_next_github_operation(self):
        if self._github_busy or not self._github_queue:
            return
        kind, file_path, project_name = self._github_queue.pop(0)
        self._github_busy = True
        labels = {
            "startup_pull": self.t("Checking GitHub for updates…", "Sprawdzanie aktualizacji na GitHubie…"),
            "pull": self.t("Pulling GitHub updates…", "Pobieranie zmian z GitHuba…"),
            "push": self.t("Pushing changes to GitHub…", "Wysyłanie zmian do GitHuba…"),
            "commit": self.t("Committing saved project…", "Commitowanie zapisanego projektu…"),
        }
        self.statusBar().showMessage(labels.get(kind, "GitHub…"))
        if kind in {"startup_pull", "pull", "push"}:
            progress = QProgressDialog(labels.get(kind, "GitHub…"), None, 0, 0, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(500)
            progress.setCancelButton(None)
            progress.show()
            self._github_progress = progress
        worker = _GitHubOperationWorker(self.settings, kind, file_path, project_name)
        self._github_worker = worker
        worker.signals.finished.connect(self._finish_github_operation)
        QThreadPool.globalInstance().start(worker)

    def _finish_github_operation(self, kind, result, error):
        self._github_busy = False
        self._github_worker = None
        if self._github_progress is not None:
            self._github_progress.close()
            self._github_progress = None
        if error:
            message = str(error)
            if kind == "startup_pull":
                self.statusBar().showMessage(self.t("GitHub startup pull failed: ", "Automatyczny pull z GitHuba nie powiódł się: ") + message, 12000)
            elif kind == "commit":
                self.statusBar().showMessage(self.t("Project saved, but GitHub commit failed: ", "Projekt zapisany, ale commit GitHub nie powiódł się: ") + message, 12000)
            else:
                QMessageBox.warning(self, "GitHub", message)
        elif kind == "commit":
            if result == "committed":
                self.statusBar().showMessage(self.t("Saved project committed locally. Push is still manual.", "Zapisany projekt zacommitowany lokalnie. Push nadal jest ręczny."), 5000)
            elif result == "outside-repository":
                self.statusBar().showMessage(self.t("Saved outside the configured Git repository; no commit was made.", "Zapisano poza skonfigurowanym repozytorium Git; commit nie powstał."), 8000)
        elif kind == "startup_pull":
            self.statusBar().showMessage(self.t("GitHub startup pull complete.", "Automatyczny pull z GitHuba zakończony."), 5000)
        else:
            QMessageBox.information(self, "GitHub", str(result or self.t("Operation complete.", "Operacja zakończona.")))
        self._start_next_github_operation()

    def _finish_cloud_operation(self, result, error, on_success):
        self._cloud_busy = False
        self._cloud_progress.close()
        value, tokens = result if result is not None else (None, self.settings.cloud_tokens)
        save_error = None
        if tokens != self.settings.cloud_tokens:
            self.settings.cloud_tokens = tokens
            try:
                save_settings(self.settings)
            except OSError as settings_error:
                save_error = settings_error
        if error:
            from app.services.cloud_storage import localized_cloud_error
            message = localized_cloud_error(error, self.settings.language)
            if save_error:
                message += "\n" + self.t("Updated credentials could not be saved: ",
                                          "Nie udało się zapisać odświeżonych danych logowania: ") + str(save_error)
            self._error(message)
            return
        if save_error:
            self._error(self.t("Cloud operation succeeded, but refreshed credentials could not be saved: ",
                               "Operacja w chmurze się powiodła, ale nie udało się zapisać odświeżonych danych logowania: ") + str(save_error))
        on_success(value)

    def _write_project(self, destination):
        self._sync_positions()
        try:
            save_project(destination, self.project)
        except (OSError, ValueError, TypeError) as error:
            self._error(str(error))
            return False
        # Ścieżkę i stan zapisany zmieniamy dopiero po udanym atomowym zapisie.
        self.current_file = Path(destination).with_suffix(".els")
        self.current_cloud_file = None
        self.current_cloud_provider = ""
        self._saved_state = deepcopy(self.project.to_dict())
        self._refresh_title()
        self.statusBar().showMessage(self.t("Project saved.", "Projekt zapisany."), 2500)
        if self.settings.cloud_provider == "github" and self.settings.github_repository_url:
            self._github_queue.append(("commit", str(self.current_file), self.project.name))
            self._start_next_github_operation()
        return True

    def save_project(self):
        return self.save_project_as() if self.current_file is None else self._write_project(self.current_file)

    def save_project_as(self):
        self._sync_positions()
        from app.core.file_names import project_filename
        filename, _ = QFileDialog.getSaveFileName(self, self.t("Save project", "Zapisz projekt"),
                                                  str(Path(file_dialog_directory(self.settings)) / project_filename(self.project.name,"els")), "ElectroSchem (*.els)")
        return self._write_project(Path(filename).with_suffix(".els")) if filename else False

    def _sync_positions(self):
        for index in range(self.tabs.count()):
            self.tabs.widget(index).finish_text_editing()
            self.tabs.widget(index)._sync_component_positions()

    def _is_dirty(self):
        return self.project.to_dict() != self._saved_state

    def _confirm_discard(self):
        self._sync_positions()
        if not self._is_dirty():
            return True
        choice = QMessageBox.question(self, self.t("Unsaved changes", "Niezapisane zmiany"),
                                      self.t("Save changes before continuing?", "Zapisać zmiany przed kontynuowaniem?"),
                                      QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard |
                                      QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Save)
        if choice == QMessageBox.StandardButton.Save:
            return self.save_project()
        return choice == QMessageBox.StandardButton.Discard

    def closeEvent(self, event):
        if self._confirm_discard():
            if getattr(self, "simulation_window", None):
                self.simulation_window.close()
            if self.ai_panel:
                self.ai_panel.cancel()
            if getattr(self, "command_panel", None): self.command_panel.cancel_request()
            event.accept()
        else:
            event.ignore()

    def set_active_tool(self, tool):
        self._active_tool = tool
        paint_color = getattr(self.settings, "wire_paint_color", "#167d3d")
        if tool == "wire_color":
            selected = QColorDialog.getColor(
                QColor(paint_color), self,
                "Kolor połączenia" if self.settings.language == "pl" else "Wire color")
            if selected.isValid():
                paint_color = selected.name(QColor.NameFormat.HexRgb)
                self.settings.wire_paint_color = paint_color
                try:
                    save_settings(self.settings)
                except (OSError, ValueError) as error:
                    self.statusBar().showMessage(
                        self.t("Color will be remembered for this session only: ",
                               "Kolor zostanie zapamiętany tylko w tej sesji: ") + str(error), 5000)
        self._current_view().set_tool(tool, paint_color)
        labels = {
            "select": ("Select / move; double-click for properties.", "Zaznacz / przesuń; dwuklik otwiera właściwości."),
            "wire_color": ("Click a wire to paint its unbranched connected cable.", "Kliknij przewód, aby pomalować jego nierozgałęzioną trasę."),
            "wire": ("Click pins to connect. Right-click cancels drawing.", "Klikaj piny, aby połączyć. PPM anuluje rysowanie."),
            "delete": ("Click an item to remove it. X activates this tool; Delete removes the selection.", "Kliknij obiekt do usunięcia. X włącza to narzędzie; Del usuwa zaznaczenie."),
            "comment": ("Click the sheet to add an Arial comment.", "Kliknij arkusz, aby dodać komentarz czcionką Arial."),
        }
        self.statusBar().showMessage(self.t(*labels[tool]))

    def _selection_changed(self, component):
        if self.ai_panel:
            self.ai_panel.update_context_label()
        self._selected_component = component
        self.properties_action.setEnabled(component is not None)
        if component is not None:
            self.statusBar().showMessage(self.t("Selected: ", "Zaznaczono: ") + component.reference, 2200)

    def edit_selected_properties(self):
        if self._selected_component is not None:
            self.show_component_properties(self._selected_component)

    def show_component_properties(self, component):
        if component is None:
            return
        if component.properties.get('_asset_properties_editable')=='false':
            self._error(self.t('This Asset member is locked. Enable property editing in the Asset case editor.','Ten element Assetu jest zablokowany. Włącz edycję właściwości w edytorze obudowy Assetu.')); return
        definition = get_definition(component.library_id, self.project.custom_components)
        dialog = ComponentPropertiesDialog(component, definition, self.settings.language, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dict(dialog.values)
        extra_key = values.pop("extra_key", "")
        extra_value = values.pop("extra_value", "")
        extra_show = values.pop("extra_show", False)
        component.properties.update(values.pop("simulation_properties", {}))
        from app.core.editor_operations import set_property
        for key, value in values.items():
            set_property(component, key, value)
        if extra_key:
            if extra_value:
                component.properties[extra_key] = extra_value
            else:
                component.properties.pop(extra_key, None)
            component.properties["show_" + extra_key] = bool(extra_show)
        if dialog.save_default_name.isChecked():
            text = component.display_name.strip()
            if text:
                self.settings.default_display_names[component.library_id] = text
            else:
                self.settings.default_display_names.pop(component.library_id, None)
        if dialog.save_default_values.isChecked():
            from app.core.component_defaults import value_defaults
            self.settings.default_component_values[component.library_id]=value_defaults(component)
        if dialog.save_default_name.isChecked() or dialog.save_default_values.isChecked():
            try:
                save_settings(self.settings)
            except OSError as error:
                self._error(str(error))
        component.properties["description"] = dialog.description.text().strip()
        self._current_view().refresh_component(component.id)
        self.record_history()

    def _reset_history(self):
        self._history = [deepcopy(self.project.to_dict())]
        self._redo_history = []
        self._saved_state = deepcopy(self.project.to_dict())
        self._refresh_title()

    def record_history(self):
        snapshot = deepcopy(self.project.to_dict())
        if not self._history or self._history[-1] != snapshot:
            # Data opisuje zmianę treści dokumentu, a nie samo otwarcie,
            # przesunięcie widoku, eksport lub ponowny zapis bez zmian.
            self.project.metadata["modified_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
            snapshot = deepcopy(self.project.to_dict())
            self._history.append(snapshot)
            self._redo_history.clear()
            for index in range(self.tabs.count()):
                self.tabs.widget(index).viewport().update()
        self._refresh_title()

    def refresh_last_route_snapshot(self):
        """Store derived async routes in the existing edit's undo snapshot."""
        if not self._history:
            return
        current = deepcopy(self.project.to_dict())
        previous = self._history[-1]
        comparable = deepcopy(current)
        previous_sheets = {sheet.get("id"): sheet for sheet in previous.get("sheets", [])}
        for sheet in comparable.get("sheets", []):
            old_sheet = previous_sheets.get(sheet.get("id"), {})
            old_wires = {wire.get("id"): wire for wire in old_sheet.get("wires", [])}
            for wire in sheet.get("wires", []):
                old_wire = old_wires.get(wire.get("id"))
                if old_wire is not None:
                    wire["points"] = deepcopy(old_wire.get("points", []))
        # Do not rewrite history if anything besides the computed paths changed
        # while the worker ran; in that case the route result was already stale.
        if comparable == previous:
            self._history[-1] = current

    def undo(self):
        if len(self._history) < 2:
            return
        self._redo_history.append(self._history.pop())
        self.project = Project.from_dict(deepcopy(self._history[-1]))
        self._rebuild_tabs()
        self._history[-1] = deepcopy(self.project.to_dict())
        self._refresh_title()

    def redo(self):
        if not self._redo_history:
            return
        snapshot = self._redo_history.pop()
        self.project = Project.from_dict(deepcopy(snapshot))
        self._rebuild_tabs()
        self._history.append(deepcopy(self.project.to_dict()))
        self._refresh_title()

    def _refresh_title(self):
        # Nazwa projektu pozostaje widoczna i edytowalna także po zapisaniu;
        # nazwa pliku jest szczegółem kontenera ELS, nie tytułem rysunku.
        name = self.project.name
        marker = " *" if self._is_dirty() else ""
        self.setWindowTitle(f"ElectroSchem {APP_VERSION} — {name}{marker}")
        self.undo_action.setEnabled(len(self._history) > 1)
        self.redo_action.setEnabled(bool(self._redo_history))

    def _error(self, message):
        from app.core.messages import localize
        message=localize(message,self.settings.language)
        QMessageBox.critical(self, self.t("ElectroSchem — error", "ElectroSchem — błąd"), message)

    def export_pdf(self):
        self._export("pdf")

    def _export(self, kind):
        self._sync_positions()
        from app.core.file_names import project_filename
        from app.services.export import export_pdf, export_png, export_svg
        filename, _ = QFileDialog.getSaveFileName(self, self.t("Export drawing", "Eksportuj schemat"),
                                                  str(Path(file_dialog_directory(self.settings)) / project_filename(self.project.name,kind)), f"{kind.upper()} (*.{kind})")
        if not filename:
            return
        try:
            target = Path(filename).with_suffix("." + kind)
            if kind == "pdf":
                export_pdf(target, [self.tabs.widget(i) for i in range(self.tabs.count())])
            else:
                (export_png if kind == "png" else export_svg)(target, self._current_view())
        except (OSError, ValueError, RuntimeError, MemoryError) as error:
            self._error(str(error))
            return
        self.statusBar().showMessage(self.t("Export completed.", "Eksport ukończony."), 2500)

    def fit_current_page(self):
        self._current_view().fit_page()

    def show_settings(self, first_run=False):
        dialog = SettingsDialog(self.settings, self, first_run=first_run)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        candidate = dialog.result_settings()
        try:
            save_settings(candidate)
        except OSError as error:
            self._error(str(error))
            return
        self.settings = candidate
        if getattr(self, "command_panel", None):
            self.command_panel.cancel_request()
            self.command_panel.translate()
            self.command_dock.setWindowTitle(self.t("AI assistant", "Asystent AI"))
        from app.ui.theme import apply_theme
        apply_theme(self,self.settings)
        from app.ui.window_mode import show_window
        show_window(self,self.settings)
        simulation=getattr(self,"simulation_window",None)
        if simulation is not None:
            simulation.fault_animation.stop(); simulation.animate_faults(1)
            if simulation.fault_sound is not None: simulation.fault_sound.stop()
            simulation.refresh_theme()
            simulation.refresh_language()
            if simulation.isVisible(): show_window(simulation,self.settings)
        if self.ai_panel:
            self.ai_panel.cancel()
            self.ai_panel._consented = False
            self.ai_panel.translate()
            self.ai_dock.setWindowTitle(self.t("AI assistant", "Asystent AI"))
        # Pierwszy pusty dokument dopasowujemy do kreatora. Istniejących
        # projektów ustawienie domyślne nigdy nie przeskalowuje w tle.
        if first_run and self.current_file is None and not self._is_dirty():
            self.project = self._empty_project()
            self._rebuild_tabs(selected=0)
            self._reset_history()
        else:
            for index in range(self.tabs.count()):
                self.tabs.widget(index).apply_settings(self.settings)
        self._translate_ui()

    def create_custom_component(self):
        dialog = CustomComponentDialog(self.settings.language, self)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.definition:
            return
        self.project.custom_components.append(deepcopy(dialog.definition))
        self.record_history()
        self.add_component_from_id(dialog.definition["id"])

    def save_as_asset(self):
        self._sync_positions()
        view=self._current_view()
        selected={item.data(1) for item in view.scene.selectedItems() if item.data(0)=="component"}
        if not selected:
            self._error(self.t('Select components to save as an Asset first.','Najpierw zaznacz elementy, które mają trafić do assetu.')); return
        name,ok=QInputDialog.getText(self,self.t("Save circuit as Asset","Zapisz układ jako Asset"),self.t("Asset name","Nazwa assetu"))
        if not ok or not name.strip(): return
        boxed=QMessageBox.question(self,self.t("Asset case","Obudowa assetu"),self.t(
            "Design a case around the selected circuit? No keeps its original form.",
            "Zaprojektować obudowę zaznaczonego układu? Nie zachowuje jego oryginalną postać."),
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.No)
        if boxed==QMessageBox.StandardButton.Cancel: return
        grouped=True
        if boxed==QMessageBox.StandardButton.No:
            choice=QMessageBox.question(self,self.t('Asset behavior','Zachowanie assetu'),self.t(
                'Move, rotate and select the asset contents together? Choose No for independent components. Shift temporarily selects individual components.',
                'Czy przesuwać, obracać i zaznaczać zawartość jako całość? Nie oznacza osobne elementy. Shift tymczasowo przełącza na wybór pojedynczych elementów.'),
                QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Yes)
            if choice==QMessageBox.StandardButton.Cancel: return
            grouped=choice==QMessageBox.StandardButton.Yes
        try:
            from app.core.assets import make_asset,save_asset
            definition=make_asset(self.project,self.project.sheets[self.tabs.currentIndex()],name,boxed==QMessageBox.StandardButton.Yes,selected,grouped)
            if boxed==QMessageBox.StandardButton.Yes:
                from app.ui.paint_case_editor import PaintAssetCaseEditor as AssetCaseEditor
                dialog=AssetCaseEditor(definition,self.settings,self)
                if dialog.exec()!=QDialog.DialogCode.Accepted: return
                definition=dialog.definition
            save_asset(definition)
            self.project.custom_components.append(definition); self.record_history()
            self.statusBar().showMessage(self.t("Asset saved in the Custom library.","Asset zapisany w bibliotece Customowe elementy."),8000)
        except (ValueError,OSError) as error: self._error(str(error))

    def place_asset(self,definition,global_pos=None):
        from app.core.assets import instantiate, with_asset_dependencies
        from app.core.models import ComponentInstance
        from app.canvas.component_item import ComponentItem
        from app.canvas.page import fit_component_position
        from PySide6.QtCore import QPointF,QRectF
        from PySide6.QtGui import QTransform
        view=self._current_view(); index=self.tabs.currentIndex()
        staged=Project.from_dict(deepcopy(self.project.to_dict())); staged.custom_components=with_asset_dependencies(staged.custom_components)
        instance=ComponentInstance(definition["id"],0,0)
        content,_=instantiate(definition["asset"],instance,staged)
        bounds=QRectF()
        for c in content.components:
            d=get_definition(c.library_id,staged.custom_components)
            bounds=bounds.united(QTransform().rotate(c.rotation).mapRect(ComponentItem.selection_rect(d)).translated(c.x,c.y))
        point=view._snap(view.mapToScene(view.mapFromGlobal(global_pos or QCursor.pos())))
        point=fit_component_position(staged.sheets[index],bounds,point)
        if point is None: raise ValueError(self.t("Asset does not fit this sheet.","Asset nie mieści się na arkuszu."))
        # Instantiate again at the fitted position in a fresh staging copy so
        # failed insertion never consumes references or touches the document.
        staged=Project.from_dict(deepcopy(self.project.to_dict())); staged.custom_components=with_asset_dependencies(staged.custom_components)
        instance.x,instance.y=point.x(),point.y(); content,_=instantiate(definition["asset"],instance,staged)
        staged.sheets[index].components.extend(content.components); staged.sheets[index].wires.extend(content.wires); staged.sheets[index].comments.extend(content.comments)
        self.project=Project.from_dict(staged.to_dict()); self._rebuild_tabs(selected=index); self.record_history()
        return content.components[0]

    def edit_custom_component(self, library_id):
        from app.core.custom_library import replace_custom
        definition = next((entry for entry in self.project.custom_components if entry["id"] == library_id), None)
        if definition is None and library_id.startswith("asset_"):
            from app.core.assets import load_assets,with_asset_dependencies
            definition=next((d for d in load_assets() if d["id"]==library_id),None)
        if definition is None:
            return
        if 'asset' in definition:
            from app.ui.paint_case_editor import PaintAssetCaseEditor as AssetCaseEditor
            dialog=AssetCaseEditor(definition,self.settings,self)
        else: dialog = CustomComponentDialog(self.settings.language, self, definition=definition)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.definition:
            return
        self._sync_positions()
        try:
            if "asset" in definition:
                in_use=any(c.library_id==library_id for s in self.project.sheets for c in s.components)
                if in_use:
                    from app.core.custom_library import existing_asset_pins_preserved
                    current=next((d for d in self.project.custom_components if d["id"]==library_id),definition)
                    if not existing_asset_pins_preserved(current,dialog.definition):
                        raise ValueError(self.t(
                            "When an asset is already used on a sheet, existing pins must keep their number, identity and position. You may append new pins.",
                            "Gdy asset jest już używany na schemacie, istniejące piny muszą zachować numer, tożsamość i położenie. Możesz dopisywać nowe piny na końcu."))
                from app.core.assets import save_asset
                save_asset(dialog.definition)
            if not any(d["id"]==library_id for d in self.project.custom_components):
                from app.core.assets import with_asset_dependencies
                self.project.custom_components=with_asset_dependencies(self.project.custom_components+[definition])
            replace_custom(self.project, dialog.definition)
        except (ValueError,OSError) as error:
            self._error(str(error)); return
        self._rebuild_tabs()
        self.record_history()

    def delete_custom_component(self, library_id):
        from app.core.custom_library import remove_custom
        definition = next((entry for entry in self.project.custom_components if entry["id"] == library_id), None)
        global_asset=None
        if library_id.startswith("asset_"):
            from app.core.assets import load_assets
            try: global_asset=next((d for d in load_assets() if d["id"]==library_id),None)
            except (ValueError,OSError) as error: self._error(str(error)); return
            definition=definition or global_asset
        if definition is None:
            return
        count = sum(component.library_id == library_id for sheet in self.project.sheets for component in sheet.components)
        message = self.t(
            f'Delete "{definition["name"]}" from the library and its {count} instances on all sheets? Wires remain with disconnected ends. Ctrl+Z restores the deletion.',
            f'Usunąć „{definition["name"]}” z biblioteki i wszystkie jego kopie ({count}) na arkuszach? Przewody pozostaną z odłączonymi końcami. Ctrl+Z przywraca usunięcie.')
        if global_asset:
            message += self.t(" The reusable asset will also be removed from the shared library. Undo restores this project only; other saved ELS files retain their embedded definition.",
                " Asset zostanie też usunięty ze wspólnej biblioteki. Cofnij przywraca tylko ten projekt; inne zapisane pliki ELS zachowują własną definicję.")
        if QMessageBox.question(self, self.t("Delete custom component", "Usuń własny element"), message,
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        self._sync_positions()
        if global_asset:
            from app.core.assets import remove_asset
            try: remove_asset(library_id)
            except (ValueError,OSError) as error: self._error(str(error)); return
        remove_custom(self.project, library_id)
        self._rebuild_tabs()
        self.record_history()

    def _ai_context(self):
        from app.libraries.simulation_catalog import behavior_for
        # Przekazujemy tylko bieżący arkusz i dane biblioteki. Ustawienia,
        # ścieżki plików oraz sekret API nie są częścią kontekstu modelu.
        sheet = self.project.sheets[self.tabs.currentIndex()]
        # Stare ukryte definicje trafiają do kontekstu tylko gdy faktycznie
        # istnieją na arkuszu; AI nie proponuje usuniętych pozycji biblioteki.
        existing_ids = {component.library_id for component in sheet.components}
        definitions = list(AVAILABLE_ITEMS)
        definitions.extend(item for item in BUILT_IN_ITEMS if item not in AVAILABLE_ITEMS and item.id in existing_ids)
        definitions.extend(get_definition(raw["id"], self.project.custom_components)
                           for raw in self.project.custom_components)
        return {
            "sheet": asdict(sheet),
            "dimensions_scene": [value * 4 for value in sheet.dimensions_mm()],
            "grid_step": 20,
            "drawing_area_scene": [40, 40, (sheet.dimensions_mm()[0] * 4 // 20)*20 - 40,
                                    (sheet.dimensions_mm()[1] * 4 // 20)*20 - 160],
            "drawing_regions_scene": [[r.left(), r.top(), r.right(), r.bottom()] for r in drawing_regions(sheet)],
            "forbidden_title_block_scene": list(title_block_rect(sheet).getRect()),
            "library": [
                {"id": item.id, "name": item_name(item, self.settings.language),
                 "symbol": item.symbol, "default_unit": item.default_unit,
                 "editable_parameters": [asdict(p) for p in behavior_for(item).parameters] if behavior_for(item) else [],
                 "width": item.width, "height": item.height, "variant": item.variant,
                 "verified": item.verified, "pins": [
                     {"index": index, "number": pin.number, "name": pin.name, "x": pin.x, "y": pin.y}
                     for index, pin in enumerate(item.pins)]}
                for item in definitions if item is not None],
        }

    def selection_command(self, operation):
        view = self._current_view()
        if view is None or view.is_editing_text():
            return
        try:
            if operation == "duplicate":
                view.paste_selection(duplicate=True)
            elif operation == "paste":
                view.paste_selection()
            elif operation == "cut":
                view.cut_selected()
            elif operation == "copy":
                view.copy_selected()
        except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as error:
            self._error(self.t("Cannot use this clipboard selection. ", "Nie można użyć tego zaznaczenia ze schowka. ") + str(error))

    def show_datasheet_ai(self):
        self.show_ai(documentation=True)

    def show_ai(self, *, documentation=False):
        if not AI_AVAILABLE:
            return
        if not documentation:
            if self.settings.ai_provider == "none": return
            self.show_command_panel()
            return
        # Integracja wycofana w rc14: brak importu i inicjalizacji klienta
        # sieciowego podczas normalnego uruchamiania edytora.
        from app.ui.ai_dialog import AiDialog
        from app.ui.ai_panel import AiPanel
        from app.services.proposals import apply_proposal
        # Skrót i bezpośrednie wywołanie też respektują wyłączone AI.
        if not self.settings.api_key:
            return
        if not documentation:
            if self.ai_panel is None:
                self.ai_panel = AiPanel(self)
                self.ai_dock = QDockWidget(self.t("AI assistant", "Asystent AI"), self)
                self.ai_dock.setObjectName("assistantDock")
                self.ai_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
                self.ai_dock.setWidget(self.ai_panel)
                self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.ai_dock)
                self.resizeDocks([self.ai_dock], [430], Qt.Orientation.Horizontal)
                self.tabs.currentChanged.connect(self.ai_panel.update_context_label)
            self.ai_dock.show()
            self.ai_dock.raise_()
            self.ai_panel.update_context_label()
            self.ai_panel.prompt.setFocus()
            return
        if not self.settings.api_key:
            QMessageBox.information(self, self.t("AI disabled", "AI wyłączone"),
                                    self.t("Add a Gemini API key in Options → Settings to enable AI.",
                                           "Podaj klucz API Gemini w Opcje → Ustawienia, aby włączyć AI."))
            return
        sheet_index = self.tabs.currentIndex()

        def apply(payload):
            # Dopiero pełna walidacja zwraca nowy dokument. Nieudana propozycja
            # nie zostawia połowy układu ani zużytych numerów elementów.
            self.project = apply_proposal(self.project, sheet_index, payload)
            self._rebuild_tabs(selected=sheet_index)
            self.record_history()

        self._sync_positions()
        context = self._ai_context()
        if documentation:
            # Analizator nie przesyła arkusza ani rozmowy zwykłego asystenta.
            context = {"library": context["library"], "grid_step": 20}
        dialog = AiDialog(self.settings, context, apply, self, documentation=documentation)
        dialog.exec()

    def show_command_panel(self, terminal=False):
        from app.ui.command_panel import CommandPanel
        panel = getattr(self, "command_panel", None)
        if panel is None:
            panel = CommandPanel(self)
            self.command_panel = panel
            self.command_dock = QDockWidget(self.t("AI assistant", "Asystent AI"), self)
            self.command_dock.setObjectName("commandDock")
            self.command_dock.setWidget(panel)
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.command_dock)
            self.resizeDocks([self.command_dock], [460], Qt.Orientation.Horizontal)
        panel.tabs.setCurrentIndex(1 if terminal else 0)
        self.command_dock.show(); self.command_dock.raise_()
        panel.update_context_label()

    def show_simulation(self):
        from app.ui.simulation_window import SimulationWindow
        self._sync_positions()
        window = getattr(self, "simulation_window", None)
        if window is None:
            window = SimulationWindow(self)
            self.simulation_window = window
            window.destroyed.connect(lambda: setattr(self, "simulation_window", None))
        from app.ui.window_mode import show_window
        window.refresh_theme()
        window.refresh_language()
        show_window(window,self.settings)
        window.raise_()
        window.activateWindow()

    def open_code(self):
        if self._selected_component is not None:
            from app.libraries.emulator_catalog import profile_for
            if profile_for(get_definition(self._selected_component.library_id)):
                self.edit_component_code(self._selected_component)
                return
        editor = self.settings.editor_path or default_editor()
        if not editor or not Path(editor).is_file():
            self._error(self.t("Select an installed code editor in Settings.", "Wybierz zainstalowany edytor kodu w ustawieniach."))
            return
        filename, _ = QFileDialog.getOpenFileName(self, self.t("Select code file", "Wybierz plik kodu"),
                                                  file_dialog_directory(self.settings), "Code (*.py *.ino *.c *.cpp *.h *.txt);;All files (*)")
        if not filename:
            return
        try:
            # Lista argumentów i shell=False: nazwa pliku nie jest poleceniem.
            subprocess.Popen([editor, str(Path(filename).resolve())], shell=False)
        except OSError as error:
            self._error(str(error))

    def _new_code_destination(self,component):
        if component.properties.get("sim_source", "").strip(): return None
        from app.core.board_code import default_source_filename
        filename=default_source_filename(component,self.project)
        folder=Path(self.settings.default_code_directory or default_code_directory())
        filter="Arduino (*.ino)" if filename.endswith('.ino') else "Python (*.py)"
        selected,_=QFileDialog.getSaveFileName(self,self.t("Create and Assign Code","Utwórz i Przypisz Kod"),
            str(folder/filename),filter,options=QFileDialog.Option.DontConfirmOverwrite)
        return selected

    def edit_component_code(self, component):
        from app.core.board_code import ensure_source
        destination=self._new_code_destination(component)
        if destination == "": return
        try:
            source = ensure_source(component, self.project, self.settings.default_code_directory or default_code_directory(), destination=destination)
            self.record_history()
            editor = self.settings.editor_path or default_editor()
            if not editor or not Path(editor).is_file():
                raise OSError(self.t("Select a code editor in Settings.", "Wybierz edytor kodu w ustawieniach."))
            subprocess.Popen([editor, str(source)], shell=False)
        except (OSError, ValueError) as error:
            self._error(str(error))

    def edit_component_code_folder(self, component):
        from app.core.board_code import ensure_code_folder
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        destination=self._new_code_destination(component)
        if destination == "": return
        try:
            folder=ensure_code_folder(component,self.project,self.settings.default_code_directory or default_code_directory(),destination=destination)
            self.record_history()
            editor=self.settings.editor_path or default_editor()
            if editor and Path(editor).is_file() and Path(editor).stem.lower() in {"code","codium","cursor"}:
                subprocess.Popen([editor,str(folder)],shell=False)
            elif not QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder))):
                raise OSError(self.t("Could not open the code folder.","Nie można otworzyć folderu kodu."))
        except (OSError,ValueError) as error:
            self._error(str(error))

    def assign_component_code(self,component):
        if component.properties.get("sim_source", "").strip(): return
        from app.core.board_code import assign_source
        definition=get_definition(component.library_id)
        filters="Python (*.py)"
        if definition and definition.name in {"Arduino Uno R3","Arduino Nano"}: filters+=";;Arduino (*.ino)"
        filters+=";;"+self.t("All files (*)","Wszystkie pliki (*)")
        filename,_=QFileDialog.getOpenFileName(self,self.t("Assign Existing Code","Przypisz Istniejący Kod"),
                                               code_dialog_directory(self.settings),filters)
        if not filename: return
        try:
            assign_source(component,filename)
            self.record_history()
        except (OSError,ValueError) as error: self._error(str(error))

    def detach_component_code(self,component):
        # Remove references only. Source files and workspace contents belong
        # to the user and must never be deleted by this operation.
        if not component.properties.get("sim_source", "").strip(): return
        for key in ("sim_source", "sim_code_folder", "sim_firmware"):
            component.properties.pop(key,None)
        self.record_history()

    def search_components(self):
        from PySide6.QtWidgets import QListWidget
        dialog = QDialog(self)
        dialog.setWindowTitle(self.t("Find component", "Wyszukaj element"))
        layout = QVBoxLayout(dialog)
        query, results = QLineEdit(), QListWidget()
        layout.addWidget(query); layout.addWidget(results)
        position = QCursor.pos()
        def refresh(text):
            results.clear()
            for d in AVAILABLE_ITEMS:
                label = item_name(d, self.settings.language)
                primary=next((self.t(en,pl) for en,pl,_,categories in LIBRARY_GROUPS if d.category in categories),d.category)
                group=self.t(*subgroup(d))
                category=primary if primary==group else primary+" / "+group
                if text.casefold() in (label+" "+category).casefold():
                    results.addItem(label+"   ["+category+"]")
                    results.item(results.count()-1).setData(Qt.ItemDataRole.UserRole, d.id)
        def place(item):
            identity = item.data(Qt.ItemDataRole.UserRole)
            dialog.accept()
            self.add_component_from_id(identity, global_pos=position)
        query.textChanged.connect(refresh)
        results.itemDoubleClicked.connect(place)
        refresh(""); dialog.resize(460, 500); dialog.exec()

    def edit_document_info(self):
        name, ok = QInputDialog.getText(self, self.t("Drawing information", "Dane tabliczki rysunkowej"),
                                       self.t("Project title:", "Tytuł projektu:"), text=self.project.name)
        if not ok:
            return
        author, ok = QInputDialog.getText(self, self.t("Drawing information", "Dane tabliczki rysunkowej"),
                                         self.t("Author:", "Autor:"), text=self.project.metadata.get("author", ""))
        if ok:
            self.project.name = name.strip()[:250] or self.project.name
            self.project.metadata["author"] = author.strip()[:250]
            for index in range(self.tabs.count()):
                self.tabs.widget(index).viewport().update()
            self.record_history()

    def set_sheet_standard(self, standard):
        """Zmiana normy bieżącego arkusza bez przeładowywania projektu."""
        if standard not in {"EN", "PN", "ISO", "IEEE/ANSI"} or not self.project.sheets:
            return
        sheet = self.project.sheets[self.tabs.currentIndex()]
        sheet.standard = standard
        self.settings.standard = standard
        for action in self.standard_actions.values():
            action.setChecked(action is self.standard_actions[standard])
        self._current_view().apply_settings(self.settings)
        self._current_view().viewport().update()
        self.record_history()

    def show_component_info(self):
        selected = self._current_view().scene.selectedItems()
        view=self._current_view(); point=view.mapToScene(view.mapFromGlobal(QCursor.pos()))
        hovered=next((item for item in view.scene.items(point) if item.data(0)=='component'),None)
        if hovered is not None: selected=[hovered]
        if len(selected) != 1:
            self.statusBar().showMessage(self.t("Select one object and press H.", "Zaznacz jeden obiekt i naciśnij H."), 3000)
            return
        kind = selected[0].data(0)
        if kind in {"wire", "comment"}:
            text = (self.t("A wire connects circuit terminals. Its endpoints can attach to pins or wire junctions; crossing lines alone does not create a connection.",
                           "Przewód łączy zaciski obwodu. Jego końce można podłączać do pinów lub węzłów; samo skrzyżowanie linii nie tworzy połączenia.") if kind == "wire" else
                    self.t("A comment is a text note on the sheet, not an electrical connection. Double-click it to edit.",
                           "Komentarz to notatka tekstowa na arkuszu, a nie połączenie elektryczne. Dwuklik pozwala go edytować."))
            QMessageBox.information(self, self.t("Object information", "Informacje o obiekcie"), text)
            return
        if kind != "component":
            return
        component = selected[0].component
        definition = get_definition(component.library_id, self.project.custom_components)
        if definition is None:
            return
        custom = next((entry for entry in self.project.custom_components if entry.get("id") == definition.id), None)
        ComponentInfoDialog(component, definition, self.settings.language, custom, self).exec()

    def show_help(self):
        from app.ui.manual_dialog import ManualDialog
        ManualDialog(self.settings.language,self).exec()
