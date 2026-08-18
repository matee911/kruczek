#!/usr/bin/env bash
# metadane.sh — zbiorcza analiza metadanych plików od przeciwnika
# Użycie: metadane.sh <plik> [plik2 ...]
# Wypisuje tabelę: plik | data z nazwy | data z metadanych | data z treści | uwagi
set -euo pipefail

if [ $# -eq 0 ]; then
  echo "Użycie: metadane.sh <plik> [plik2 ...]"
  echo "Obsługiwane: .pdf .docx .xlsx .jpg .jpeg .png .eml"
  exit 1
fi

has() { command -v "$1" &>/dev/null; }

printf '%-40s | %-12s | %-20s | %s\n' "PLIK" "DATA_Z_NAZWY" "DATA_Z_METADANYCH" "UWAGI"
printf '%s\n' "$(printf '%.0s-' {1..100})"

for FILE in "$@"; do
  [ -f "$FILE" ] || { echo "POMINIĘTO (brak pliku): $FILE" >&2; continue; }
  BASENAME=$(basename "$FILE")
  EXT="${BASENAME##*.}"
  EXT_LOWER=$(echo "$EXT" | tr '[:upper:]' '[:lower:]')

  # Data z nazwy pliku (RRRR-MM-DD na początku)
  DATE_NAME=$(echo "$BASENAME" | grep -oE '^[0-9]{4}-[0-9]{2}-[0-9]{2}' || echo "brak")

  META_DATE="?"
  UWAGI=""

  case "$EXT_LOWER" in
    pdf)
      if has exiftool; then
        CREATE=$(exiftool -s3 -CreateDate "$FILE" 2>/dev/null | head -1 | tr -d '\r')
        MODIFY=$(exiftool -s3 -ModifyDate "$FILE" 2>/dev/null | head -1 | tr -d '\r')
        AUTHOR=$(exiftool -s3 -Author "$FILE" 2>/dev/null | head -1 | tr -d '\r')
        PRODUCER=$(exiftool -s3 -Producer "$FILE" 2>/dev/null | head -1 | tr -d '\r')
        META_DATE="${CREATE:-$MODIFY}"
        [ -n "$AUTHOR" ] && UWAGI+="Author:${AUTHOR} "
        echo "$PRODUCER" | grep -qi "word\|writer\|excel" && UWAGI+="⚠Producer:Word/Writer "
        [ -n "$UWAGI" ] && UWAGI="$UWAGI"
      else
        META_DATE="(brak exiftool)"
      fi
      ;;
    docx|xlsx|pptx)
      if has unzip; then
        CORE=$(unzip -p "$FILE" docProps/core.xml 2>/dev/null || echo "")
        if [ -n "$CORE" ]; then
          _grep() { ggrep -oP "$@" 2>/dev/null || grep -oP "$@" 2>/dev/null || true; }
          CREATE=$(echo "$CORE" | _grep '(?<=<dcterms:created[^>]*>)[^<]+' | head -1)
          MODIFY=$(echo "$CORE" | _grep '(?<=<dcterms:modified[^>]*>)[^<]+' | head -1)
          AUTHOR=$(echo "$CORE" | _grep '(?<=<dc:creator>)[^<]+' | head -1)
          REVISIONS=$(echo "$CORE" | _grep '(?<=<cp:revision>)[^<]+' | head -1)
          META_DATE="${CREATE:-$MODIFY}"
          [ -n "$AUTHOR" ] && UWAGI+="Author:${AUTHOR} "
          [ -n "$REVISIONS" ] && [ "$REVISIONS" -le 2 ] 2>/dev/null && UWAGI+="⚠RevWersje:${REVISIONS} "
        fi
      else
        META_DATE="(brak unzip)"
      fi
      ;;
    jpg|jpeg|png|gif|tiff|heic)
      if has exiftool; then
        DT=$(exiftool -s3 -DateTimeOriginal "$FILE" 2>/dev/null | head -1 | tr -d '\r')
        GPS=$(exiftool -s3 -GPSLatitude "$FILE" 2>/dev/null | head -1 | tr -d '\r')
        MODEL=$(exiftool -s3 -Model "$FILE" 2>/dev/null | head -1 | tr -d '\r')
        META_DATE="${DT:-(brak EXIF)}"
        [ -n "$GPS" ] && UWAGI+="⚠GPS_obecny "
        [ -n "$MODEL" ] && UWAGI+="Aparat:${MODEL} "
      else
        META_DATE="(brak exiftool)"
      fi
      ;;
    eml)
      DATE_HDR=$(grep -m1 '^Date:' "$FILE" 2>/dev/null | sed 's/^Date: //' | tr -d '\r' || echo "brak")
      META_DATE="$DATE_HDR"
      DKIM=$(grep -m1 'DKIM-Signature' "$FILE" 2>/dev/null | head -c 20 || echo "")
      [ -n "$DKIM" ] && UWAGI+="DKIM_obecny "
      ;;
    *)
      META_DATE="(nieobsługiwany typ)"
      ;;
  esac

  # Wykryj rozbieżność daty z nazwy i metadanych
  if [ "$DATE_NAME" != "brak" ] && [ -n "$META_DATE" ] && [ "$META_DATE" != "?" ]; then
    META_YEAR=$(echo "$META_DATE" | grep -oE '[0-9]{4}' | head -1)
    NAME_YEAR=$(echo "$DATE_NAME" | grep -oE '[0-9]{4}' | head -1)
    [ -n "$META_YEAR" ] && [ -n "$NAME_YEAR" ] && [ "$META_YEAR" != "$NAME_YEAR" ] && \
      UWAGI+="⚠RozbieznosDat "
  fi

  printf '%-40s | %-12s | %-20s | %s\n' \
    "${BASENAME:0:40}" \
    "${DATE_NAME:0:12}" \
    "${META_DATE:0:20}" \
    "$UWAGI"
done

echo ""
echo "Legenda flag:"
echo "  ⚠Producer:Word/Writer — dokument złożony ręcznie, nie eksport z systemu"
echo "  ⚠RevWersje:N          — bardzo mała liczba rewizji (≤2), możliwe zrobione ad hoc"
echo "  ⚠GPS_obecny           — zdjęcie zawiera dane lokalizacyjne (art. 5 ust. 1 lit. c RODO)"
echo "  ⚠RozbieznosDat        — rok w nazwie pliku ≠ rok w metadanych"
