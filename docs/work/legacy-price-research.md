# Research: modernisering av den äldre prisberäkningen

**Kontrollerad:** 2026-11-18, cirka 15:28 +01:00  
**Fas:** Research; ingen källkod eller test ändrad

## Nuvarande beteende – karakteriseringsunderlag

Källa: `src/legacy/price_calc.py` (funktioner för prisberäkning och CLI).

1. Radbeloppen räknas som `quantity * unit_price` med `Decimal` och summeras.
2. Om en order har en rabattkod och en motsvarande rad finns i `discounts`, dras `summa * percent / 100` från summan.
3. Nettot kapas till två decimaler med `_kapa(x) = Decimal(int(x * 100)) / 100`. `int` trunkerar mot noll, inte vanlig avrundning.
4. Moms beräknas som 25 % av det redan trunkerade nettot och kapas separat med samma regel.
5. Totalen är den trunkerade netto- och momssumman adderad. `valid_from` och `valid_to` används inte; rabattens giltighet och procentintervall valideras inte.

Exempel från fiktiv seed-data (`db/seed.sql`):

- Order 1042: `2 × 375 + 200 = 950`; netto 950, moms 237,5, total 1187,5.
- Order 1044: 199,90 med 10 % rabatt → netto 179,91; moms 44,9775 → 44,97 efter trunkering; total 224,88.
- Order 1045: 649 med 15 % rabatt → netto 551,65; moms 137,9125 → 137,91; total 689,56. Seedens rabatt är utgången relativt rapportens datum men tillämpas ändå.

Mätning med ren `Decimal`-beräkning av 1042 gav `str`-värdena `"950"`, `"237.5"` och `"1187.5"`, inte alltid två decimaler. För 1044/1045 råkade serialiserade tal ha två decimaler. Detta skiljer sig från standardens önskan om strängar med två decimaler; ett formateringsbyte skulle ändra API-/CLI-beteende och måste därför uttryckligen beslutas samt karakteriseras.

**Moderniseringsregel:** Bevara först befintliga pris-, rabatt-, moms- och trunkeringsregler. Ändra inte giltighetsdatum, avrundning eller format utan ett separat beslut/teststöd.

## Säkerhets- och driftsrisker

- `price_calc.py` har tre SQL-frågor med stränginterpolering. Rabattkod hämtas ur DB och interpoleras inuti SQL-citattecken. Ordertjänsten accepterar strängar i `discountCode` och lagrar värdet parametriserat, så API-värdet kan nå den interpolerade rabattfrågan. Order-ID interpoleras också; CLI:t konverterar argumentet med `int`, men den importerbara funktionen validerar inte ID:t själv.
- `jobs/nightly_report.py` interpolerar datumargument i SQL.
- `price_calc.py` läser endast `DATABASE_URL` (fallback till utvecklingsdatabasens URL) och skapar en global psycopg-anslutning med `autocommit=True` vid import. Import kräver alltså fungerande anslutning; anslutningen stängs inte av modulen. Testisolering är känslig för när miljövariabler sätts.
- Pris-/DB-undantag hanteras inte i Python. Loggning fångar brett undantag med `except: pass`; loggfilen ligger bredvid källan och inkluderar tid, order-ID och total. Loggfel tystas.
- `src/pricing/legacyPrice.ts` mappar alla subprocessfel till `not_found`/404 och saknar skyddad JSON-parsning. Interpreterfel, DB-fel eller felaktig stdout kan således se ut som att order saknas.
- `nightly_report.py` läser `p.total` utan att kontrollera om `calc_price` returnerade `None`.
- Inga hemligheter eller verkliga personuppgifter återges i denna rapport.

## Windows-404: verifierade fakta och hypotes

**Verifierat lokalt:** `Get-Command` hittade `python3.exe` och `python.exe` som Microsoft Store-appalias; `python3 --version` och `python --version` rapporterade att Python inte hittades. `py` saknades. En ofarlig Node `execFile("python3", ["--version"])`-kontroll gav exitkod 1 och felkod 9009. Projektets `.venv` innehåller Python 3.12.14, pytest 8.3.3 och psycopg 3.2.3. Bryggan använder hårdkodat `"python3"`; ingen interpreterinställning hittades i granskad kod/konfiguration.

**Hypotes med starkt stöd, ej bekräftad som endpointkörning här:** På denna Windows-miljö kan bryggan misslyckas med att starta `python3`; dess felmappning kan då svara 404 för `GET /orders/:id/price`. Detta stämmer med tidigare Jest-resultat 404 i stället för 200. Researchern körde inte om endpointtestet, så det är inte en ny reproduction av HTTP-resultatet. Portabel interpreterupplösning behöver beslutas i planen; den ska inte ändra affärslogik.

## Teststatus och isolering

- Ingen fristående `test_*.py`-fil hittades i `tests/`; pytest-konfigurationen söker där efter `test_*.py`. Befintligt pris-endpointstest finns i `tests/orders.test.ts` och verifierar status 200 och numerisk total 1187.5, inte detaljerna i Python-beteendet.
- Testsetupen i Jest sätter `DATABASE_URL` från `TEST_DATABASE_URL`; pytest använder inte automatiskt denna setup. Python-test måste ställa in en isolerad test-URL innan modulimport, eller injicera/mocka DB-gränsen innan import.
- Researchern körde inte `npm test`, `pytest`, DB-reset eller databastest. `db/schema.sql` börjar med `DROP TABLE`; ingen reset utfördes.
- Tillgänglig pytest-miljö verifierades med `.venv`-pytest `--version`; ingen testsvit kördes.

## Faktiska kontroller (Research)

Researcher läste `README.md`, `docs/standard.md`, `docs/api.md`, `docs/rigg.md`, legacy-modulen, nattjobbet, TypeScript-bryggan, orderroute/-service, TS-tester, pytest-konfiguration, schema och seed-data. Kördes även `git status --short --branch`, filinventering, interpreterkontroller (`python3`, `python`, `py`, `.venv`), Node `execFile`-probe samt ren Decimal-beräkning med endast syntetiska seed-värden. Inga applikationskommandon eller databasprocesser startades. Worktree-ändringarna `package-lock.json` och `sessions/last-state.md` lämnades orörda.

## Öppna beslut

- Hur lösa interpretervalet portabelt (konfigurerbar executable, aktiv venv/`process.execPath`-ekvivalent, eller miljövariabel) utan att bygga in en maskinspecifik sökväg.
- Hur karakteriseringstester säkert isolerar DB före import.
- Om JSON-prisbelopp ska förbli nuvarande `str(Decimal)`-format eller senare standardiseras till två decimaler; moderniseringens första steg ska låsa befintligt format.
- Rabattgiltighetsdatum saknas i nuvarande beräkning; att börja tillämpa dem är beteendeförändring och ingår inte utan beslut.
