"""Keep the official source release free of uploads, caches, and developer files."""
from pathlib import Path
from scripts.make_release import build, verify


def test_release_archive_round_trip(tmp_path):
    path = tmp_path / 'release.zip'
    count = build(path)
    assert count >= 25
    assert verify(path)
    from zipfile import ZipFile
    with ZipFile(path) as z:
        names = z.namelist()
    assert not any('__pycache__' in name or '.venv' in name or name.endswith('.log') for name in names)
    assert any(name.endswith('/start-mac.command') for name in names)
    assert any(name.endswith('/PRIVACY_AND_LICENSE.md') for name in names)
