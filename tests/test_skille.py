"""Testy strukturalne skilli i agentów: rzeczy, których nie złapie żaden test kodu, a które psują
zachowanie komend (np. krok, którego model nie może wykonać)."""

import re
from pathlib import Path

import pytest
from build_pismo_logic import DOZWOLONE_ZNACZNIKI
from linki_dowodu import Rekomendacja

KORZEN = Path(__file__).resolve().parent.parent
SKILLE = KORZEN / "skills"
AGENCI = KORZEN / "agents"
WZMIANKA = re.compile(r"/kruczek:([a-z-]+)")
# Komenda z disable-model-invocation jest niewidoczna dla modelu — wolno ją tylko podpowiedzieć użytkownikowi.
PODPOWIEDZ_DLA_USERA = re.compile(r"zaproponuj|podpowiedz|użytkownikowi|podpowiedź dla użytkownika", re.IGNORECASE)


def _frontmatter(tekst: str) -> dict[str, str]:
    _, naglowek, _ = tekst.split("---", 2)
    pola = {}
    for linia in naglowek.splitlines():
        if ":" in linia and not linia.startswith((" ", "\t")):
            klucz, wartosc = linia.split(":", 1)
            pola[klucz.strip()] = wartosc.strip()
    return pola


def _skill(nazwa: str) -> tuple[dict[str, str], str]:
    tekst = (SKILLE / nazwa / "SKILL.md").read_text(encoding="utf-8")
    return _frontmatter(tekst), tekst.split("---", 2)[2]


def _sekcja(tresc: str, numer: int) -> str:
    """Treść sekcji „## <numer>. …” do następnego nagłówka „## ”."""
    m = re.search(rf"^## {numer}\..*?(?=^## |\Z)", tresc, re.MULTILINE | re.DOTALL)
    assert m, f"brak sekcji {numer}"
    return m.group(0)


def _niewidoczne_dla_modelu() -> set[str]:
    return {k.name for k in SKILLE.iterdir()
            if (k / "SKILL.md").exists() and _skill(k.name)[0].get("disable-model-invocation") == "true"}


def martwe_wzmianki(tresc: str, niewidoczne: set[str], wlasna: str = "") -> list[str]:
    """Linie, które wymieniają komendę niewidoczną dla modelu bez znacznika podpowiedzi dla usera.

    >>> martwe_wzmianki("```\\n/kruczek:kontrola  # mechanicznie\\n/kruczek:recenzja  # merytorycznie\\n```", {"recenzja"})
    ['/kruczek:recenzja  # merytorycznie']
    >>> martwe_wzmianki("zaproponuj `/kruczek:recenzja`\\n| `/kruczek:recenzja` | spis |", {"recenzja"})
    []
    """
    zle = []
    for linia in tresc.splitlines():
        if linia.lstrip().startswith("|") or PODPOWIEDZ_DLA_USERA.search(linia):
            continue
        if any(m.group(1) in niewidoczne and m.group(1) != wlasna for m in WZMIANKA.finditer(linia)):
            zle.append(linia.strip())
    return zle


PLIKI_Z_INSTRUKCJAMI = sorted([*SKILLE.glob("*/SKILL.md"), *AGENCI.glob("*.md")])


