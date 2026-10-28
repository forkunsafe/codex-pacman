#!/usr/bin/env python3
"""Build a source distribution using an explicit allowlist; no local settings/state."""
from pathlib import Path
import tarfile

root = Path(__file__).resolve().parents[1]
destination = root/'dist'
destination.mkdir(exist_ok=True)
output = destination/'codex-pacman-1.0.0.tar.gz'
allowed = ['README.md', 'LICENSE', '.gitignore', 'install.py', 'plugin', 'tests', 'docs', 'tools', '.github']


def filter_member(member):
    parts = Path(member.name).parts
    if '__pycache__' in parts or member.name.endswith(('.pyc', '.vars.json', '.log', '.DS_Store')):
        return None
    member.uid = member.gid = 0
    member.uname = member.gname = ''
    member.mtime = 0
    return member


with tarfile.open(output, 'w:gz') as archive:
    for name in allowed:
        archive.add(root/name, arcname='codex-pacman/'+name, filter=filter_member)
print(output.name)
