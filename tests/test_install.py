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


if __name__ == '__main__':
    unittest.main()
