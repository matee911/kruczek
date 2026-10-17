#!/usr/bin/env bash
# Repo jest publiczne. Dokument z „nie commitować” w treści to notatka robocza z danymi spraw.
# Wspólne dla haka pre-commit i CI (CI łapie commity z --no-verify i z klonów bez włączonych haków).
#
# Sprawdzamy indeks: w haku to dokładnie to, co trafi do commita, w CI — sprawdzany commit.
# Ten skrypt i test haka same zawierają znacznik, więc są wyłączone.
set -euo pipefail

RC=0
ZAKAZANE=$(git grep --cached -l -i -E 'nie commitowa|do not commit' -- . \
  ':!.githooks/sprawdz-znacznik.sh' ':!tests/test_hook_pre_commit.py') || RC=$?

if [ "$RC" -eq 0 ]; then
  echo "✗ Pliki oznaczone „nie commitować” — nie mogą trafić do repo:"
  echo "${ZAKAZANE}" | sed 's/^/    /'
  echo "Wyjmij je z indeksu: git restore --staged <plik> (miejsce na notatki robocze: .superpowers/)"
  exit 1
elif [ "$RC" -ne 1 ]; then
  # git grep: 1 = brak trafień, każdy inny kod to błąd — wtedy blokada ma się zamknąć, nie otworzyć.
  echo "✗ Blokada „nie commitować”: nie udało się sprawdzić indeksu (git grep: ${RC})."
  exit 1
fi
