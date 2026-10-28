"""Installation tests never start Codex or read any real profile."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('installer', ROOT/'install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class Installation(unittest.TestCase):
    def test_install_update_preserve_uninstall(self):
        with tempfile.TemporaryDirectory(prefix='plugin folder ') as temporary:
            folder = Path(temporary).resolve()
            other = folder/'other.1m.sh'
            other.write_text('untouched')
            with patch.object(sys, 'argv', ['install.py', '--plugin-dir', str(folder), '--codex-home', '/selected personal home']):
                installer.main()
            self.assertEqual(other.read_text(), 'untouched')
            self.assertTrue((folder/'.codex-pacman/main.py').exists())
            self.assertTrue(os.access(folder/'codex-pacman.sh', os.X_OK))
            settings = folder/'codex-pacman.vars.json'
            values = json.loads(settings.read_text())
            self.assertEqual(values['VAR_CODEX_HOME'], '/selected personal home')
            with patch.object(sys, 'argv', ['install.py', '--plugin-dir', str(folder)]), self.assertRaises(SystemExit):
                installer.main()
            values['VAR_ENABLE_ANIMATION'] = 'false'
            settings.write_text(json.dumps(values))
            with patch.object(sys, 'argv', ['install.py', '--plugin-dir', str(folder), '--update']):
                installer.main()
            self.assertEqual(json.loads(settings.read_text()), values)
            fake_home = folder/'user home'
            identity = hashlib.sha256(str(folder/'codex-pacman.sh').encode()).hexdigest()[:24]
            state = fake_home/'Library/Application Support/Codex Pac-Man'/identity/'environment'
            state.mkdir(parents=True)
            (state/'state.json').write_text('{}')
            with patch.object(Path, 'home', return_value=fake_home), patch.object(sys, 'argv', ['install.py', '--plugin-dir', str(folder), '--uninstall']):
                installer.main()
            self.assertTrue(other.exists())
            self.assertFalse(settings.exists())
            self.assertFalse((folder/'codex-pacman.sh').exists())
            self.assertFalse((folder/'.codex-pacman').exists())
            self.assertFalse(state.exists())

    def test_launcher_missing_home_never_falls_back(self):
        env = dict(os.environ, VAR_CODEX_HOME='/nonexistent selected codex home', CODEX_HOME='/another home')
        result = subprocess.run([str(ROOT/'plugin/codex-pacman.sh'), '--once'], env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertIn('no fallback was attempted', result.stdout)
        self.assertIn('~~~', result.stdout)
        self.assertEqual(result.stderr, '')


class HomebrewInstallation(unittest.TestCase):
    def test_cli_version_and_help(self):
        for args, expected in [(['--version'], 'Codex Pac-Man ' + (ROOT/'VERSION').read_text().strip()), (['install', '--help'], '--plugin-dir'), (['uninstall', '--help'], '--uninstall')]:
            result = subprocess.run([sys.executable, '-B', str(ROOT/'cli.py'), *args], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(expected, result.stdout)

    def test_link_migration_preserves_settings_and_code(self):
        with tempfile.TemporaryDirectory(prefix='linked plugin ') as temporary:
            folder = Path(temporary).resolve()
            (folder/'other.1m.sh').write_text('untouched')
            installer.main(['--plugin-dir', str(folder), '--codex-home', '/selected home'])
            settings = folder/'codex-pacman.vars.json'
            before = settings.read_bytes()
            installer.main(['--link', '--update', '--plugin-dir', str(folder)])
            entry, modules = folder/'codex-pacman.sh', folder/'.codex-pacman'
            self.assertTrue(entry.is_symlink())
            self.assertTrue(modules.is_symlink())
            self.assertEqual(entry.read_bytes(), (ROOT/'plugin/codex-pacman.sh').read_bytes())
            self.assertEqual(settings.read_bytes(), before)
            installer.main(['--link', '--update', '--plugin-dir', str(folder)])
            with patch.object(Path, 'home', return_value=folder/'user home'):
                installer.main(['--uninstall', '--plugin-dir', str(folder)])
            self.assertFalse(entry.is_symlink())
            self.assertFalse(modules.is_symlink())
            self.assertTrue((ROOT/'plugin/.codex-pacman/main.py').exists())
            self.assertEqual((folder/'other.1m.sh').read_text(), 'untouched')

    def test_stable_opt_link_follows_upgrade(self):
        import shutil
        with tempfile.TemporaryDirectory(prefix='brew opt ') as temporary:
            root = Path(temporary).resolve()
            first, second, stable, plugins = [root/name for name in ('1.0.1', '1.0.2', 'opt', 'SwiftBar Plugins')]
            for keg in (first, second):
                keg.mkdir()
                for name in ('install.py', 'cli.py', 'VERSION'):
                    shutil.copyfile(ROOT/name, keg/name)
                shutil.copytree(ROOT/'plugin', keg/'plugin')
            stable.symlink_to(first, target_is_directory=True)
            plugins.mkdir()
            subprocess.run([sys.executable, '-B', str(stable/'cli.py'), 'install', '--plugin-dir', str(plugins)], check=True, capture_output=True)
            entry = plugins/'codex-pacman.sh'
            self.assertEqual(os.readlink(entry), str(stable/'plugin/codex-pacman.sh'))
            stable.unlink()
            stable.symlink_to(second, target_is_directory=True)
            self.assertEqual(entry.resolve(), second/'plugin/codex-pacman.sh')
            self.assertEqual((plugins/'.codex-pacman').resolve(), second/'plugin/.codex-pacman')

    def test_failed_link_swap_restores_copied_modules(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, destination = root/'source', root/'destination'
            source.mkdir(); destination.mkdir()
            (destination/'keep.py').write_text('previous code')
            with patch.object(installer.os, 'replace', side_effect=OSError('simulated swap failure')):
                with self.assertRaises(OSError):
                    installer.link_modules(source, destination)
            self.assertEqual((destination/'keep.py').read_text(), 'previous code')
            self.assertFalse(list(root.glob('.codex-pacman-*')))


if __name__ == '__main__':
    unittest.main()
