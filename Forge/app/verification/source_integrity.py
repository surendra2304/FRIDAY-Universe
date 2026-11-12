"""Bounded project-byte inventory, excluding explicitly non-delivery build caches.

This detects persistent source drift; it is not an attestation against hostile
code that edits and restores files during a test, nor a signature of the host.
"""
from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path

MAX_FILES = 2048
MAX_BYTES = 32 * 1024 * 1024
EXCLUDED = frozenset({'.git', '__pycache__', '.pytest_cache', '.ruff_cache',
                      '.mypy_cache', '.cache', '.venv', 'venv', 'env',
                      'node_modules', 'dist', 'build'})


def project_snapshot(project: Path) -> dict:
    """Hash regular project files or raise ValueError/OSError; never follow links."""
    project = Path(project)
    if project.is_symlink() or not project.is_dir():
        raise ValueError('project_unavailable')
    files = {}
    total = 0

    def onerror(error):
        raise error

    for directory, dirs, names in os.walk(project, followlinks=False, onerror=onerror):
        for name in dirs:
            if name not in EXCLUDED and (Path(directory) / name).is_symlink():
                raise ValueError('project_symlink')
        dirs[:] = sorted(name for name in dirs if name not in EXCLUDED)
        for name in sorted(names):
            path = Path(directory) / name
            if name.endswith(('.pyc', '.pyo')):
                continue
            if path.is_symlink() or not path.is_file():
                raise ValueError('non_regular_project_file')
            if len(files) >= MAX_FILES:
                raise ValueError('project_file_limit')
            digest = hashlib.sha256()
            fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
            with os.fdopen(fd, 'rb') as handle:
                # The opened object must still be a regular file, not a FIFO.
                if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                    raise ValueError('non_regular_project_file')
                while chunk := handle.read(65536):
                    total += len(chunk)
                    if total > MAX_BYTES:
                        raise ValueError('project_byte_limit')
                    digest.update(chunk)
            files[path.relative_to(project).as_posix()] = digest.hexdigest()
    if not files:
        raise ValueError('empty_project')
    return {'version': 1, 'files': files}


def snapshot_matches(project: Path, expected: object) -> bool:
    """Unknown legacy/schema, unsafe paths and unavailable files fail closed."""
    if not isinstance(expected, dict) or expected.get('version') != 1:
        return False
    if not isinstance(expected.get('files'), dict) or not expected['files']:
        return False
    try:
        return project_snapshot(project) == expected
    except (OSError, ValueError):
        return False
