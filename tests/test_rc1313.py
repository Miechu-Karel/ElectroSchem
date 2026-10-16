"""Regression checks for per-instance asset component targets."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from types import SimpleNamespace
from app.core.models import Project,Sheet
from app.core.assets import instantiate
from app.ui.asset_shells import CaseShell
from test_rc1308 import RC8Tests,APP


class RC13AssetTests(unittest.TestCase):
    def test_duplicate_module_instances_resolve_distinct_internal_ids(self):
        editor,_,led,_=RC8Tests.editor(self)
        definition=editor.definition
        project=Project(sheets=[Sheet()],custom_components=[definition])
        first=project.new_component(definition['id'],300,300)
        second=project.new_component(definition['id'],700,300)
        first_contents,_=instantiate(definition['asset'],first)
        second_contents,_=instantiate(definition['asset'],second)
        window=SimpleNamespace(pl=True,custom=[definition])
        first_shell=CaseShell(window,first,first_contents,definition)
        second_shell=CaseShell(window,second,second_contents,definition)
        internal_index=next(i for i,c in enumerate(definition['asset']['sheet']['components']) if c['id']==led.id)
        self.assertEqual(first_shell.targets[led.id],first_contents.components[internal_index].id)
        self.assertEqual(second_shell.targets[led.id],second_contents.components[internal_index].id)
        self.assertNotEqual(first_shell.targets[led.id],second_shell.targets[led.id])
        first_shell.deleteLater(); second_shell.deleteLater(); APP.processEvents()
