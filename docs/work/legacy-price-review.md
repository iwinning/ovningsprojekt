# Review: legacy-prisberäkningen

**Datum:** 2026-11-18  
**Fas:** Oberoende Review efter Build. Implementation och testfiler lämnades orörda.  
**Granskare:** Reviewer-agent. Granskningen omfattade diffen `fe87ebe..HEAD`, `docs/standard.md`, plan/buildrapporter och berörda Python-, TypeScript-, route- och testfiler.

## Sammanfattning

Granskningen bekräftade att prislogiken och SQL-parametrisering är bevarade, anslutningarna har explicit livscykel, API-bryggan skiljer saknad order från operativa fel och nattjobbet är uppdaterat.

Förbättringspunkter: nattjobbet utför N+1-frågor; pris-endpointens felstatusar saknar route-specifika integrationstester; repositoryts formateringskontroll misslyckas.

## Fynd

### 1. N+1-frågor i nattjobbet — MEDIUM

- **Plats:** `jobs/nightly_report.py:15–24`; prisfrågorna finns i `src/legacy/price_calc.py:38–57`.
- **Evidens:** `create_report` hämtar betalda order-ID:n och kör sedan `calc_price` en gång per order. Prisberäkningen frågar efter ordern och orderraderna, samt gör en rabattfråga om en rabattkod finns. Det innebär 1 + 2N–3N SQL-frågor per rapport, där N är antalet order.
- **Risk:** Antalet databaserundresor växer linjärt per order och gör rapporten långsammare när mängden betalda order ökar. Detta avviker från `docs/standard.md:11`, som förbjuder att hämta relaterade rader en fråga per rad i loop.
- **Förbättringsförslag:** Hämta prisunderlag i batch och lägg till en kontroll av frågeantalet så att det inte ökar per order.
- **Confidence:** hög.

### 2. Pris-endpointens förväntade felstatusar saknar integrationstesttäckning — LOW

- **Plats:** `tests/orders.test.ts:67–73`; route `src/routes/orders.ts:31–45`.
- **Evidens:** Pris-endpointkontrollen täcker lyckat svar. Route-specifika kontroller för ogiltigt ID (400), saknad autentisering (401), annan kunds order (403) och saknad order (404) saknas. Kontroller för den separata orderdetaljrouten täcker inte statuskontraktet för prisrouten.
- **Risk:** Regressioner i statusmappning eller i att bryggan undviks vid nekad åtkomst kan gå oupptäckta. Granskningen fann inte att själva ägarskapskontrollen saknas: prisrouten anropar `getOrder` före `calcPrice`.
- **Förbättringsförslag:** Lägg till kontroller för dessa fyra statusar och verifiera att Python-bryggan inte körs vid nekad åtkomst.
- **Confidence:** hög.

### 3. Projekttäckande formatkontroll misslyckas — LOW

- **Plats:** bland annat `src/pricing/legacyPrice.ts`, `src/routes/orders.ts` och `tests/legacyPrice.test.ts`.
- **Evidens:** Reviewer-agenten körde `npm run format:check`; Prettier rapporterade 16 TypeScript-filer, däribland ändrade filer. Den riktade Prettier-kontrollen under Build passerade, men ersätter inte den projekttäckande kontrollen.
- **Risk:** CI eller lokal kvalitetskontroll som kräver `format:check` förblir röd.
- **Förbättringsförslag:** Utred konsekvent radsluts-/Prettier-konfiguration eller hantera formatteringen separat; undvik att oavsiktligt formatera orelaterade filer.
- **Confidence:** hög.

## Icke-blockerande risker

- **Databas-URL i fallback:** `src/legacy/price_calc.py:9` innehåller en fallback-URL med inloggningsuppgifter. Den är oförändrad från baseline och introducerades inte av moderniseringen. Överväg att kräva miljökonfiguration i separat ändring. Förekomsten är verifierad; faktisk exponering beror på driftkontext. **Confidence:** hög för förekomsten.
- **Order-ID och belopp i logg:** `src/legacy/price_calc.py:65–68` loggar order-ID och totalbelopp vid lyckad beräkning. Om order-ID kan länkas till kund kan loggen vara integritetskänslig. Granska loggningsbehov, åtkomst och retention. **Confidence:** hög för logginnehåll, medel för personuppgiftsrisk.
- **JSON-prisformat avviker från standard:** `str(Decimal)` bevaras av kompatibilitetsskäl och kan ge exempelvis `"950"` och `"237.5"`; se `src/legacy/price_calc.py:82` och karakteriseringsassertionerna. Detta avviker från `docs/standard.md:25`, som föreskriver två decimaler. Ett formatbyte bör beslutas separat eftersom det ändrar API-beteendet.

## Positiva kontroller

- Prisfrågornas order-ID och rabattkod samt nattjobbets datum är parametriserade. Granskaren fann ingen SQL-stränginterpolering i de granskade Python-frågorna.
- Karakteriseringsfallen omfattar priser, rabatt, moms, trunkering mot noll, JSON-format, negativt belopp och rabatt vars giltighetstid passerat.
- Modulimporten öppnar ingen databasanslutning. Anslutning kan injiceras, och nattjobbet använder en explicit hanterad anslutning.
- Prisrouten kontrollerar ägarskap innan bryggan anropas. Endast exakt saknad-order-JSON med förväntad exitkod mappas till 404; operativa fel går till generiskt HTTP 500. Oväntat asynkront fel i Express 4-route skickas vidare till central felhantering.
- Inga Python- eller nattjobbsflöden gör skrivningar; ingen transaktionsbrist hittades där.
- Testdiffen granskades: tidigare testfall är fortsatt aktiva och ingen befintlig testfil har tagits bort.

## Kontroller körda under Review

| Kontroll | Resultat |
|---|---|
| `.venv` Python-tester | 18/18 godkända |
| Riktade bridge Jest-tester | 15/15 godkända |
| `npm run lint` | Godkänd |
| `npm run typecheck` | Godkänd |
| `npm run format:check` | Underkänd; 16 TypeScript-filer rapporterades |
| Full DB-beroende Jest-svit | Inte omkörd av Reviewer-agenten; Build-loggen dokumenterar 43/43 |
| Databasreset/destruktiv kontroll | Inte körd |

Review bekräftar inte att formatproblemen introducerades av denna ändring; flera rapporterade filer är inte ändrade. Inga implementationer ändrades och ingen commit skapades under Review.
