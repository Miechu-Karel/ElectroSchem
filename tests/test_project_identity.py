"""Project identities survive editing and prevent accidental source reuse."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import UUID
from app.core.models import Project
from app.core.project_file import load_project, save_project
from app.core.board_code import ensure_source, ensure_code_folder, project_code_id
from test_simulation import component


class ProjectIdentityTests(unittest.TestCase):
    def test_new_projects_with_same_title_have_different_random_ids(self):
        first, second = Project(name='Blink'), Project(name='Blink')
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(UUID(first.id).version, 4)
        self.assertEqual(len(project_code_id(first)), 32)

    def test_rename_and_serialization_preserve_identity(self):
        project = Project(name='Blink')
        identity = project_code_id(project)
        project.name = 'Nowy tytuł'
        restored = Project.from_dict(project.to_dict())
        self.assertEqual(project_code_id(restored), identity)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'saved.els'
            save_project(path, project)
            self.assertEqual(load_project(path).id, project.id)

    def test_legacy_documents_migrate_stably_independent_of_title(self):
        first, second = Project(name='Blink').to_dict(), Project(name='Blink').to_dict()
        first.pop('id'); second.pop('id')
        migrated = Project.from_dict(first)
        self.assertEqual(Project.from_dict(first).id, migrated.id)
        self.assertNotEqual(Project.from_dict(second).id, migrated.id)
        first['name'] = 'Renamed legacy project'
        self.assertEqual(Project.from_dict(first).id, migrated.id)
        self.assertEqual(Project.from_dict(migrated.to_dict()).id, migrated.id)

    def test_invalid_stored_identity_is_rejected(self):
        for identity in ('../other', '', 123, 'not-a-uuid'):
            data = Project().to_dict(); data['id'] = identity
            with self.subTest(identity=identity), self.assertRaisesRegex(ValueError, 'Invalid project ID'):
                Project.from_dict(data)

    def test_same_title_and_component_id_cannot_reuse_other_project_code(self):
        with tempfile.TemporaryDirectory() as directory, patch('app.core.board_code.appdata_directory', return_value=Path(directory)):
            first, second = Project(name='Blink'), Project(name='Blink')
            board = component('Raspberry Pi 5', 100, 100)
            other = deepcopy(board)
            source = ensure_source(board, first)
            self.assertEqual(source.read_bytes(), b'')
            source.write_text('# Only the first project\n', encoding='utf-8')
            second_source = ensure_source(other, second)
            self.assertNotEqual(source, second_source)
            self.assertEqual(second_source.read_bytes(), b'')
            self.assertEqual(source.read_text(), '# Only the first project\n')
            self.assertEqual(ensure_source(board, first), source)

    def test_unassigned_old_code_is_not_imported_into_new_project(self):
        with tempfile.TemporaryDirectory() as directory, patch('app.core.board_code.appdata_directory', return_value=Path(directory)):
            board = component('Raspberry Pi 5', 100, 100)
            root = Path(directory) / 'code'; root.mkdir()
            old = root / (sha256(board.id.encode()).hexdigest()[:24] + '.py')
            old.write_text('# Code from a different document\n', encoding='utf-8')
            source = ensure_source(board, Project())
            self.assertEqual(source.read_bytes(), b'')
            self.assertTrue(old.read_text().startswith('# Code from'))

    def test_legacy_linked_folder_and_helper_are_not_moved_or_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source, helper = folder / 'old_hash_code.py', folder / 'helper.py'
            source.write_text('import helper\n', encoding='utf-8')
            helper.write_text('value=42\n', encoding='utf-8')
            board = component('Raspberry Pi 5', 100, 100)
            board.properties.update(sim_source=str(source), sim_code_folder=str(folder))
            project = Project(name='Blink')
            self.assertEqual(ensure_source(board, project), source)
            self.assertEqual(ensure_code_folder(board, project), folder)
            self.assertEqual(source.read_text(), 'import helper\n')
            self.assertEqual(helper.read_text(), 'value=42\n')

    def test_new_python_folder_has_an_empty_entry_point(self):
        with tempfile.TemporaryDirectory() as directory, patch('app.core.board_code.appdata_directory', return_value=Path(directory)):
            board = component('Raspberry Pi 5', 100, 100)
            folder = ensure_code_folder(board, Project())
            self.assertEqual(Path(board.properties['sim_source']).read_bytes(), b'')
            self.assertTrue((folder / 'README.md').is_file())
