"""Package a clean V1.0 source ZIP with a SHA-256 integrity inventory.

Only project source, documentation, test fixtures and scripts are shipped.
No end-user documents, caches, history or virtualenvs are copied.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import zipfile
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from filedesk.version import VERSION

ALLOWED_ROOT_FILES = {
    'README.md', 'QUICKSTART_MAC.md', 'RELEASE_NOTES.md', 'QA_MATRIX.md',
    'PRIVACY_AND_LICENSE.md', 'RELEASE_CHECKLIST.md', 'requirements.txt',
    'main.py', '.gitignore', 'start-mac.command', 'doctor-mac.command',
}
ALLOWED_FOLDERS = ('filedesk/', 'web/', 'tests/', 'scripts/', 'docs/')
SKIP_NAMES = {'__pycache__', '.pytest_cache', '.venv', 'dist', 'build', '.DS_Store'}
SKIP_EXTENSIONS = {'.pyc', '.pyo', '.log', '.zip', '.dmg', '.app'}


def release_files():
    for path in sorted(ROOT.rglob('*')):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        if any(part in SKIP_NAMES or part.startswith('.filedesk-') for part in path.relative_to(ROOT).parts):
            continue
        if path.suffix.lower() in SKIP_EXTENSIONS:
            continue
        if rel not in ALLOWED_ROOT_FILES and not rel.startswith(ALLOWED_FOLDERS):
            continue
        if rel.startswith('tests/') and '/fixtures/' in rel:
            # Only synthetic fixtures kept under tests/fixtures, no real uploads.
            pass
        yield path, rel


def build(destination: Path):
    files = list(release_files())
    inventory = []
    for file, rel in files:
        inventory.append(f'{hashlib.sha256(file.read_bytes()).hexdigest()}  {rel}')
    content = '\n'.join(inventory) + '\n'
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        prefix = f'FileDesk-v{VERSION}/'
        for file, rel in files:
            output.write(file, prefix + rel)
        output.writestr(prefix + 'SHA256SUMS.txt', content)
    return len(files)


def verify(destination: Path):
    prefix = f'FileDesk-v{VERSION}/'
    with zipfile.ZipFile(destination) as archive:
        entries = set(archive.namelist())
        manifest = archive.read(prefix + 'SHA256SUMS.txt').decode('utf-8')
        for line in manifest.splitlines():
            checksum, rel = line.split('  ', 1)
            assert hashlib.sha256(archive.read(prefix + rel)).hexdigest() == checksum, rel
        assert len(entries) == len(manifest.splitlines()) + 1
        assert all(name.startswith(prefix) and '..' not in Path(name).parts for name in entries)
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path,
                        default=ROOT.parent / f'文序-FileDesk-V{VERSION}-正式版完整项目.zip')
    args = parser.parse_args()
    count = build(args.out)
    verify(args.out)
    print(f'V{VERSION}: {count} source files checked and packaged: {args.out}')
