---
name: zrodla-dns-poczta
description: "Sprawdzanie rekordów DNS, konfiguracji poczty (SPF, DKIM, DMARC), danych rejestracyjnych domeny i powiązań między domenami. Użyj, gdy trzeba ustalić kto stoi za domeną, kiedy ją założono, czy kilka domen należy do jednego podmiotu albo skąd naprawdę wyszła wiadomość."
when_to_use: Rekordy DNS, MX, SPF, DKIM, DMARC, whois, RDAP, kto ma domenę, kiedy zarejestrowano domenę, czy domeny są powiązane, na jakim hostingu stoi strona, skąd wyszedł mail.
model: haiku
effort: low
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/dns.sh *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/podmiot.sh *)
---

# DNS, poczta i dane domeny

Praca mechaniczna — skrypty odpytują, ty zestawiasz wynik. Nie zgaduj rekordów, nie licz z pamięci.

## Narzędzia

```
${CLAUDE_PLUGIN_ROOT}/scripts/dns.sh rekordy <domena>          A, AAAA, MX, NS, TXT, SOA, CNAME, CAA
${CLAUDE_PLUGIN_ROOT}/scripts/dns.sh poczta  <domena>          MX + SPF + DMARC + typowe selektory DKIM
${CLAUDE_PLUGIN_ROOT}/scripts/dns.sh dkim    <domena> <sel>    konkretny selektor
${CLAUDE_PLUGIN_ROOT}/scripts/dns.sh raport  <domena>          gotowy markdown do ARCHIWUM
${CLAUDE_PLUGIN_ROOT}/scripts/dns.sh porownaj <d1> <d2> …      czy domeny stoją na tej samej infrastrukturze
${CLAUDE_PLUGIN_ROOT}/scripts/podmiot.sh domena <domena>       RDAP: rejestrator, abonent, DATA REJESTRACJI
${CLAUDE_PLUGIN_ROOT}/scripts/podmiot.sh strona <URL>          łańcuch przekierowań HTTP
```

Rozstrzyganie idzie przez DNS-over-HTTPS (dns.google i cloudflare-dns.com) — `dig` i `whois`
nie są potrzebne i zwykle nie są dostępne.

## Co jest wartościowe dowodowo

**Data rejestracji domeny (RDAP).** Najmocniejsze pojedyncze ustalenie techniczne, ale wciąż
poszlaka: domena założona kilka dni przed spornym zdarzeniem może wskazywać, że powstała na
potrzeby jednej akcji. Sama zbieżność dat tego nie przesądza — firmy zakładają domeny również
pod kampanie, rebrandingi i testy. Do pisma wchodzi dopiero w połączeniu z innym ustaleniem
(ten sam podmiot w RDAP, ta sama treść strony, przekierowanie).

**Rozbieżność domeny nadawczej i domeny marki.** Wiadomość podpisana DKIM-em domeny, która nie
prowadzi żadnej działalności i nie ma związku z reklamowaną marką.

**Selektor DKIM z nagłówka wiadomości.** W nagłówku jest `DKIM-Signature: … s=<selektor>; d=<domena>`.
Sprawdź `dns.sh dkim <domena> <selektor>` — potwierdza, że klucz jest opublikowany **w dacie
odczytu**, co jest spójne z tym, że domena pozostaje pod kontrolą podmiotu podpisującego wysyłkę
(często dostawcy mailingu, nie samego nadawcy). Sam odczyt nie mówi nic o stanie z daty
zdarzenia — zapisz raport z datą.

**Brak SPF/DMARC** przy jednoczesnym `dkim=pass` — konfiguracja minimalna, wystarczająca do
przejścia przez filtry. Sama w sobie nie świadczy o zamiarze (najczęstszą przyczyną jest zwykłe
zaniedbanie) — odnotuj jako poszlakę.

**Wspólna infrastruktura.** `dns.sh porownaj` zestawia NS, MX i A kilku domen naraz.

## Granica, której nie przekraczasz

Wspólny hosting, wspólne serwery nazw i sąsiednie adresy IP to **poszlaka, nie dowód**. Ten sam
wynik daje współdzielony hosting dla tysięcy niepowiązanych klientów. Takie ustalenie trafia do
sekcji `⚠ HIPOTEZY` w `index.md`, nigdy do pisma w trybie oznajmującym.

Dowodem staje się dopiero w połączeniu z czymś twardym: tą samą osobą w RDAP, tym samym NIP-em
w stopce, tą samą treścią strony, przekierowaniem jednej domeny na drugą.

## DNS zmienia się w minutę

Rekord istotny dowodowo **zapisz od razu**:

```
dns.sh raport <domena> > <sprawa>/ARCHIWUM/RRRR-MM-DD_dns_<domena>.md
manifest.py sumy <sprawa>
```

Raport zawiera datę i godzinę odczytu oraz kontrolę krzyżową z drugiego rozstrzygacza — to
zabezpiecza przed zarzutem, że odczyt pochodzi z zatrutej pamięci podręcznej. Za miesiąc rekordu
może już nie być, a wtedy nie udowodnisz, że kiedykolwiek istniał.

## Czego te narzędzia nie zrobią

- **Domeny `.eu`** nie mają publicznego RDAP ani WHOIS po HTTP (EURid za anty-botem).
- **Dane abonenta będącego osobą fizyczną** są w RDAP ukryte — zobaczysz rejestratora, nie właściciela.
- **Historii DNS** (jak rekord wyglądał w przeszłości) te API nie dają.

W tych trzech przypadkach przejdź na ścieżkę przeglądarkową — zob. skill `fallback-przegladarka`.
