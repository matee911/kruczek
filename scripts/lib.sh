#!/usr/bin/env bash
# lib.sh — wspólne funkcje pomocnicze dla skryptów kruczka. Nie uruchamiaj bezpośrednio.
# Użycie: source "$(dirname "$0")/lib.sh"

urlencode() { printf '%s' "$1" | jq -sRr @uri; }

# sha256 <plik> — sama suma, bez nazwy pliku.
# Przenośnie: macOS nie gwarantuje `sha256sum` (ma `shasum`), a minimalne obrazy Linuksa
# bywają bez `shasum` (idzie z perlem). python3 jest i tak wymagany przez check-deps.sh,
# więc stanowi pewne domknięcie.
sha256() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | cut -d' ' -f1
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | cut -d' ' -f1
  else
    python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$1"
  fi
}
