#!/usr/bin/env bash
# smoketest.sh — mechaniczny "czy się w ogóle uruchamia" test dla wszystkich skryptów kruczka
# I każdej ich podkomendy, nie tylko wywołania bez argumentów.
#
# Nie sprawdza logiki (od tego jest test_kontrola_logika.py) — łapie: błędy składni,
# crashe bashowe (np. "unbound variable" na pustej tablicy pod bash 3.2 — dokładnie ten
# błąd, który miał check-deps.sh) i literówki w nazwach zmiennych ujawniające się dopiero
# przy uruchomieniu konkretnej gałęzi kodu, nie przy `bash -n`.
#
# Trzy warstwy:
#   1. składnia (bash -n / python3 -m py_compile)
#   2. uruchomienie bez argumentów — łapie błędy w samej ścieżce "brak argumentu"/usage
#   3. uruchomienie KAŻDEJ realnej podkomendy z sensownymi argumentami — łapie błędy
#      w kodzie, do którego brak-argumentów nigdy nie dotrze
#
# Warstwa 3 woła prawdziwe, publiczne, tylko-do-odczytu API (dns.google, ELI Sejmu, SAOS,
# UODO, RDAP, biała lista VAT, KRS, Wayback CDX/historia). To celowe — bug w check-deps.sh
# manifestował się tylko przy realnym przebiegu, nie przy samej składni. Świadomie pomijamy
# `archiwa.sh save` (Save Page Now realnie zapisuje coś w Wayback Machine u strony trzeciej —
# nie chcemy tego robić przy każdym pushu). Awaria SIECI (curl nie odpowiada, 429, 5xx) nie
# jest tu traktowana jako błąd smoketestu — to nie to sprawdzamy. Błąd to: crash
# bashowy/pythonowy, albo kod wyjścia spoza {0,1,2}.
#
# Użycie: smoketest.sh [ścieżka do katalogu scripts/]
set -uo pipefail   # bez -e — jeden niezerowy exit nie ma przerywać reszty testów

# Ścieżkę z argumentu normalizujemy do bezwzględnej: część testów uruchamia skrypty
# z katalogu tymczasowego (smoke_cmd_fixture), więc ścieżka względna — jak "scripts"
# przekazywane przez workflow CI — rozjeżdża się tam na "No such file or directory".
SCRIPTS_DIR="$(cd "${1:-$(dirname "${BASH_SOURCE[0]}")}" && pwd)"
FAIL=0

CRASH_SIGNATURES='unbound variable|bad substitution|syntax error near|Traceback \(most recent call last\)|SyntaxError'

TIMEOUT_BIN=""
command -v timeout >/dev/null 2>&1 && TIMEOUT_BIN="timeout"
command -v gtimeout >/dev/null 2>&1 && TIMEOUT_BIN="gtimeout"

report() {
  # $1=etykieta $2=exit-code $3=plik-ze-stderr $4=tryb (strict|soft, domyślnie strict)
  #
  # "soft" jest dla komend zależnych od usług trzecich o udokumentowanej niestabilności
  # (SAOS, CBOSA/SN, Wayback CDX — patrz retrospektywy: "w praktyce nieużyty",
  # "zablokowane dla automatu"). Sygnatura crasha ZAWSZE failuje, niezależnie od trybu —
  # to co "soft" wybacza, to sam fakt, że sieć/API stron trzecich bywa wolne albo padnie.
  local label="$1" ec="$2" errfile="$3" mode="${4:-strict}"
  if grep -qEi "$CRASH_SIGNATURES" "$errfile"; then
    echo "✗ CRASH  $label  (exit=$ec)"
    sed 's/^/    /' "$errfile"
    FAIL=1
  elif [ "$ec" -gt 2 ]; then
    if [ "$mode" = soft ]; then
      echo "⚠ FLAKY  $label  (exit=$ec — usługa trzecia niedostępna/wolna, nie liczymy jako błąd)"
      sed 's/^/    /' "$errfile"
    else
      echo "✗ EXIT?  $label  (exit=$ec, spodziewano 0/1/2)"
      sed 's/^/    /' "$errfile"
      FAIL=1
    fi
  else
    echo "✓ ok     $label  (exit=$ec)"
  fi
}

