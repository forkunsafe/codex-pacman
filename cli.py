#!/usr/bin/env python3
"""Homebrew command for connecting or removing the native SwiftBar plugin."""
import argparse
from pathlib import Path
import sys
import install


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in ('install', 'uninstall'):
        operation = '--link' if args[0] == 'install' else '--uninstall'
        install.main([operation, *args[1:]], source=Path(sys.argv[0]).absolute().parent/'plugin')
        return
    parser = argparse.ArgumentParser(prog='codex-pacman', description=__doc__)
    parser.add_argument('--version', action='version', version='Codex Pac-Man ' + Path(__file__).with_name('VERSION').read_text().strip())
    parser.add_argument('command', choices=('install', 'uninstall'), nargs='?', help='Use COMMAND --help for options.')
    parser.parse_args(args)
    parser.print_help()


if __name__ == '__main__':
    main()
