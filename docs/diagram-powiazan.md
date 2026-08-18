# Prompt: diagram powiązań kruczek

Poniższy prompt generuje diagram Mermaid pokazujący relacje między komendami, skillami, subagentami i skryptami pluginu kruczek.

---

## Prompt do wklejenia w Claude

```
Wygeneruj diagram Mermaid (flowchart LR) pokazujący powiązania w pluginie kruczek.

Zasady:
- Root (punkt wejścia użytkownika) to każda komenda /kruczek:<nazwa>
- Strzałki pokazują: co dana komenda triggeruje (skill, subagent, skrypt)
- Subagenci oznaczeni kształtem równoległoboku (["nazwa"])
- Skille oznaczone kształtem zaokrąglonym ((nazwa))
- Skrypty oznaczone kształtem cylindra [(nazwa)]
- Komendy oznaczone prostokątem [nazwa]
- Grupuj w subgraphy: KOMENDY, SKILLE, SUBAGENCI, SKRYPTY

Dane do zmapowania (z /kruczek:komendy):

KOMENDY i co wyzwalają:
- /init-projekt → skill:init-projekt → skrypt:init-projekt.sh
- /nowa-sprawa → skill:nowa-sprawa, skill:konwencje-teczki → skrypt:nowa-sprawa.sh
- /dowod → skill:dowod, skill:konwencje-teczki → agent:archiwista, agent:transkryber → skrypt:manifest.py, skrypt:eml-forensics.py
- /chronologia → skill:chronologia → agent:kronikarz
- /status → skill:status
- /baza-wiedzy → skill:baza-wiedzy, skill:zrodla-prawa, skill:zrodla-orzecznictwa
- /pismo → skill:pismo, skill:redagowanie-pism, skill:konwencje-teczki → agent:redaktor-pism, agent:zrodlo-prawa, agent:researcher-orzecznictwa → skrypt:build-pismo.py
- /kontrola → skill:kontrola → agent:kontroler-zalacznikow → skrypt:kontrola-pisma.py
- /weryfikuj → skill:weryfikuj → agent:weryfikator-cytatow → skill:zrodla-prawa, skill:zrodla-orzecznictwa
- /recenzja → skill:recenzja → agent:recenzent
- /eskalacja → skill:eskalacja

SKILLE WIEDZY (ładowane automatycznie przez kontekst, nie przez komendę):
- analiza-eml → agent:forensyk-spamu → skrypt:eml-forensics.py
- zrodla-dns-poczta → skrypt:dns.sh
- zrodla-rejestry → skrypt:podmiot.sh
- ocr-transkrypcja → agent:transkryber
- fallback-przegladarka (brak subagenta)
- zrodla-prawa → skrypt:eli.sh
- zrodla-orzecznictwa → skrypt:orzecznictwo.sh

Użyj validate_and_render_mermaid_diagram do walidacji przed pokazaniem.
```

---

## Jak wyświetlić diagram

- **VS Code** — rozszerzenie [Markdown Preview Mermaid Support](https://marketplace.visualstudio.com/items?itemName=bierner.markdown-mermaid), potem `Cmd+Shift+V`
- **GitHub** — renderuje automatycznie w podglądzie pliku `.md`
- **Online** — wklej kod diagramu na [mermaid.live](https://mermaid.live) (eksport PNG/SVG)
- **Claude Code** — agent `mermaid-diagram-specialist` może wygenerować zaktualizowaną wersję na podstawie promptu wyżej

---

## Diagram

```mermaid
flowchart LR
  subgraph KOMENDY
    cmd_init["/init-projekt"]
    cmd_nowa["/nowa-sprawa"]
    cmd_dowod["/dowod"]
    cmd_chron["/chronologia"]
    cmd_status["/status"]
    cmd_baza["/baza-wiedzy"]
    cmd_pismo["/pismo"]
    cmd_kontrola["/kontrola"]
    cmd_weryfikuj["/weryfikuj"]
    cmd_recenzja["/recenzja"]
    cmd_eskalacja["/eskalacja"]
  end

  subgraph SKILLE
    sk_init((init-projekt))
    sk_nowa((nowa-sprawa))
    sk_dowod((dowod))
    sk_chron((chronologia))
    sk_status((status))
    sk_baza((baza-wiedzy))
    sk_pismo((pismo))
    sk_kontrola((kontrola))
    sk_weryfikuj((weryfikuj))
    sk_recenzja((recenzja))
    sk_eskalacja((eskalacja))
    sk_konwencje((konwencje-teczki))
    sk_redagowanie((redagowanie-pism))
    sk_prawo((zrodla-prawa))
    sk_orzecznictwo((zrodla-orzecznictwa))
    sk_rejestry((zrodla-rejestry))
    sk_analiza_eml((analiza-eml))
    sk_dns((zrodla-dns-poczta))
    sk_ocr((ocr-transkrypcja))
    sk_fallback((fallback-przegladarka))
  end

  subgraph SUBAGENCI
    ag_archiwista[/archiwista/]
    ag_transkryber[/transkryber/]
    ag_kronikarz[/kronikarz/]
    ag_forensyk[/forensyk-spamu/]
    ag_ustalacz[/ustalacz-podmiotu/]
    ag_kontroler[/kontroler-zalacznikow/]
    ag_redaktor[/redaktor-pism/]
    ag_zrodlo[/zrodlo-prawa/]
    ag_researcher[/researcher-orzecznictwa/]
    ag_weryfikator[/weryfikator-cytatow/]
    ag_recenzent[/recenzent/]
  end

  subgraph SKRYPTY
    sc_init[(init-projekt.sh)]
    sc_nowa[(nowa-sprawa.sh)]
    sc_eml[(eml-forensics.py)]
    sc_manifest[(manifest.py)]
    sc_eli[(eli.sh)]
    sc_orzecznictwo[(orzecznictwo.sh)]
    sc_podmiot[(podmiot.sh)]
    sc_dns[(dns.sh)]
    sc_build[(build-pismo.py)]
    sc_kontrola[(kontrola-pisma.py)]
  end

  cmd_init --> sk_init --> sc_init
  cmd_nowa --> sk_nowa & sk_konwencje --> sc_nowa
  cmd_dowod --> sk_dowod & sk_konwencje --> ag_archiwista & ag_transkryber
  ag_archiwista --> sc_manifest
  ag_transkryber --> sc_eml
  cmd_chron --> sk_chron --> ag_kronikarz
  cmd_status --> sk_status
  cmd_baza --> sk_baza & sk_prawo & sk_orzecznictwo
  cmd_pismo --> sk_pismo & sk_redagowanie & sk_konwencje --> ag_redaktor & ag_zrodlo & ag_researcher --> sc_build
  ag_zrodlo --> sc_eli
  ag_researcher --> sc_orzecznictwo
  cmd_kontrola --> sk_kontrola --> ag_kontroler --> sc_kontrola
  cmd_weryfikuj --> sk_weryfikuj --> ag_weryfikator --> sk_prawo & sk_orzecznictwo
  cmd_recenzja --> sk_recenzja --> ag_recenzent
  cmd_eskalacja --> sk_eskalacja

  sk_analiza_eml --> ag_forensyk --> sc_eml
  sk_dns --> sc_dns
  sk_rejestry --> ag_ustalacz --> sc_podmiot
  sk_ocr --> ag_transkryber
  sk_prawo --> sc_eli
  sk_orzecznictwo --> sc_orzecznictwo
```