run_isolated() {
  # Wywołanie bez argumentów: $1=ścieżka skryptu $2=runner (bash/python3/...)
  local script="$1" runner="$2"
  local tmp out err ec
  tmp=$(mktemp -d); out=$(mktemp); err=$(mktemp)
  if [ -n "$TIMEOUT_BIN" ]; then
    ( cd "$tmp" && "$TIMEOUT_BIN" 20 "$runner" "$script" ) >"$out" 2>"$err" </dev/null
  else
    ( cd "$tmp" && "$runner" "$script" ) >"$out" 2>"$err" </dev/null
  fi
  ec=$?
  report "$(basename "$script") (bez argumentów, $runner)" "$ec" "$err"
  rm -rf "$tmp" "$out" "$err"
}

# Wywołanie z realnymi argumentami we WŁASNYM, izolowanym katalogu tymczasowym.
# $1=etykieta $2=runner $3=ścieżka skryptu, reszta=argumenty.
# Zmienne środowiskowe do przekazania: ustaw przed wywołaniem (np. KRUCZEK_CONTACT=...).
smoke_cmd() {
  local label="$1" runner="$2" script="$3"; shift 3
  local tmp out err ec
  tmp=$(mktemp -d); out=$(mktemp); err=$(mktemp)
  if [ -n "$TIMEOUT_BIN" ]; then
    ( cd "$tmp" && "$TIMEOUT_BIN" 25 "$runner" "$script" "$@" ) >"$out" 2>"$err" </dev/null
  else
    ( cd "$tmp" && "$runner" "$script" "$@" ) >"$out" 2>"$err" </dev/null
  fi
  ec=$?
  report "$label" "$ec" "$err"
  rm -rf "$tmp" "$out" "$err"
}

# Jak smoke_cmd, ale w trybie "soft" — patrz komentarz w report(). Dla komend zależnych
# od realnie niestabilnych usług trzecich (SAOS, Wayback CDX...) — patrz komentarze
# przy poszczególnych blokach niżej, gdzie to zweryfikowano bezpośrednio.
smoke_cmd_soft() {
  local label="$1" runner="$2" script="$3"; shift 3
  local tmp out err ec
  tmp=$(mktemp -d); out=$(mktemp); err=$(mktemp)
  if [ -n "$TIMEOUT_BIN" ]; then
    ( cd "$tmp" && "$TIMEOUT_BIN" 25 "$runner" "$script" "$@" ) >"$out" 2>"$err" </dev/null
  else
    ( cd "$tmp" && "$runner" "$script" "$@" ) >"$out" 2>"$err" </dev/null
  fi
  ec=$?
  report "$label" "$ec" "$err" soft
  rm -rf "$tmp" "$out" "$err"
}

# Jak smoke_cmd, ale z przygotowaniem plików w katalogu roboczym PRZED uruchomieniem —
# przydatne dla skryptów operujących na realnych plikach (metadane.sh, manifest.py, ...).
# $1=etykieta $2=runner $3=ścieżka skryptu $4=nazwa funkcji przygotowującej fixture
# (wykonywana w katalogu tymczasowym, przed właściwym wywołaniem), reszta=argumenty.
smoke_cmd_fixture() {
  local label="$1" runner="$2" script="$3" setup_fn="$4"; shift 4
  local tmp out err ec
  tmp=$(mktemp -d); out=$(mktemp); err=$(mktemp)
  ( cd "$tmp" && "$setup_fn" )
  if [ -n "$TIMEOUT_BIN" ]; then
    ( cd "$tmp" && "$TIMEOUT_BIN" 25 "$runner" "$script" "$@" ) >"$out" 2>"$err" </dev/null
  else
    ( cd "$tmp" && "$runner" "$script" "$@" ) >"$out" 2>"$err" </dev/null
  fi
  ec=$?
  report "$label" "$ec" "$err"
  rm -rf "$tmp" "$out" "$err"
}

