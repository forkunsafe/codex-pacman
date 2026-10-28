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
import uuid

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


def link_modules(source, destination):
    """Replace only installed code, restoring a copied directory if linking fails."""
    temporary = destination.with_name('.codex-pacman-link-' + uuid.uuid4().hex)
    backup = destination.with_name('.codex-pacman-backup-' + uuid.uuid4().hex)
    temporary.symlink_to(source, target_is_directory=True)
    moved = False
    try:
        if destination.is_dir() and not destination.is_symlink():
            destination.rename(backup)
            moved = True
        os.replace(temporary, destination)
    except BaseException:
        if moved:
            backup.rename(destination)
        raise
    finally:
        temporary.unlink(missing_ok=True)
    if moved:
        shutil.rmtree(backup)


def main(argv=None, source=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plugin-dir', help='SwiftBar Plugin Folder; discovered from SwiftBar preferences by default')
    parser.add_argument('--codex-home', help='Set native Codex Home setting without reading account data')
    parser.add_argument('--update', action='store_true', help='Replace existing code, preserving native settings; stop this plugin first')
    parser.add_argument('--uninstall', action='store_true', help='Remove this plugin, its native settings, and its private local state')
    parser.add_argument('--link', action='store_true', help='Link code from this installation instead of copying; used by the Homebrew command')
    args = parser.parse_args(argv)
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
    if (entry.exists() or entry.is_symlink() or modules.exists() or modules.is_symlink()) and not args.update:
        raise SystemExit('Codex Pac-Man is already installed. Stop only this plugin and use --update.')
    values = None
    if args.codex_home is not None:
        home = Path(args.codex_home).expanduser()
        if not home.is_absolute():
            raise SystemExit('--codex-home must be absolute or begin with ~.')
        values = json.loads(settings.read_text()) if settings.exists() else {}
        values['VAR_CODEX_HOME'] = str(home)
    # Preserve the Homebrew opt path so upgrades do not pin links to an old keg.
    source = Path(source) if source is not None else (Path(__file__).absolute() if args.link else Path(__file__).resolve()).parent/'plugin'
    if not (source/NAME).is_file() or not (source/MODULES/'main.py').is_file():
        raise SystemExit('Plugin source files are missing. Reinstall Codex Pac-Man.')
    # Modules first; the launcher is the commit point recognized by SwiftBar.
    if args.link:
        link_modules(source/MODULES, modules)
    else:
        if modules.is_symlink():
            raise SystemExit('This installation uses Homebrew links. Use codex-pacman install --update, or uninstall before switching to copied files.')
        shutil.copytree(source/MODULES, modules, dirs_exist_ok=args.update, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    if values is not None:
        temporary = settings.with_suffix('.tmp')
        temporary.write_text(json.dumps(values) + '\n')
        temporary.chmod(0o600)
        os.replace(temporary, settings)
    temporary = directory/'.codex-pacman-launcher.tmp'
    temporary.unlink(missing_ok=True)
    if args.link:
        temporary.symlink_to(source/NAME)
    else:
        shutil.copyfile(source/NAME, temporary)
        temporary.chmod(0o755)
    os.replace(temporary, entry)
    print('Installed Codex Pac-Man. SwiftBar will discover it automatically.')
    print('Configure the three native variables under SwiftBar Settings → Plugins.')


if __name__ == '__main__':
    main()
