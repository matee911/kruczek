#!/usr/bin/env bash
# check-deps.sh — sprawdza zależności kruczka i wypisuje instrukcję instalacji brakujących.
# Wyjście: 0 = wszystko OK, 1 = brakuje czegoś wymaganego.
set -euo pipefail

REQUIRED=(curl jq python3)
OPTIONAL_PDF=(weasyprint wkhtmltopdf)
# Chrome/Chromium sprawdzane osobno (has_chrome) — na macOS to .app, nie binarka w PATH
# ggrep (macOS) — GNU grep z obsługą -P (PCRE); na Linux zwykły grep już ma -P
case "$(uname -s)" in
  Darwin) OPTIONAL_REST=(pandoc pdftotext pdfinfo tesseract ocrmypdf qpdf p7zip exiftool ggrep unzip) ;;
  *)      OPTIONAL_REST=(pandoc pdftotext pdfinfo tesseract ocrmypdf qpdf p7zip exiftool unzip) ;;
esac

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { printf "${GREEN}  ✓${NC} %s\n" "$1"; }
warn() { printf "${YELLOW}  ⚠${NC} %s\n" "$1"; }
err()  { printf "${RED}  ✗${NC} %s\n" "$1"; }

has() { command -v "$1" &>/dev/null; }

has_chrome() {
  for cmd in google-chrome google-chrome-stable chromium chromium-browser; do
    has "$cmd" && return 0
  done
  [ -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ] && return 0
  [ -x "/Applications/Chromium.app/Contents/MacOS/Chromium" ] && return 0
  return 1
}

OS="$(uname -s)"
case "$OS" in
  Darwin)  PLATFORM="macos" ;;
  Linux)   PLATFORM="linux" ;;
  *)       PLATFORM="unknown" ;;
esac

missing_required=()
pdf_found=false
missing_optional=()

echo ""
echo "=== kruczek: sprawdzanie zależności ==="
echo ""

echo "Wymagane:"
for cmd in "${REQUIRED[@]}"; do
  if has "$cmd"; then
    ok "$cmd"
  else
    err "$cmd  (brakuje)"
    missing_required+=("$cmd")
  fi
done

echo ""
echo "PDF (wystarczy jedno; próbowane w kolejności: weasyprint, Chrome/Chromium, wkhtmltopdf):"
for cmd in "${OPTIONAL_PDF[@]}"; do
  if has "$cmd"; then
    ok "$cmd"
    pdf_found=true
  else
    warn "$cmd  (brak)"
  fi
done
if has_chrome; then
  ok "Chrome/Chromium (headless)"
  pdf_found=true
else
  warn "Chrome/Chromium  (brak)"
fi

echo ""
echo "Opcjonalne:"
for cmd in "${OPTIONAL_REST[@]}"; do
  if has "$cmd"; then
    ok "$cmd"
  else
    warn "$cmd  (brak — ograniczona funkcjonalność)"
    missing_optional+=("$cmd")
  fi
done

if [ "${#missing_required[@]}" -gt 0 ] || ! $pdf_found || [ "${#missing_optional[@]}" -gt 0 ]; then
  echo ""
  echo "=== Instalacja brakujących pakietów ==="
  echo ""

  # Zbierz wszystkie brakujące do zainstalowania
  # Uwaga: "${arr[@]}" na PUSTEJ tablicy pod `set -u` wywraca się w bashu 3.2
  # (domyślny /bin/bash na macOS) błędem "unbound variable" — naprawione w bashu
  # 4.4+, ale kruczek ma działać też na starym systemowym bashu. Stąd wszędzie
  # niżej idiom "${arr[@]+"${arr[@]}"}" zamiast gołego "${arr[@]}".
  to_install=("${missing_required[@]+"${missing_required[@]}"}")
  # weasyprint ma najlepsze wsparcie CSS @page (marginesy pisma) — sugerujemy je
  # jako pierwsze do instalacji, ale Chrome/Chromium (już często obecny) też
  # wystarczy i nie wymaga żadnej instalacji.
  ! $pdf_found && to_install+=(weasyprint)
  to_install+=("${missing_optional[@]+"${missing_optional[@]}"}")

  case "$PLATFORM" in
    macos)
      # Mapuj nazwy poleceń na pakiety brew
      brew_pkgs=()
      brew_cask_pkgs=()
      for cmd in "${to_install[@]}"; do
        case "$cmd" in
          python3)     brew_pkgs+=(python) ;;
          pdftotext|pdfinfo) brew_pkgs+=(poppler) ;;
          tesseract)   brew_pkgs+=(tesseract tesseract-lang) ;;
          wkhtmltopdf) brew_cask_pkgs+=(wkhtmltopdf) ;;
          p7zip)       brew_pkgs+=(p7zip) ;;
          exiftool)    brew_pkgs+=(exiftool) ;;
          qpdf)        brew_pkgs+=(qpdf) ;;
          ggrep)       brew_pkgs+=(grep) ;;
          unzip)       brew_pkgs+=(unzip) ;;
          *)           brew_pkgs+=("$cmd") ;;
        esac
      done
      # Deduplicate
      brew_pkgs=($(printf '%s\n' "${brew_pkgs[@]+"${brew_pkgs[@]}"}" | sort -u))
      [ "${#brew_pkgs[@]}" -gt 0 ] && echo "  brew install ${brew_pkgs[*]}"
      [ "${#brew_cask_pkgs[@]}" -gt 0 ] && echo "  brew install --cask ${brew_cask_pkgs[*]}"
      ;;
    linux)
      apt_pkgs=()
      for cmd in "${to_install[@]}"; do
        case "$cmd" in
          python3)     apt_pkgs+=(python3) ;;
          pdftotext|pdfinfo) apt_pkgs+=(poppler-utils) ;;
          tesseract)   apt_pkgs+=(tesseract-ocr tesseract-ocr-pol) ;;
          p7zip)       apt_pkgs+=(p7zip-full) ;;
          exiftool)    apt_pkgs+=(libimage-exiftool-perl) ;;
          qpdf)        apt_pkgs+=(qpdf) ;;
          unzip)       apt_pkgs+=(unzip) ;;
          *)           apt_pkgs+=("$cmd") ;;
        esac
      done
      apt_pkgs=($(printf '%s\n' "${apt_pkgs[@]+"${apt_pkgs[@]}"}" | sort -u))
      [ "${#apt_pkgs[@]}" -gt 0 ] && echo "  sudo apt install ${apt_pkgs[*]}"
      if [ "${#apt_pkgs[@]}" -gt 0 ] && printf '%s\n' "${apt_pkgs[@]}" | grep -qx weasyprint; then
        echo "  (jeśli apt nie ma pakietu weasyprint w Twojej dystrybucji: pip install weasyprint," \
             "albo zainstaluj chromium: sudo apt install chromium)"
      fi
      ;;
    *)
      echo "  Zainstaluj ręcznie: ${to_install[*]}"
      ;;
  esac
  echo ""
fi

if [ "${#missing_required[@]}" -gt 0 ]; then
  echo "Brakuje wymaganych narzędzi: ${missing_required[*]}"
  echo "Zainstaluj je i uruchom /kruczek:init-projekt ponownie."
  exit 1
fi

if ! $pdf_found; then
  warn "Brak narzędzi PDF (wkhtmltopdf / weasyprint) — składanie pism do PDF nie będzie działać."
fi

if [ "${#missing_optional[@]}" -gt 0 ]; then
  warn "Brakujące opcjonalne: ${missing_optional[*]}"
fi

echo ""
echo "Zależności wymagane: OK"
echo ""
exit 0
