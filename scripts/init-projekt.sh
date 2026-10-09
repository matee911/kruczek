#!/usr/bin/env bash
# init-projekt.sh — zakłada strukturę repozytorium spraw kruczka.
#   init-projekt.sh [KATALOG]      (domyślnie bieżący)
set -euo pipefail

# Sprawdź zależności przed czymkolwiek innym
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$SCRIPT_DIR/check-deps.sh" || exit 1

ROOT="${1:-.}"
mkdir -p "$ROOT"/BAZA_WIEDZY/{przepisy,orzecznictwo,decyzje,wzory,metodyka}
mkdir -p "$ROOT"/_SZABLONY

[ -f "$ROOT/BAZA_WIEDZY/index.md" ] || cat > "$ROOT/BAZA_WIEDZY/index.md" <<'EOF'
# BAZA WIEDZY

Przepisy, orzecznictwo i metodyka wielokrotnego użytku. **Zanim zaczniesz szukać w internecie —
sprawdź, czy odpowiedź już tu jest.**

## Zasady
- Cytaty **dosłowne**, wyłącznie ze źródeł urzędowych (API ELI Sejmu / ISAP, EUR-Lex, portale orzeczeń organów).
- Każdy plik ma na górze: akt, publikator (Dz.U.), URL źródła, datę weryfikacji.
- Pozycje niepotwierdzone oznaczaj `⚠ NIEPOTWIERDZONE` — **nie wolno ich cytować w pismach**.
- Przy każdym przepisie notuj, czy i kiedy został **uchylony lub znowelizowany**.
- Nowa sprawa = najpierw sprawdź bazę, dopiero potem research.

## Spis
| Plik | Zakres |
|---|---|
| _(pusto — dopisuj przy każdym researchu)_ | |
EOF

[ -f "$ROOT/index.md" ] || cat > "$ROOT/index.md" <<'EOF'
# Rejestr spraw

## Struktura
```
.
├── index.md            ← ten plik: rejestr wszystkich spraw
├── BAZA_WIEDZY/        ← przepisy, orzecznictwo, metodyka (wspólne)
├── _SZABLONY/          ← wzory pism i plików
└── <PODMIOT>/          ← jeden katalog na drugą stronę
    ├── index.md        ← chronologia (generowana), ustalenia, eskalacja
    ├── sprawa.json     ← dane sprawy: zdarzenia, terminy, zadania (zapisuje teczka.py)
    ├── ARCHIWUM/       ← oryginały dowodów — TYLKO DOPISYWANIE, nigdy edycja
    ├── ROBOCZE/        ← notatki, wersje, materiały pomocnicze
    └── <YYYY_MM_DD>-<CO>-<DO_KOGO>-DO_WYSYLKI/
        ├── ROBOCZE/    ← szablon pisma + instrukcja regeneracji
        ├── *.pdf       ← pismo gotowe do druku (z wdrukowanymi załącznikami)
        └── dowody.zip  ← dowody cyfrowe + SHA256SUMS.txt
```

## Sprawy
| # | Podmiot | Przedmiot | Założono |
|---|---|---|---|

Status, terminy i zadania wszystkich spraw: `/kruczek:status` (liczone z `sprawa.json`).
EOF

TEMPLATES="$(dirname "$SCRIPT_DIR")/templates"
[ -f "$ROOT/KONWENCJE.md" ] || cp "$TEMPLATES/KONWENCJE.md" "$ROOT/KONWENCJE.md"

# Pliki robocze teczki (blokada zapisu, pliki tymczasowe) nie trafiają do gita spraw.
touch "$ROOT/.gitignore"
# Plik bez końcowej nowej linii: dopisz ją, żeby nie skleić wzorca z ostatnią linią.
[ ! -s "$ROOT/.gitignore" ] || [ -z "$(tail -c1 "$ROOT/.gitignore")" ] || echo >> "$ROOT/.gitignore"
for wzor in '.sprawa.lock' '.*.tmp'; do
  grep -qxF "$wzor" "$ROOT/.gitignore" || printf '%s\n' "$wzor" >> "$ROOT/.gitignore"
done
[ -f "$ROOT/_SZABLONY/dane-nadawcy.md" ] || \
  cp "$(dirname "$SCRIPT_DIR")/templates/dane-nadawcy.md" "$ROOT/_SZABLONY/dane-nadawcy.md"

# CLAUDE.md generujemy zawsze (nadpisujemy) — zawiera dane nadawcy i nawigację
bash "$SCRIPT_DIR/gen-claude-md.sh" "$ROOT"

echo "Struktura założona w: $(cd "$ROOT" && pwd)"
find "$ROOT" -maxdepth 2 -not -path '*/.*' | sort
