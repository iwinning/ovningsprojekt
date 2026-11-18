# Plan: avbryta en beställning

**User story:** `docs/user-stories.md`, story 2  
**Planerad:** 2026-11-16  
**Status:** Granskningsbar plan. Ingen implementation, testkörning eller databasändring utförd i planfasen. Stanna före build.

## Föreslaget kontrakt

`POST /orders/:id/cancel`

- Kräver `X-Customer-Id`; route använder `requireCustomer` och tjänsten får kund-ID från `req.customerId`. Ingen request body behövs.
- Vid framgång svarar API:t `200` med `{ "id": 1047, "status": "cancelled" }`.
- Felsvar följer formatet `{ "error": { "code": "...", "message": "..." } }`.

| Villkor | Resultat | HTTP |
|---|---|---:|
| Felaktigt order-ID | `invalid_input` | 400 |
| Saknad inloggning | hanteras av `requireCustomer` | 401 |
| Order saknas | `not_found` | 404 |
| Order ägs av annan kund | `forbidden` | 403 |
| För gammal order, framtida `created_at` eller otillåten status | `conflict` | 409 |

## Föreslagna acceptanskriterier

**Lyckad avbokning**
- **Givet** en inloggad kund som äger en order med status `new`, skapad högst 30 minuter tidigare
- **När** kunden anropar `POST /orders/:id/cancel`
- **Så** svarar API:t `200` med orderns ID och status `cancelled`, och den beständiga orderstatusen ändras.

**Tidsgräns**
- **Givet** en ägd order med status `new` och ålder exakt 30 minuter
- **När** kunden avbryter ordern
- **Så** tillåts avbokningen.
- **Givet** en motsvarande order som är äldre än 30 minuter
- **När** kunden avbryter ordern
- **Så** svarar API:t `409 conflict` och orderstatusen förblir oförändrad.
- En order med framtida `created_at` nekas med `409 conflict`.

**Indata och åtkomst**
- **Givet** ett ogiltigt ID-format
- **När** kunden anropar endpointen
- **Så** svarar API:t `400 invalid_input`.
- **Givet** ett giltigt ID för en order som inte finns
- **När** kunden anropar endpointen
- **Så** svarar API:t `404 not_found`.
- **Givet** en order som tillhör en annan kund
- **När** kunden försöker avbryta den
- **Så** svarar API:t `403 forbidden` och ordern ändras inte.
- **Givet** ett anrop utan inloggad kund
- **När** endpointen anropas
- **Så** svarar API:t `401` via `requireCustomer`.

**Status**
- **Givet** en order vars status inte tillåter avbokning, inklusive en redan avbruten order
- **När** ägaren försöker avbryta den
- **Så** svarar API:t `409 conflict` och ordern ändras inte.

## Beslut för implementationen

Kravet säger inte vilka statusar som får avbrytas eller vad en upprepad avbokning ska ge för svar. Policyn som används för implementationen är att endast tillåta avbokning från `new`, och svara `409 conflict` för `paid`, `shipped` och `cancelled`, även vid upprepade försök. Den ligger i linje med befintliga seed-statusar men är ett affärsbeslut utöver ordalydelsen i user storyn. Användaren bekräftade i sin instruktion att planen ska användas som beslut.

Föreslagen gränstolkning är ålder `<= 30 minuter`; ålder `> 30 minuter` nekas. Beslutet om 403 för en annan kund följer befintligt `getOrder`-mönster.

## Testplan

1. Börja build med test först: lägg till tester utan att ändra befintliga. Kontrollera tjänstens resultat, route-status/svar och beständig status.
2. Täck lyckad avbokning och samtliga kriterier ovan: exakt 30 minuter, strax över gränsen, framtida ordertid, felaktigt ID, saknad order, annan kund, saknad auth, otillåten status och upprepad avbokning.
3. Kontrollera att nekade fall inte ändrar status och att två konkurrerande statusändringar inte kan skriva över varandra.
4. Kör berörda tester först, därefter `npm test`, `npm run typecheck`, `npm run lint` och `npm run format:check`.

### Testa tiden utan väntan

