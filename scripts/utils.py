"""utils.py — wspólne narzędzia dla skryptów kruczka."""

import hashlib
import os

PRINT_MAIL_MAX_SIZE_MB = 2
PRINT_MAIL_MAX_SHEETS = 98


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


def parse_unembedded_fonts(pdffonts_output: str) -> list | None:
    """Extract font names NOT marked embedded ('yes') from `pdffonts` output.

    Shared by build_pismo.py (checking a PDF it just built) and kontrola_pisma.py
    (checking a finished one) — both need the exact same column-position parsing,
    which used to be duplicated between them.

    Returns None when the 'emb' column can't be located (empty output, or a
    format pdffonts didn't produce) — that is a distinct "couldn't check" state
    from "checked, and every font is embedded" ([]), and callers must not
    conflate the two. The column position is read from the header row rather
    than assumed at a fixed offset, because it shifts with the widest font name
    in the "type" column (e.g. "CID TrueType" vs "TrueType").

    >>> header = "name".ljust(38) + "type".ljust(18) + "emb"
    >>> sep    = "-" * 56
    >>> embedded     = "Liberation Serif".ljust(38) + "CID TrueType".ljust(18) + "yes"
    >>> not_embedded = "Arial".ljust(38) + "TrueType".ljust(18) + "no "
    >>> parse_unembedded_fonts("\\n".join([header, sep, embedded, not_embedded]))
    ['Arial']
    >>> parse_unembedded_fonts("\\n".join([header, sep, embedded]))
    []
    >>> parse_unembedded_fonts("") is None
    True
    >>> parse_unembedded_fonts("garbage without the expected column\\n") is None
    True
    """
    lines = pdffonts_output.splitlines()
    if not lines or "emb" not in lines[0]:
        return None
    col = lines[0].index("emb")
    return [
        line[:36].strip()
        for line in lines[2:]
        if line.strip() and line[col : col + 3].strip() != "yes"
    ]


def evaluate_print_mail_requirements(
    size_mb: float,
    pages: int | None,
    max_size_mb: float = PRINT_MAIL_MAX_SIZE_MB,
    max_sheets: int = PRINT_MAIL_MAX_SHEETS,
) -> list:
    """Check a PDF's size and physical sheet count against Envelo/PUH limits.

    Shared by build_pismo.py and kontrola_pisma.py — same two checks, same
    thresholds, only the wording and severity of the report differ per caller
    (build_pismo prints OK/UWAGA; kontrola_pisma treats an oversized PDF as a
    warning but too many sheets as a blocking error), which is why this returns
    plain facts instead of formatted messages.

    `pages` may be None when pdfinfo wasn't available — the sheet-count check is
    then skipped entirely (no dict for it in the result, not a failing one),
    since "unknown" and "fails the limit" are different findings for the caller
    to report differently.

    >>> evaluate_print_mail_requirements(1.5, 10)
    [{'check': 'size', 'ok': True, 'size_mb': 1.5, 'max_size_mb': 2}, {'check': 'sheets', 'ok': True, 'pages': 10, 'sheets': 5, 'max_sheets': 98}]
    >>> evaluate_print_mail_requirements(3.0, None)
    [{'check': 'size', 'ok': False, 'size_mb': 3.0, 'max_size_mb': 2}]
    >>> [r['ok'] for r in evaluate_print_mail_requirements(1.0, 200)]
    [True, False]
    >>> evaluate_print_mail_requirements(1.0, 195)[1]['sheets']
    98
    """
    results = [
        {
            "check": "size",
            "ok": size_mb <= max_size_mb,
            "size_mb": size_mb,
            "max_size_mb": max_size_mb,
        }
    ]
    if pages is not None:
        sheets = (pages + 1) // 2
        results.append(
            {
                "check": "sheets",
                "ok": sheets <= max_sheets,
                "pages": pages,
                "sheets": sheets,
                "max_sheets": max_sheets,
            }
        )
    return results


def all_requirements_met(results: list) -> bool:
    """>>> all_requirements_met([{'ok': True}, {'ok': True}])
    True
    >>> all_requirements_met([{'ok': True}, {'ok': False}])
    False
    >>> all_requirements_met([])
    True
    """
    return all(r["ok"] for r in results)
