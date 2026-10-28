#!/usr/bin/env python3
"""Install/remove only this plugin. No elevated privileges or Codex access."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

NAME = 'codex-pacman.sh'
MODULES = '.codex-pacman'


def plugin_directory(configured):
    if configured:
        return Path(configured).expanduser().absolute()
    try:
        result = subprocess.run(['defaults', 'read', 'com.ameba.SwiftBar', 'PluginDirectory'],
                                check=True, capture_output=True, text=True)
        return Path(result.stdout.strip()).expanduser().absolute()
    except (OSError, subprocess.CalledProcessError):
        raise SystemExit('Cannot find SwiftBar Plugin Folder. Pass --plugin-dir explicitly.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plugin-dir', help='SwiftBar Plugin Folder; discovered from SwiftBar preferences by default')
    parser.add_argument('--codex-home', help='Set native Codex Home setting without reading account data')
    parser.add_argument('--update', action='store_true', help='Replace existing code, preserving native settings; stop this plugin first')
    parser.add_argument('--uninstall', action='store_true', help='Remove this plugin, its native settings, and its private local state')
    args = parser.parse_args()
    directory = plugin_directory(args.plugin_dir)
    if not directory.is_dir():
        raise SystemExit('SwiftBar Plugin Folder does not exist.')
    entry, modules, settings = directory/NAME, directory/MODULES, directory/'codex-pacman.vars.json'
    if args.uninstall:
        # Identity matches SWIFTBAR_PLUGIN_PATH, without reading any Codex home.
        instance = hashlib.sha256(str(entry).encode()).hexdigest()[:24]
        state = Path.home()/'Library'/'Application Support'/'Codex Pac-Man'/instance
        for path in (entry, settings):
            path.unlink(missing_ok=True)
        for path in (modules, state):
            if path.is_symlink(): path.unlink()
            elif path.exists(): shutil.rmtree(path)
        print('Removed Codex Pac-Man and its local state. Codex and other plugins were untouched.')
        return
    if (entry.exists() or modules.exists()) and not args.update:
        raise SystemExit('Codex Pac-Man is already installed. Stop only this plugin and use --update.')
    values = None
    if args.codex_home is not None:
        home = Path(args.codex_home).expanduser()
        if not home.is_absolute():
            raise SystemExit('--codex-home must be absolute or begin with ~.')
        values = json.loads(settings.read_text()) if settings.exists() else {}
        values['VAR_CODEX_HOME'] = str(home)
    source = Path(__file__).resolve().parent/'plugin'
    # Modules first; the launcher is the commit point recognized by SwiftBar.
    shutil.copytree(source/MODULES, modules, dirs_exist_ok=args.update, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    if values is not None:
        temporary = settings.with_suffix('.tmp')
        temporary.write_text(json.dumps(values) + '\n')
        temporary.chmod(0o600)
        os.replace(temporary, settings)
    temporary = directory/'.codex-pacman-launcher.tmp'
    shutil.copyfile(source/NAME, temporary)
    temporary.chmod(0o755)
    os.replace(temporary, entry)
    print('Installed Codex Pac-Man. SwiftBar will discover it automatically.')
    print('Configure the three native variables under SwiftBar Settings → Plugins.')


if __name__ == '__main__':
    main()