echo "=== składnia bash ==="
for f in "$SCRIPTS_DIR"/*.sh; do
  if bash -n "$f"; then
    echo "✓ syntax $(basename "$f")"
  else
    echo "✗ syntax $(basename "$f")"
    FAIL=1
  fi
done

echo
echo "=== składnia python ==="
for f in "$SCRIPTS_DIR"/*.py; do
  if python3 -m py_compile "$f"; then
    echo "✓ syntax $(basename "$f")"
  else
    echo "✗ syntax $(basename "$f")"
    FAIL=1
  fi
done

skip_sh() {
  case "$(basename "$1")" in
    lib.sh|smoketest.sh) return 0 ;;   # lib.sh: nie do bezpośredniego uruchamiania.
    # smoketest.sh bez argumentów domyśla katalog skryptów do własnej lokalizacji —
    # uruchomiony sam na sobie wchodzi w rekurencję bez końca. Nie testujemy się nim samym.
    *) return 1 ;;
  esac
}

skip_py() {
  case "$(basename "$1")" in
    utils.py|kontrola_logika.py|run_tests.py) return 0 ;;  # moduły — run_tests.py jest CLI, ale odpala go osobny krok CI
    # Warstwy eml_forensics: importowane przez eml_forensics.py, nie CLI.
    # Wykluczenie było dopisane tylko w workflow (kontrola trybu pliku),
    # a smoketest.sh próbuje URUCHOMIĆ każdy skrypt bezpośrednio — więc
    # moduły bez +x wywracały build z „Permission denied”.
    eml_forensics_logika.py|eml_forensics_raport.py) return 0 ;;
    # czysta logika importowana przez build_pismo.py, bez CLI — `+x` byłby
    # nieprawdziwą deklaracją o roli pliku, więc wyjątek zamiast chmod.
    build_pismo_logic.py) return 0 ;;
    test_*.py) return 0 ;;  # pliki testowe — źródło/import, nie CLI
    *) return 1 ;;
  esac
}

# Wywołanie BEZPOŚREDNIE (./script, bez jawnego interpretera z przodu) — jedyny sposób,
# który faktycznie sprawdza bit +x. Wszystkie inne warstwy tego smoketestu wołają
# "bash script.sh" / "python3 script.py" — a to NIGDY nie sprawdza +x, bo to interpreter
# czyta plik jako swój argument, nie system operacyjny przez exec(). Skille wywołują
# skrypty właśnie bezpośrednio (np. `${CLAUDE_PLUGIN_ROOT}/scripts/gen-claude-md.sh
# <katalog>`, bez "bash" z przodu) — dokładnie tak w realnej sesji 2026-08-28 wyszło na
# jaw, że `archiwa.sh`, `gen-claude-md.sh` i `metadane.sh` były commitowane bez +x.
check_direct_exec() {
  local script="$1"
  local tmp out err ec
  tmp=$(mktemp -d); out=$(mktemp); err=$(mktemp)
  if [ -n "$TIMEOUT_BIN" ]; then
    ( cd "$tmp" && "$TIMEOUT_BIN" 20 "$script" ) >"$out" 2>"$err" </dev/null
  else
    ( cd "$tmp" && "$script" ) >"$out" 2>"$err" </dev/null
  fi
  ec=$?
  if [ "$ec" -eq 126 ] || grep -qi "permission denied" "$err"; then
    echo "✗ BRAK +x  $(basename "$script")  (exit=$ec) — napraw: chmod +x $script"
    sed 's/^/    /' "$err"
    FAIL=1
  else
    echo "✓ ok       $(basename "$script")  (bezpośrednio, exit=$ec)"
  fi
  rm -rf "$tmp" "$out" "$err"
}

echo
echo "=== uruchomienie bezpośrednie, sprawdza bit +x (./script, bez interpretera) ==="
for f in "$SCRIPTS_DIR"/*.sh; do
  skip_sh "$f" && continue
  check_direct_exec "$f"
done
for f in "$SCRIPTS_DIR"/*.py; do
  skip_py "$f" && continue
  check_direct_exec "$f"
done

echo
echo "=== uruchomienie bez argumentów (bash domyślny w PATH) ==="
for f in "$SCRIPTS_DIR"/*.sh; do
  skip_sh "$f" && continue
  run_isolated "$f" bash
done

if [ -x /bin/bash ]; then
  echo
  echo "=== uruchomienie bez argumentów (/bin/bash — łapie regresje typu bash 3.2 na macOS) ==="
  for f in "$SCRIPTS_DIR"/*.sh; do
    skip_sh "$f" && continue
    run_isolated "$f" /bin/bash
  done
fi

echo
echo "=== uruchomienie bez argumentów (python3) ==="
for f in "$SCRIPTS_DIR"/*.py; do
  case "$(basename "$f")" in
    utils.py|kontrola_logika.py|test_kontrola_logika.py|run_tests.py) continue ;;  # moduły/testy — run_tests.py jest CLI, ale odpala go osobny krok CI
  esac
  run_isolated "$f" python3
done

# ============================================================================
# Warstwa 3: każda realna podkomenda, z argumentami, prawdziwe API tylko-do-odczytu.
# ============================================================================
echo
echo "=== realne podkomendy (dns.sh) ==="
D="$SCRIPTS_DIR/dns.sh"
smoke_cmd "dns.sh rekordy"  bash "$D" rekordy example.com
smoke_cmd "dns.sh poczta"   bash "$D" poczta example.com
smoke_cmd "dns.sh dkim"     bash "$D" dkim example.com default
smoke_cmd "dns.sh typ"      bash "$D" typ example.com A
smoke_cmd "dns.sh raport"   bash "$D" raport example.com
smoke_cmd "dns.sh porownaj" bash "$D" porownaj example.com example.org

echo
echo "=== realne podkomendy (eli.sh) ==="
E="$SCRIPTS_DIR/eli.sh"
smoke_cmd "eli.sh szukaj"       bash "$E" szukaj "Kodeks cywilny"
smoke_cmd "eli.sh meta"         bash "$E" meta DU 2024 1221
smoke_cmd "eli.sh teksty"       bash "$E" teksty DU 1964 93
smoke_cmd "eli.sh ujednolicony" bash "$E" ujednolicony DU 1964 93
smoke_cmd "eli.sh referencje"   bash "$E" referencje DU 2004 1800
smoke_cmd "eli.sh obowiazuje"   bash "$E" obowiazuje DU 2004 1800
smoke_cmd "eli.sh zmiany"       bash "$E" zmiany 2026-08-01

echo
echo "=== realne podkomendy (orzecznictwo.sh) — tryb soft: bazy orzeczeń stron trzecich"
echo "    (SAOS, CBOSA, SN) mają udokumentowaną (patrz retrospektywy kruczka) historię"
echo "    niedostępności/blokad dla automatów, w praktyce bywają wolne/niestabilne pod"
echo "    obciążeniem (zweryfikowane 2026-08-28: SAOS timeoutował dwukrotnie z rzędu,"
echo "    po 15s przerwy odpowiedział w 0,27s — realna niestabilność serwisu, nie stała"
echo "    blokada); timeout/błąd sieci tu ostrzega, nie failuje builda ==="
O="$SCRIPTS_DIR/orzecznictwo.sh"
smoke_cmd_soft "orzecznictwo.sh saos"         bash "$O" saos "informacja handlowa"
smoke_cmd_soft "orzecznictwo.sh saos-tresc"   bash "$O" saos-tresc 123456
smoke_cmd_soft "orzecznictwo.sh saos-przepis" bash "$O" saos-przepis 2024/1221
smoke_cmd_soft "orzecznictwo.sh uodo"         bash "$O" uodo marketing
smoke_cmd_soft "orzecznictwo.sh uodo-tresc"   bash "$O" uodo-tresc DKN.5131.34.2023
smoke_cmd_soft "orzecznictwo.sh cbosa"        bash "$O" cbosa 6C317F6401
smoke_cmd_soft "orzecznictwo.sh sn"           bash "$O" sn "III SZP 7/15"
smoke_cmd_soft "orzecznictwo.sh uke"          bash "$O" uke 2025

echo
echo "=== realne podkomendy (podmiot.sh) ==="
P="$SCRIPTS_DIR/podmiot.sh"
smoke_cmd "podmiot.sh nip"    bash "$P" nip 5252344078
smoke_cmd "podmiot.sh regon"  bash "$P" regon 140182840
smoke_cmd "podmiot.sh krs"    bash "$P" krs 0000240611 P
# ceidg bez tokenu kończy się kontrolowanym exit 1 — to gałąź "brak tokenu", też warta testu
smoke_cmd "podmiot.sh ceidg (bez tokenu)" bash "$P" ceidg 5252344078
smoke_cmd "podmiot.sh domena" bash "$P" domena example.pl
smoke_cmd "podmiot.sh strona" bash "$P" strona https://example.com
smoke_cmd "podmiot.sh pelny"  bash "$P" pelny 5252344078

echo
echo "=== realne podkomendy (archiwa.sh) — tryb soft. Zweryfikowane 2026-08-28: endpoint"
echo "    CDX (historia, cdx-url) bywa degradowany niezależnie od User-Agenta i obciążenia"
echo "    z naszej strony — web.archive.org/ (strona główna) odpowiadał normalnie (<1s),"
echo "    ale /cdx/search/cdx timeoutował z 0 bajtów nawet po przerwie i zmianie URL-a."
echo "    To realna niestabilność konkretnie CDX API, nie throttling za częste odpytania"
echo "    ani brak zgodnego z archive.org/developers/bots.html UA (archiwa.sh go ustawia)."
echo "    Pomijamy 'save' (realny zapis u strony trzeciej) ==="
export KRUCZEK_CONTACT="ci-smoketest@example.invalid"
A="$SCRIPTS_DIR/archiwa.sh"
smoke_cmd_soft "archiwa.sh historia" bash "$A" historia example.com
smoke_cmd_soft "archiwa.sh cdx-url"  bash "$A" cdx-url example.com
smoke_cmd_soft "archiwa.sh pobierz"  bash "$A" pobierz example.com 20200101000000 .
unset KRUCZEK_CONTACT

echo
echo "=== realne podkomendy (manifest.py) ==="
M="$SCRIPTS_DIR/manifest.py"
setup_manifest() { echo "przykladowa tresc" > dowod.txt; }
smoke_cmd_fixture "manifest.py skan"    python3 "$M" setup_manifest skan .
smoke_cmd_fixture "manifest.py sumy"    python3 "$M" setup_manifest sumy .
smoke_cmd_fixture "manifest.py sprawdz" python3 "$M" setup_manifest sprawdz .
setup_manifest_wstaw() {
  echo "przykladowa tresc" > dowod.txt
  printf '# SPRAWA\n\n<!-- KRUCZEK:MANIFEST:START -->\n<!-- KRUCZEK:MANIFEST:END -->\n' > index.md
}
smoke_cmd_fixture "manifest.py wstaw" python3 "$M" setup_manifest_wstaw wstaw index.md .

echo
echo "=== realne podkomendy (metadane.sh) ==="
ME="$SCRIPTS_DIR/metadane.sh"
setup_metadane() { echo "tresc" > 2026-01-01_dowod.eml; }
smoke_cmd_fixture "metadane.sh na .eml" bash "$ME" setup_metadane 2026-01-01_dowod.eml

echo
echo "=== realne podkomendy (eml_forensics.py) ==="
EF="$SCRIPTS_DIR/eml_forensics.py"
setup_eml() {
  cat > sample.eml <<'EOM'
From: nadawca@example.com
To: odbiorca@example.com
Subject: Test smoketestu
Date: Mon, 1 Jan 2026 12:00:00 +0000
Content-Type: text/plain; charset=utf-8

Tresc testowej wiadomosci.
EOM
}
smoke_cmd_fixture "eml_forensics.py" python3 "$EF" setup_eml sample.eml

echo
echo "=== realne podkomendy (build_pismo.py) — bez silnika PDF w CI: oczekiwany kontrolowany błąd ==="
BP="$SCRIPTS_DIR/build_pismo.py"
setup_pismo() { printf '<html><body><!--KRUCZEK:ZALACZNIKI--><!--KRUCZEK:LISTA_ZALACZNIKOW--></body></html>' > pismo.html; }
smoke_cmd_fixture "build_pismo.py" python3 "$BP" setup_pismo pismo.html -o pismo.pdf

echo
echo "=== realne podkomendy (kontrola_pisma.py) — bez pdftotext w CI: oczekiwany kontrolowany błąd ==="
KP="$SCRIPTS_DIR/kontrola_pisma.py"
setup_kontrola() { mkdir -p ARCHIWUM; echo "%PDF-1.4 fake" > fake.pdf; }
smoke_cmd_fixture "kontrola_pisma.py" python3 "$KP" setup_kontrola fake.pdf --sprawa .

echo
echo "=== realne podkomendy (dane_nadawcy_status.py) ==="
DS="$SCRIPTS_DIR/dane_nadawcy_status.py"
setup_dane() { cp "$SCRIPTS_DIR/../templates/dane-nadawcy.md" dane-nadawcy.md 2>/dev/null || echo "| Imię i nazwisko | |" > dane-nadawcy.md; }
smoke_cmd_fixture "dane_nadawcy_status.py" python3 "$DS" setup_dane dane-nadawcy.md

echo
echo "=== realne podkomendy (nowa-sprawa.sh, gen-claude-md.sh, init-projekt.sh) ==="
NS="$SCRIPTS_DIR/nowa-sprawa.sh"
smoke_cmd "nowa-sprawa.sh z argumentami" bash "$NS" "Testowa Sp. z o.o." "test smoketestu" .
GC="$SCRIPTS_DIR/gen-claude-md.sh"
setup_gen_claude() { mkdir -p _SZABLONY; cp "$SCRIPTS_DIR/../templates/dane-nadawcy.md" _SZABLONY/dane-nadawcy.md 2>/dev/null || true; }
smoke_cmd_fixture "gen-claude-md.sh z katalogiem" bash "$GC" setup_gen_claude .
IP="$SCRIPTS_DIR/init-projekt.sh"
smoke_cmd "init-projekt.sh na pustym katalogu" bash "$IP" .

echo
if [ "$FAIL" -eq 0 ]; then
  echo "Smoketest: OK"
else
  echo "Smoketest: BŁĘDY — patrz wyżej"
fi
exit "$FAIL"
