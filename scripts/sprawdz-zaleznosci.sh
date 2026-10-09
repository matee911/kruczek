#!/usr/bin/env bash
# sprawdz-zaleznosci.sh — hook SessionStart: czy są narzędzia, bez których kruczek nie ruszy.
# Z kompletem milczy. Bez czegoś wypisuje JSON: systemMessage dla użytkownika (komenda
# instalacji) i additionalContext dla Claude. Zawsze exit 0 — sesja ma wystartować.
# Pełna lista (PDF, OCR…) i komendy dla systemu: scripts/check-deps.sh.
set -u

brak=()
for cmd in uv curl jq; do
  command -v "$cmd" >/dev/null 2>&1 || brak+=("$cmd")
done
[ "${#brak[@]}" -eq 0 ] && exit 0

lista="${brak[*]}"
instrukcja=""
for cmd in "${brak[@]}"; do
  case "$cmd" in
    uv) instrukcja="$instrukcja uv: macOS brew install uv, Linux curl -LsSf https://astral.sh/uv/install.sh | sh (skrypty Pythona kruczka startują przez uv)." ;;
    *)  instrukcja="$instrukcja $cmd: macOS brew install $cmd, Linux sudo apt install $cmd." ;;
  esac
done

printf '{"systemMessage":"Kruczek: brakuje %s.%s Potem otwórz nową sesję.","hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"Kruczek: brakuje narzędzi: %s. Skrypty, które ich wymagają, nie ruszą (bez uv: env: uv: No such file or directory). Zanim użyjesz skilli kruczka, poproś użytkownika o instalację:%s"}}\n' \
  "$lista" "$instrukcja" "$lista" "$instrukcja"
