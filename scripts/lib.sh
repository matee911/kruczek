#!/usr/bin/env bash
# lib.sh — wspólne funkcje pomocnicze dla skryptów kruczka. Nie uruchamiaj bezpośrednio.
# Użycie: source "$(dirname "$0")/lib.sh"

urlencode() { printf '%s' "$1" | jq -sRr @uri; }