Använd en deterministisk klocka/tidskälla i tjänstelagret, injicerbar endast internt och aldrig från HTTP. I produktion bör tidsvärdet komma från PostgreSQL efter att orderraden har låsts; testerna kan tillhandahålla en fast tid för att prova exakt 30 minuter och tiden precis över gränsen utan `sleep`. Implementationsdesignen måste säkerställa att testklockan och produktionsklockan använder samma jämförelselogik. Bekräfta att detta passar befintlig DB-klient och serviceform innan kod skrivs.

Alternativet är att endast manipulera `created_at` i testdatabasen. Det undviker produktionsinjektion men ger en skör exakt-gränstestning när riktig tid fortsätter gå; därför föredras en kontrollerbar klocka.

## Filer som föreslås ändras

- `src/routes/orders.ts` — lägg till route, återanvänd befintlig ID-validering och `requireCustomer`, skicka resultat via befintlig HTTP-hantering.
- `src/services/orderService.ts` — avboka med ägarskaps-, status- och tidskontroll och returnera förväntade fel som `Result`.
- `tests/orders.test.ts` — lägg till route-/integrationstester för kontrakt, gränsfall och oförändrad status vid fel; behåll alla befintliga tester.
- `docs/api.md` — dokumentera den nya metoden, sökvägen, svaren och felkoderna.

Inga ändringar i `db/schema.sql`, seed-data eller migrations föreslås: den befintliga `TEXT`-kolumnen kan lagra `cancelled`. Om statusbegränsning i databasen senare önskas ska den hanteras separat som en migrering med backningssteg. `src/http.ts` har redan `conflict`-mappning och behöver inte ändras.

## Säkerhet, transaktion och risker

- Ägarskap kontrolleras i tjänstelagret; kund-ID från body/query används inte.
- Lås orderraden inom transaktionen (`SELECT ... FOR UPDATE`) innan tid/status kontrolleras. Hämta DB-tid efter låsning i produktion. Uppdatera villkorat på order, ägare och tillåten status och kontrollera att en rad uppdaterades, så samtidiga ändringar inte kringgår regeln.
- Förväntade fel returneras som `Result`; transaktionen committas endast vid framgång och rullas tillbaka vid fel enligt befintligt projektmönster.
- Tidsgräns, framtida `created_at` och fria statusvärden är centrala felrisker. En migrationsbaserad statusbegränsning vore ett separat, större beslut.
- Rollback av implementationen görs separat från eventuella dataåtgärder. Ingen schemaändring föreslås och redan avbrutna ordrar ska inte automatiskt återställas till `new`.

## ADR-förslag

**Rubrik:** *Avbokningspolicy och tidskälla för orderavbokning*  
**Föreslaget beslut:** Avboka endast order med status `new`; tillåt ålder från 0 till och med 30 minuter; använd PostgreSQL-tid i produktion och en internt injicerbar, deterministisk klocka i tester. Skapa inte ADR-filen förrän policyn är godkänd.

**Alternativ:** Använd applikationsserverns `Date`/klocka direkt. Det är enklare att testa, men kan skilja sig från databasklockan som sätter `created_at`, vilket kan ge fel beslut runt gränsen vid klockdrift. Förslaget föredrar DB-klockan som auktoritativ källa.

## VG-underlag och kontroller

- Researchrapporten är daterad **2026-11-16 23:02 +01:00** och redovisar `npm run typecheck` och `npm run lint` som godkända.
- Inga tester kördes i researchfasen eftersom testernas `beforeEach` kör `resetDb`, vilket tar bort och återskapar tabeller. Ingen databasåterställning utfördes. Inga tester eller kontroller kördes i planfasen.
- Före planeringen fanns redan lokala ändringar i `package-lock.json` och `sessions/last-state.md`; dessa ska bevaras.
- Ouppmätt: implementationstid, nya testresultat, DB/concurrency-resultat och kostnad/tokenåtgång. Samla dem under build/verify; tidsestimat ska inte rapporteras som uppmätt tid.
- Risk-/policybeslut som kräver granskning: tillåtna statusar, upprepad avbokning, exakt gräns och klockkälla.

Det tidigare rapporterade `GET /orders/:id/price`-felet är separat. Ingen rotorsak verifierades här och prisflödet ingår inte i denna plan.

**Fasgräns:** Den ursprungliga planfasen avslutades före build. Beslutet ovan bekräftades därefter av användaren; den efterföljande builden dokumenteras i `docs/work/feature-build.md`.