@pytest.mark.parametrize("plik", PLIKI_Z_INSTRUKCJAMI, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_instrukcje_nie_wymieniaja_komendy_niewidocznej_bez_podpowiedzi_dla_usera(plik):
    # Arrange
    tresc = plik.read_text(encoding="utf-8").split("---", 2)[2]
    wlasna = plik.parent.name if plik.name == "SKILL.md" else plik.stem
    # Act
    martwe = martwe_wzmianki(tresc, _niewidoczne_dla_modelu(), wlasna)
    # Assert
    assert martwe == []


def test_dawny_krok_recenzji_w_pismie_jest_wykrywany():
    # Arrange — krok 8 /kruczek:pismo w wersji 0.10.0: blok kodu z komendami, bez czasownika
    dawny = "```\n/kruczek:kontrola     # mechanicznie: numeracja\n/kruczek:recenzja     # merytorycznie: fakty\n```"
    # Act
    martwe = martwe_wzmianki(dawny, _niewidoczne_dla_modelu(), "pismo")
    # Assert
    assert martwe == ["/kruczek:recenzja     # merytorycznie: fakty"]


def test_pismo_recenzuje_przez_agentow_a_nie_komende_usera():
    # Arrange
    _, tresc = _skill("pismo")
    # Act
    krok = _sekcja(tresc, 8)
    # Assert
    assert "weryfikuj-cytaty" in krok and "recenzuj" in krok
    assert martwe_wzmianki(krok, {"recenzja"}) == []


PYTA_USERA = re.compile(r"zapytaj|dopytaj|zapytać|AskUserQuestion|pytaj użytkownika|pytaj usera", re.IGNORECASE)
SKILLE_PYTAJACE = sorted(k.name for k in SKILLE.iterdir()
                         if (k / "SKILL.md").exists() and "model" in _skill(k.name)[0]
                         and PYTA_USERA.search(_skill(k.name)[1]))
# Wyjątek: pola otwarte (imię, adres, NIP) nie mają opcji do wyboru, więc te skille pytają o nie zwykłą wiadomością.
# Wolno tylko skillowi na tanim modelu (przełączenie na model sesji po odpowiedzi kosztuje mało), a AskUserQuestion
# zostaje w allowed-tools dla pytań zamkniętych.
OTWARTE_POLA_ZWYKLA_WIADOMOSCIA = {"dane-nadawcy"}
FRAZA_WYJATKU = "zwykłą wiadomością tekstową"


@pytest.mark.parametrize("nazwa", SKILLE_PYTAJACE)
def test_skill_z_modelem_pyta_usera_przez_askuserquestion(nazwa):
    # Arrange — model komendy obowiązuje w pierwszej turze; odpowiedź w prozie zaczyna nową turę modelem sesji
    pola, tresc = _skill(nazwa)
    # Act
    narzedzia = pola.get("allowed-tools", "").split()
    # Assert
    assert "AskUserQuestion" in narzedzia
    assert (FRAZA_WYJATKU in tresc) == (nazwa in OTWARTE_POLA_ZWYKLA_WIADOMOSCIA)


@pytest.mark.parametrize("nazwa", sorted(OTWARTE_POLA_ZWYKLA_WIADOMOSCIA))
def test_wyjatek_od_askuserquestion_tylko_na_tanim_modelu(nazwa):
    # Arrange
    pola, _ = _skill(nazwa)
    # Assert
    assert pola["model"] in {"haiku", "sonnet"}


def test_pismo_deleguje_redakcje_do_napisz_pismo_przez_pliki():
    # Arrange
    _, tresc = _skill("pismo")
    # Act
    napisz, zloz = _sekcja(tresc, 5), _sekcja(tresc, 6)
    # Assert
    assert "napisz-pismo" in napisz and "zawsze" in napisz and "BRIEF.md" in napisz
    assert "Przy złożonej subsumpcji" not in napisz
    assert "--tresc" in zloz and "tresc.html" in zloz


def test_pismo_ogranicza_rundy_poprawek():
    # Arrange
    _, tresc = _skill("pismo")
    # Act
    krok = _sekcja(tresc, 8)
    # Assert
    assert "najwyżej jedna runda" in krok and "AskUserQuestion" in krok


def test_pismo_sklada_raport_wedlug_skilla_recenzja_i_definiuje_przejscie():
    # Arrange
    _, tresc = _skill("pismo")
    recenzja = (SKILLE / "recenzja" / "SKILL.md").read_text(encoding="utf-8")
    # Act
    krok = _sekcja(tresc, 8)
    # Assert
    assert "skills/recenzja/SKILL.md" in krok and "sekcji Raport" in krok
    assert re.search(r"^## Raport$", recenzja, re.MULTILINE)
    assert "przechodzi, gdy nie ma 🔴" in krok


def test_napisz_pismo_ma_staly_model_opus_i_pisze_plik():
    # Arrange
    tekst = (AGENCI / "napisz-pismo.md").read_text(encoding="utf-8")
    # Assert
    assert _frontmatter(tekst).get("model") == "opus"
    assert "tresc.html" in tekst and "Twierdzenia spoza briefu" in tekst


def test_recenzuj_porownuje_pismo_z_briefem():
    # Arrange
    tekst = (AGENCI / "recenzuj.md").read_text(encoding="utf-8")
    # Assert
    assert "BRIEF.md" in tekst
    assert "weryfikatorem-cytatow" not in tekst


def test_fakt_nie_odsyla_do_samego_siebie():
    # Arrange — model jest już wewnątrz /kruczek:fakt; podpowiedź ma wskazywać następny krok
    _, tresc = _skill("fakt")
    # Assert
    assert "/kruczek:fakt" not in tresc


PLIKI_Z_MANIFESTEM = [SKILLE / "dowod" / "SKILL.md", SKILLE / "pismo" / "SKILL.md", AGENCI / "archiwizuj.md"]


@pytest.mark.parametrize("plik", PLIKI_Z_MANIFESTEM, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_blad_manifestu_pokazuje_sie_userowi_a_index_md_nie_jest_edytowany(plik):
    # Arrange — index.md zawiera notatki użytkownika, więc naprawa „na szybko” przez model je zniszczy
    tresc = plik.read_text(encoding="utf-8")
    # Act
    zdanie = re.search(r"uszkodzone znaczniki.{0,80}popraw\s+ręcznie.{0,300}", tresc, re.DOTALL)
    # Assert
    assert zdanie, "brak reguły: błąd manifestu → pokaż komunikat"
    assert re.search(r"pokaż komunikat\s+użytkownikowi", zdanie.group(0))
    assert re.search(r"nie edytuj\s+`index\.md`", zdanie.group(0))


def test_pismo_przekazuje_agentowi_wzor_i_konwencje_jako_bezwzgledne_sciezki():
    # Arrange — agent nie zna katalogu pluginu: bez ścieżek nie zobaczy klas szablonu ani konwencji redakcyjnej
    _, tresc = _skill("pismo")
    agent = (AGENCI / "napisz-pismo.md").read_text(encoding="utf-8")
    # Act
    napisz = _sekcja(tresc, 5)
    # Assert
    for sciezka in ("${CLAUDE_PLUGIN_ROOT}/templates/pismo.html", "${CLAUDE_PLUGIN_ROOT}/skills/redagowanie-pism/SKILL.md"):
        assert sciezka in napisz
        assert sciezka in agent.split("## Struktura argumentacji")[0]
    assert "Zastrzeżenie" in agent


SKILLE_Z_LISTA_SKRYPTOW = ["dowod", "pismo"]


@pytest.mark.parametrize("nazwa", SKILLE_Z_LISTA_SKRYPTOW)
def test_skill_wywoluje_tylko_skrypty_z_allowed_tools(nazwa):
    # Arrange — skrypt spoza allowed-tools to pytanie o zgodę w środku komendy
    pola, tresc = _skill(nazwa)
    # Act
    skrypt = r"\b([A-Za-z_-]+\.(?:sh|py))\b"
    uzyte = set(re.findall(skrypt, tresc))
    dozwolone = set(re.findall(skrypt, pola["allowed-tools"]))
    # Assert
    assert uzyte - dozwolone == set()


def test_dowod_archiwizuje_linki_wedlug_rekomendacji_z_kodu():
    # Arrange — link ze spamu potrafi nieść adres odbiorcy; czy go otworzyć, rozstrzyga skrypt, nie model
    _, tresc = _skill("dowod")
    # Act
    krok = _sekcja(tresc, 6)
    tabela = set(re.findall(r"^\| `([A-Z_]+)` \|", krok, re.MULTILINE))
    jednym_ciagiem = " ".join(krok.split())
    # Assert
    assert "linki_dowodu.py" in krok
    assert tabela == {r.value for r in Rekomendacja}
    assert "`do_archiwizacji`" in jednym_ciagiem and "bez pytania" in jednym_ciagiem and "--nazwa" in krok
    assert "AskUserQuestion" in jednym_ciagiem and "bez `save`" not in jednym_ciagiem
    assert "nie zmieniaj jej" in jednym_ciagiem
    assert "„żaden (zalecane)”" in jednym_ciagiem and "po kroku 7" in jednym_ciagiem
    assert "ze strony publicznej" not in jednym_ciagiem and "wyłącznie przez `linki_dowodu.py`" in jednym_ciagiem


def test_pismo_kopiuje_tresc_przed_poprawka_i_dzieli_limit_rundy_z_krokiem_5():
    # Arrange
    _, tresc = _skill("pismo")
    agent_recenzji = (AGENCI / "recenzuj.md").read_text(encoding="utf-8")
    # Act
    krok5, krok8 = _sekcja(tresc, 5), _sekcja(tresc, 8)
    poprawki = krok8[krok8.index("**Poprawki"):]
    # Assert — kopia przed odesłaniem do agenta (inaczej agent nadpisze plik i „przed” jest puste)
    assert poprawki.index("cp ") < poprawki.index("odeślij")
    assert "ROBOCZE/tresc.przed.html" in poprawki and "diff" not in poprawki
    assert "tresc.przed.html" in agent_recenzji
    assert "wspólny z krokiem 8" in krok5 and "wspólna z krokiem 5" in poprawki


def test_pismo_pozwala_swiadomie_przyjac_pozostale_czerwone():
    # Arrange
    _, tresc = _skill("pismo")
    # Act
    krok = _sekcja(tresc, 8)
    # Assert
    assert krok.count("świadomie przyjął") >= 2 and "gdzie jesteśmy słabi" in krok


def test_pismo_pola_fill_znane_tylko_uzytkownikowi_nie_blokuja_meldunku():
    # Arrange — kontrola mechaniczna zgłasza każde class="fill" jako błąd, a krok 6 każe je zostawić
    _, tresc = _skill("pismo")
    # Act
    krok8, krok11 = _sekcja(tresc, 8), _sekcja(tresc, 11)
    regula = " ".join(krok8[krok8.index("**Nie melduj"):].split())  # łamanie wierszy bez znaczenia
    # Assert
    assert 'class="fill"' in regula and "nie blokują meldunku" in regula
    assert "TLDR" in regula and "krok 11" in regula
    assert "inne błędy kontroli blokują" in regula
    assert "do uzupełnienia" in krok11


def test_weryfikuj_cytaty_sprawdza_sumy_plikow_z_briefu():
    # Arrange
    tekst = (AGENCI / "weryfikuj-cytaty.md").read_text(encoding="utf-8")
    # Assert
    assert "BRIEF.md" in tekst and "sha256sum" in tekst
    assert "Bash" in _frontmatter(tekst)["tools"]


def test_napisz_pismo_zna_dokladnie_te_znaczniki_ktore_przepuszcza_walidacja():
    # Arrange — lista agenta nie może się rozjechać z kodem: agent pisze tresc.html bez zaglądania do skryptu
    agent = (AGENCI / "napisz-pismo.md").read_text(encoding="utf-8")
    # Act
    wiersz = re.search(r"Dozwolone znaczniki:([^;]+);", agent)
    # Assert
    assert wiersz, "agent nie wymienia dozwolonych znaczników"
    assert set(re.findall(r"`(\w+)`", wiersz.group(1))) == DOZWOLONE_ZNACZNIKI
    assert "jedyny atrybut: `class`" in agent


def test_napisz_pismo_wie_jak_zapisac_adres_url_e_mail_i_znaki_specjalne():
    # Arrange
    agent = (AGENCI / "napisz-pismo.md").read_text(encoding="utf-8")
    # Assert
    assert 'zwykły tekst' in agent and '<span class="mono">' in agent
    assert "&lt;" in agent and "&gt;" in agent and "&amp;" in agent


def test_pismo_odsyla_blad_niedozwolonego_html_do_agenta_raz_a_potem_pyta_usera():
    # Arrange
    _, tresc = _skill("pismo")
    # Act
    krok = _sekcja(tresc, 6)
    blad = " ".join(krok[krok.index("niedozwolony HTML"):].split())  # łamanie wierszy bez znaczenia
    # Assert
    assert "napisz-pismo" in blad and "poprawkę techniczną" in blad
    assert "nie liczy się do rundy z kroku 8" in blad
    assert "nie edytuj `tresc.html` sam" in blad
    assert "Najwyżej jedna" in blad and "AskUserQuestion" in blad


def test_dowod_raport_nazywa_adresy_bez_identyfikatora_a_nie_bez_parametrow():
    # Arrange — `czysty_url` to też strona docelowa przekierowania, więc „bez parametrów” opisuje go błędnie
    _, tresc = _skill("dowod")
    # Act
    raport = _sekcja(tresc, 11)
    # Assert
    assert "adresy stron bez identyfikatora: <e>" in raport
    assert "adresy bez parametrów" not in raport
