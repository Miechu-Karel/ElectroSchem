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

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QIcon, QKeySequence, QCursor
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QDockWidget, QFileDialog, QInputDialog, QLabel, QMainWindow,
    QMenu, QMessageBox, QStatusBar, QTabWidget, QToolBar, QToolButton,
    QVBoxLayout, QFormLayout, QLineEdit, QPushButton, QWidget,
)

from app.canvas.schematic_view import SchematicView
from app.core.models import Project, Sheet
from app.core.project_file import load_project, save_project
from app.core.settings import AppSettings, default_editor, load_settings, save_settings, file_dialog_directory
from app.libraries.built_in import BUILT_IN_ITEMS, AVAILABLE_ITEMS, get_definition, item_name
from app.libraries.menu_groups import subgroup
from app.core.features import AI_AVAILABLE
from app.ui.i18n import install_ui_language
from app.ui.component_dialogs import CustomComponentDialog, ProjectDialog
from app.ui.component_info_dialog import ComponentInfoDialog
from app.ui.properties_dialog import ComponentPropertiesDialog
from app.ui.settings_dialog import SettingsDialog
from app.canvas.page import drawing_regions, title_block_rect
from app.ui.sheet_tabs import SheetTabBar
from app.ui.shortcuts import EditorShortcuts

APP_VERSION = "1.0.0"
ICON_DIR = Path(__file__).resolve().parents[2] / "Ikonki"

# Kolejność odpowiada szkicowi oraz literom E/S/I/C/M w skrótach.
LIBRARY_GROUPS = (
    ("Electronic components", "Elementy elektroniczne", "Elementy Elektroniczne.png",
     {"Elementy pasywne", "Półprzewodniki", "Zasilanie i połączenia"}),
    ("Sensors, modules and drives", "Czujniki, moduły i napędy", "Czujnik.png", {"Czujniki", "Moduły i interfejsy", "Napędy"}),
    ("Integrated circuits", "Układy scalone", "Domyślne Układy Scalone.png", {"Układy i sterowniki"}),
    ("Custom components", "Customowe elementy", "Customowe Elementy.png", {"Własne"}),
    ("Microcontrollers and computers", "Mikrokontrolery i mikrokomputery", "Mikrokontrolery.png", {"Mikrokontrolery i SBC"}),
)


