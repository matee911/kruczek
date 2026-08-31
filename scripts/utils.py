#!/usr/bin/env python3
"""utils.py — wspólne narzędzia dla skryptów kruczka."""

import hashlib
import os


def sha256_file(path: str | os.PathLike[str]) -> str:
    """SHA-256 pliku — czyta w blokach 64 KB, nie wczytuje całości do pamięci."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def human_size(n: float) -> str:
    """Rozmiar w bajtach → czytelny string.

    >>> human_size(0)
    '0 B'
    >>> human_size(512)
    '512 B'
    >>> human_size(1023)
    '1023 B'
    >>> human_size(1024)
    '1.0 KB'
    >>> human_size(1536)
    '1.5 KB'
    >>> human_size(1024 * 1024)
    '1.0 MB'
    >>> human_size(1024 * 1024 * 1024)
    '1.0 GB'
    >>> human_size(1024 * 1024 * 1024 * 5)
    '5.0 GB'
    """
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024
