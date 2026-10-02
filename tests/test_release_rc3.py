"""Windows taskbar identity without changing the test process's real identity."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from main import WINDOWS_APP_ID, configure_taskbar_identity


class TaskbarTests(unittest.TestCase):
    def test_windows_sets_stable_application_identity(self):
        setter = Mock(return_value=0)
        shell = SimpleNamespace(shell32=SimpleNamespace(SetCurrentProcessExplicitAppUserModelID=setter))
        with patch("main.sys.platform", "win32"), patch("ctypes.windll", shell, create=True):
            self.assertTrue(configure_taskbar_identity())
        setter.assert_called_once_with(WINDOWS_APP_ID)
        self.assertNotIn("rc3", WINDOWS_APP_ID)

    def test_other_platform_does_not_access_windows_api(self):
        with patch("main.sys.platform", "linux"), patch("ctypes.windll", create=True) as shell:
            self.assertFalse(configure_taskbar_identity())
            shell.shell32.SetCurrentProcessExplicitAppUserModelID.assert_not_called()

    def test_unavailable_windows_api_does_not_break_startup(self):
        setter = Mock(side_effect=OSError("unavailable"))
        shell = SimpleNamespace(shell32=SimpleNamespace(SetCurrentProcessExplicitAppUserModelID=setter))
        with patch("main.sys.platform", "win32"), patch("ctypes.windll", shell, create=True):
            self.assertFalse(configure_taskbar_identity())