class MainWindow(QMainWindow):
    """Jeden dokument, wiele arkuszy, wspólna historia i ustawienia użytkownika."""

    def __init__(self, settings: AppSettings | None = None, start_setup: bool = True):
        super().__init__()
        self.settings = settings if settings is not None else load_settings()
        self.project = self._empty_project()
        self.current_file: Path | None = None
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
        self._create_component_library()
        self._create_workspace()
        self._create_tools()
        self._create_menu()
        self._reset_history()
        self.shortcuts = EditorShortcuts(self)
        self._translate_ui()
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #f6f9fc; color: #162a3a; }
            QMenuBar, QMenu, QStatusBar { background: #ffffff; color: #162a3a; }
            QMenu::item:selected { background: #d8f0f8; color: #102a43; }
            QToolBar { background: #ffffff; border: 1px solid #d6e1ea; spacing: 6px; padding: 5px; }
            QToolButton { min-width: 38px; min-height: 38px; border-radius: 5px; color: #162a3a; }
            QToolButton:hover { background: #e6f3f7; }
            QToolButton:checked { background: #ccecf5; color: #075a7b; }
            QToolButton:disabled { color: #8a98a2; }
            QLineEdit, QTextEdit, QPlainTextEdit, QTableWidget, QComboBox, QSpinBox {
                background: white; color: #162a3a; selection-background-color: #bce4f0;
            }
            QDialogButtonBox QPushButton { min-width: 80px; padding: 5px; }
            QTabWidget::pane { border: 0; }
        """)
        # Timer pokazuje konfigurację dopiero po uruchomieniu pętli zdarzeń.
        # Testy i narzędzia mogą jawnie wyłączyć ten jednorazowy dialog.
        if start_setup and not self.settings.setup_complete:
            QTimer.singleShot(0, lambda: self.show_settings(first_run=True))

    def t(self, en: str, pl: str) -> str:
        return pl if self.settings.language == "pl" else en

    def _empty_project(self):
        return Project(name=self.t("New project", "Nowy projekt"), sheets=[
            Sheet(name=self.t("Sheet 1", "Arkusz 1"), paper_size=self.settings.paper_size,
                  orientation=self.settings.orientation, standard=self.settings.standard)])

    @staticmethod
    def _icon(filename):
        return QIcon(str(ICON_DIR / filename))

    def _action(self, en, pl, callback=None, shortcut=None, icon=None, checkable=False):
        action = QAction(self.t(en, pl), self)
        self._action_labels[action] = (en, pl)
        if callback:
            action.triggered.connect(callback)
        if shortcut:
            action.setShortcut(shortcut)
        if icon:
            action.setIcon(self._icon(icon))
        action.setCheckable(checkable)
        return action

    def _create_actions(self):
        self.new_action = self._action("New project…", "Nowy projekt…", self.new_project, QKeySequence.StandardKey.New)
        self.open_action = self._action("Open project…", "Otwórz projekt…", self.open_project, QKeySequence.StandardKey.Open)
        self.save_action = self._action("Save", "Zapisz", self.save_project, QKeySequence.StandardKey.Save)
        self.save_as_action = self._action("Save as…", "Zapisz jako…", self.save_project_as, QKeySequence.StandardKey.SaveAs)
        self.export_pdf_action = self._action("PDF", "PDF", self.export_pdf)
        self.export_png_action = self._action("PNG", "PNG", lambda: self._export("png"))
        self.export_svg_action = self._action("SVG", "SVG", lambda: self._export("svg"))
        self.help_action = self._action("Help", "Pomoc", self.show_help)
        self.standard_actions = {}
        for standard in ("EN", "PN", "ISO"):
            action = self._action(standard, standard, lambda checked=False, value=standard: self.set_sheet_standard(value), checkable=True)
            self.standard_actions[standard] = action
        self.add_sheet_action = self._action("Add sheet (Shift+A, S)", "Dodaj arkusz (Shift+A, S)", self.add_sheet, icon="Dodaj Arkusz.png")
        self.ai_action = self._action("AI assistant (Shift+A, I)", "Asystent AI (Shift+A, I)", self.show_ai, icon="Funkcje AI.png")
        self.datasheet_action = self._action("Analyse datasheet PDF…", "Analizuj dokumentację PDF…", self.show_datasheet_ai)
        self.clipboard_actions = [self._action(en, pl, lambda checked=False, op=op: self.selection_command(op))
                                  for en, pl, op in (
                                      ("Duplicate (Ctrl+D)", "Duplikuj (Ctrl+D)", "duplicate"),
                                      ("Cut (Ctrl+X)", "Wytnij (Ctrl+X)", "cut"),
                                      ("Copy (Ctrl+C)", "Kopiuj (Ctrl+C)", "copy"),
                                      ("Paste (Ctrl+V)", "Wklej (Ctrl+V)", "paste"))]
        self.fit_page_action = self._action("Reset zoom / fit sheet", "Zeruj zoom / dopasuj arkusz", self.fit_current_page, icon="Zeruj Zoom.png")
        self.select_action = self._action("Select (S)", "Zaznaczanie (S)", lambda: self.set_active_tool("select"), icon="Kursor.png", checkable=True)
        self.wire_action = self._action("Draw connections (D)", "Rysuj połączenia (D)", lambda: self.set_active_tool("wire"), icon="Rysik.png", checkable=True)
        self.delete_action = self._action("Delete tool", "Narzędzie usuwania", lambda: self.set_active_tool("delete"), icon="Usuń v2.png", checkable=True)
        self.comment_action = self._action("Add comment", "Dodaj komentarz", lambda: self.set_active_tool("comment"), icon="Pisz.png", checkable=True)
        self.tool_group = QActionGroup(self)
        self.tool_group.setExclusive(True)
        for action in (self.select_action, self.wire_action, self.delete_action, self.comment_action):
            self.tool_group.addAction(action)
        self.select_action.setChecked(True)
        self.undo_action = self._action("Undo", "Cofnij", self.undo, QKeySequence.StandardKey.Undo, "Cofnij.png")
        self.redo_action = self._action("Redo", "Ponów", self.redo, icon="Ponów.png")
        self.redo_action.setShortcuts([QKeySequence("Ctrl+Y"), QKeySequence("Ctrl+Shift+Z")])
        self.properties_action = self._action("Component properties…", "Właściwości elementu…", self.edit_selected_properties)
        self.properties_action.setEnabled(False)
        self.custom_action = self._action("Create custom component…", "Utwórz customowy element…", self.create_custom_component, icon="Customowe Elementy.png")
        self.settings_action = self._action("Settings…", "Ustawienia…", lambda: self.show_settings())
        self.code_action = self._action("Open code in external editor…", "Otwórz kod w zewnętrznym edytorze…", self.open_code)
        self.document_action = self._action("Drawing information…", "Dane tabliczki rysunkowej…", self.edit_document_info)
        self.exit_action = self._action("Exit", "Zakończ", self.close)
        self.library_actions = []
        for index, (en, pl, icon, _) in enumerate(LIBRARY_GROUPS):
            letter = "ESICM"[index]
            self.library_actions.append(self._action(
                en + f" (Ctrl+A, {letter})", pl + f" (Ctrl+A, {letter})",
                lambda checked=False, i=index: self.open_library(i), icon=icon))

    def _create_menu(self):
        self.menuBar().clear()
        file_menu = self.menuBar().addMenu(self.t("File", "Plik"))
        file_menu.addActions([self.new_action, self.open_action, self.save_action, self.save_as_action])
        file_menu.addSeparator()
        export_menu = file_menu.addMenu(self.t("Export…", "Eksportuj…"))
        export_menu.addActions([self.export_pdf_action, self.export_png_action, self.export_svg_action])
        file_menu.addSeparator()
        file_menu.addAction(self.document_action)
        file_menu.addAction(self.exit_action)
        edit_menu = self.menuBar().addMenu(self.t("Edit", "Edycja"))
        edit_menu.addActions(self.clipboard_actions)
        tools_menu = self.menuBar().addMenu(self.t("Tools", "Narzędzia"))
        tools_menu.addActions([self.select_action, self.wire_action, self.delete_action, self.comment_action,
                               self.undo_action, self.redo_action, self.fit_page_action])
        tools_menu.addSeparator()
        tools_menu.addActions([self.properties_action, self.custom_action, self.add_sheet_action, self.code_action])
        library = tools_menu.addMenu(self.t("Add component", "Dodaj element"))
        library.addActions(self.library_actions)
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
        self.toolbar.addActions([self.select_action, self.wire_action, self.delete_action, self.comment_action])
        self.toolbar.addSeparator()
        self.toolbar.addActions([self.undo_action, self.redo_action])
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.fit_page_action)
        self.addToolBar(Qt.ToolBarArea.RightToolBarArea, self.toolbar)

    def _translate_ui(self):
        install_ui_language(self.settings.language)
        for action, (en, pl) in self._action_labels.items():
            action.setText(self.t(en, pl))
            action.setToolTip(self.t(en, pl))
        self.ai_action.setVisible(AI_AVAILABLE)
        self.datasheet_action.setVisible(AI_AVAILABLE)
        self.ai_action.setEnabled(AI_AVAILABLE and bool(self.settings.api_key))
        if not self.settings.api_key and self.ai_panel is not None:
            self.ai_panel.cancel()
            self.ai_dock.hide()
        self.datasheet_action.setEnabled(AI_AVAILABLE and bool(self.settings.api_key))
        if not self.settings.api_key:
            self.ai_action.setToolTip(self.t("Add a Gemini API key in Settings to enable AI.",
                                             "Podaj klucz API Gemini w ustawieniach, aby włączyć AI."))
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
        view.on_selection = self._selection_changed
        view.on_edit_properties = self.show_component_properties
        view.load_sheet(sheet)
        view.set_tool(self._active_tool)
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
        entries = [item for item in AVAILABLE_ITEMS if item.category in categories]
        if index == 3:
            entries = [get_definition(entry["id"], self.project.custom_components)
                       for entry in self.project.custom_components]
            entries = [item for item in entries if item is not None]
        if not entries:
            menu.addAction(self.t("[NONE]", "[BRAK]")).setEnabled(False)
        submenus = {}
        for item in entries:
            if index == 3:
                target = menu.addMenu(item_name(item, self.settings.language))
                target.addAction(self.t("Edit definition…", "Edytuj definicję…"),
                                 lambda checked=False, identity=item.id: self.edit_custom_component(identity))
                target.addAction(self.t("Delete from library…", "Usuń z biblioteki…"),
                                 lambda checked=False, identity=item.id: self.delete_custom_component(identity))
                target.addSeparator()
            else:
                group = subgroup(item)
                if group not in submenus:
                    submenus[group] = menu.addMenu(self.t(*group))
                target = submenus[group]
            action = target.addAction(self.t("Place on sheet", "Umieść na arkuszu") if index == 3 else item_name(item, self.settings.language))
            action.setData(item.id)
            action.setToolTip(item.variant)
            # Pozycja jest przechwycona przed otwarciem menu. Przejście przez
            # podkategorie nie przesuwa miejsca wstawienia elementu.
            action.triggered.connect(lambda checked=False, identity=item.id, pos=menu_pos: self.add_component_from_id(identity, global_pos=pos))
        if index == 3:
            menu.addSeparator()
            menu.addAction(self.custom_action)

    def add_component_from_id(self, library_id, name=None, global_pos=None):
        try:
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
        self.project = Project(name=dialog.name.text().strip() or self.t("New project", "Nowy projekt"),
                               sheets=[Sheet(name=self.t("Sheet 1", "Arkusz 1"),
                                             paper_size=dialog.paper.currentText(),
                                             orientation=dialog.orientation.currentData(), standard=self.settings.standard)])
        self.current_file = None
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
        self.current_file = Path(filename)
        self._rebuild_tabs(selected=0)
        self._reset_history()
        notice = self.project.metadata.get("migration_notice")
        if notice:
            QMessageBox.warning(self, self.t("Check migrated connections", "Sprawdź migrowane połączenia"), notice)

    def _write_project(self, destination):
        self._sync_positions()
        try:
            save_project(destination, self.project)
        except (OSError, ValueError, TypeError) as error:
            self._error(str(error))
            return False
        # Ścieżkę i stan zapisany zmieniamy dopiero po udanym atomowym zapisie.
        self.current_file = Path(destination).with_suffix(".els")
        self._saved_state = deepcopy(self.project.to_dict())
        self._refresh_title()
        self.statusBar().showMessage(self.t("Project saved.", "Projekt zapisany."), 2500)
        return True

    def save_project(self):
        return self.save_project_as() if self.current_file is None else self._write_project(self.current_file)

    def save_project_as(self):
        filename, _ = QFileDialog.getSaveFileName(self, self.t("Save project", "Zapisz projekt"),
                                                  str(Path(file_dialog_directory(self.settings)) / (self.current_file.name if self.current_file else "project.els")), "ElectroSchem (*.els)")
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
            if self.ai_panel:
                self.ai_panel.cancel()
            event.accept()
        else:
            event.ignore()

    def set_active_tool(self, tool):
        self._active_tool = tool
        self._current_view().set_tool(tool)
        labels = {
            "select": ("Select / move; double-click for properties.", "Zaznacz / przesuń; dwuklik otwiera właściwości."),
            "wire": ("Click pins to connect. Right-click cancels drawing.", "Klikaj piny, aby połączyć. PPM anuluje rysowanie."),
            "delete": ("Click an item to remove it. Delete removes the selection.", "Kliknij obiekt do usunięcia. Del usuwa zaznaczenie."),
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
        definition = get_definition(component.library_id, self.project.custom_components)
        dialog = ComponentPropertiesDialog(component, definition, self.settings.language, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dict(dialog.values)
        extra_key = values.pop("extra_key", "")
        extra_value = values.pop("extra_value", "")
        extra_show = values.pop("extra_show", False)
        for key, value in values.items():
            setattr(component, key, value)
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
        QMessageBox.critical(self, self.t("ElectroSchem — error", "ElectroSchem — błąd"), message)

    def export_pdf(self):
        self._export("pdf")

    def _export(self, kind):
        self._sync_positions()
        from app.services.export import export_pdf, export_png, export_svg
        filename, _ = QFileDialog.getSaveFileName(self, self.t("Export drawing", "Eksportuj schemat"),
                                                  str(Path(file_dialog_directory(self.settings)) / ("schematic." + kind)), f"{kind.upper()} (*.{kind})")
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

    def edit_custom_component(self, library_id):
        from app.core.custom_library import replace_custom
        definition = next((entry for entry in self.project.custom_components if entry["id"] == library_id), None)
        if definition is None:
            return
        dialog = CustomComponentDialog(self.settings.language, self, definition=definition)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.definition:
            return
        self._sync_positions()
        replace_custom(self.project, dialog.definition)
        self._rebuild_tabs()
        self.record_history()

    def delete_custom_component(self, library_id):
        from app.core.custom_library import remove_custom
        definition = next((entry for entry in self.project.custom_components if entry["id"] == library_id), None)
        if definition is None:
            return
        count = sum(component.library_id == library_id for sheet in self.project.sheets for component in sheet.components)
        message = self.t(
            f'Delete "{definition["name"]}" from the library and its {count} instances on all sheets? Wires remain with disconnected ends. Ctrl+Z restores the deletion.',
            f'Usunąć „{definition["name"]}” z biblioteki i wszystkie jego kopie ({count}) na arkuszach? Przewody pozostaną z odłączonymi końcami. Ctrl+Z przywraca usunięcie.')
        if QMessageBox.question(self, self.t("Delete custom component", "Usuń własny element"), message,
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        self._sync_positions()
        remove_custom(self.project, library_id)
        self._rebuild_tabs()
        self.record_history()

    def _ai_context(self):
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

    def open_code(self):
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
        if standard not in {"EN", "PN", "ISO"} or not self.project.sheets:
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
        text = self.t(
            "Shortcuts:\nS — select, D — draw wire, Del — delete, Ctrl+Z/Y — undo/redo, Ctrl+S — save, Ctrl+Shift+S — save as, Ctrl+N/O — new/open project, Ctrl+A then E/S/I/C/M — add a component category, Shift+A then S — add sheet, R — rotate selected component.\n\nElements and wires are restricted to the drawing area; comments may be placed in margins.",
            "Skróty:\nS — zaznaczanie, D — przewód, Del — usuń, Ctrl+Z/Y — cofnij/ponów, Ctrl+S — zapisz, Ctrl+Shift+S — zapisz jako, Ctrl+N/O — nowy/otwórz projekt, Ctrl+A potem E/S/I/C/M — dodaj kategorię elementu, Shift+A potem S — dodaj arkusz, R — obrót zaznaczonego elementu.\n\nElementy i przewody są ograniczone do obszaru rysowania; komentarze można umieszczać także na marginesach.")
        text += self.t("\n\nCtrl+A, A — add anything (all categories).", "\n\nCtrl+A, A — dodaj cokolwiek (wszystkie kategorie).")
        text += self.t("\nH — information about the selected component.", "\nH — informacje o zaznaczonym elemencie.")
        text += self.t("\nCtrl+D — duplicate; Ctrl+X/C/V — cut/copy/paste the selection. Paste at the cursor; duplicates are offset by one grid square. Drag a selected object to move the whole group including free wire nodes.",
                       "\nCtrl+D — duplikuj; Ctrl+X/C/V — wytnij/kopiuj/wklej zaznaczenie. Wklejanie przy kursorze; duplikat jest przesunięty o kratkę. Przeciągnij zaznaczony obiekt, aby przesunąć całą grupę wraz z wolnymi węzłami kabli.")
        text += self.t(
            "\n\nMouse: left-click selects an object; hold the middle button to pan; drag the right button to select a rectangle. Right-click cancels a wire in progress. Double-click the project title, sheet name or author in the drawing table to edit it directly. Enter confirms; Shift+Enter adds a line. Double-click a bottom sheet tab to rename or delete it; Ctrl+Z restores a deleted sheet.",
            "\n\nMysz: LPM wybiera obiekt; wciśnięte kółko przesuwa widok; przeciągnięcie PPM zaznacza prostokątem. PPM anuluje rysowany kabel. Dwuklik nazwy projektu, arkusza lub autora w tabliczce uruchamia edycję na arkuszu. Enter zatwierdza, Shift+Enter dodaje linię. Dwuklik dolnej zakładki pozwala zmienić nazwę lub usunąć arkusz; Ctrl+Z przywraca usunięty arkusz.")
        QMessageBox.information(self, self.t("Help", "Pomoc"), text)
