import unittest
from PySide6.QtWidgets import QApplication
from app.ui.local_ai_guide import LocalAIGuide, guide_html
from app.ui.manual_dialog import ManualDialog
from app.ui.settings_dialog import SettingsDialog
from app.core.settings import AppSettings

APP = QApplication.instance() or QApplication([])


class LocalGuideTests(unittest.TestCase):
    def test_bilingual_offline_content(self):
        for language, title in [('pl', 'Ile parametrów potrzeba?'), ('en', 'How large a model?')]:
            html = guide_html(language)
            for term in (title, '11434/v1', '1234/v1', 'ollama pull', '7-8B', '14B', '32B', 'fine-tuning'):
                self.assertIn(term, html)
            dialog = LocalAIGuide(language)
            self.assertIn(title, dialog.browser.toPlainText())
            self.assertTrue(dialog.browser.openExternalLinks())
            dialog.close()

    def test_guide_available_in_settings_and_manual(self):
        dialog = SettingsDialog(AppSettings(language='pl', ai_provider='none'))
        dialog.show(); APP.processEvents()
        self.assertFalse(dialog.local_tutorial.isHidden())
        self.assertIn('Tutorial', dialog.local_tutorial.text())
        dialog.language.setCurrentIndex(dialog.language.findData('en'))
        self.assertIn('tutorial', dialog.local_tutorial.text())
        manual = ManualDialog('pl')
        self.assertIn('Ile parametrów potrzeba?', manual.browser.toPlainText())
        manual.close(); dialog.close()
