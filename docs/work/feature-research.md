# Research: avbryta en beställning

**User story:** `docs/user-stories.md`, story 2  
**Kontrollerad:** 2026-11-16 23:02 +01:00  
**Fas:** Research; ingen implementation utförd

## Nuvarande beteende

- `docs/api.md` beskriver inget avboknings-endpoint. `src/routes/orders.ts` hanterar skapande, hämtning och prisberäkning.
- `db/schema.sql` definierar `orders.status` som fri `TEXT` med standardvärdet `new`; det finns ingen statusbegränsning. `created_at` är `TIMESTAMPTZ NOT NULL DEFAULT now()`.
- `db/seed.sql` använder statusarna `new`, `paid`, `shipped` och `cancelled`. Förekomsten av `cancelled` i seed-data innebär inte i sig att en tillåten övergång är definierad.
- `createOrder` låter databasen sätta status och `created_at`. Orderobjektet från `getOrder` innehåller inte `created_at`; `listOrdersForCustomer` returnerar däremot `createdAt` från `created_at`.
- Orderroutes använder `requireCustomer`, som tar kund-ID från `X-Customer-Id`. `getOrder` kontrollerar i tjänstelagret att beställningen tillhör kunden och returnerar `forbidden` vid ägarskapskonflikt. Inloggningen är förenklad, inte tokenbaserad.
- Tjänster använder `Result`/`err`; `sendError` mappar `invalid_input`, `forbidden`, `not_found` och `conflict` till HTTP 400, 403, 404 och 409. `requireCustomer` svarar med 401. `createOrder` är ett befintligt exempel på transaktionshantering.
- `tests/orders.test.ts` täcker bland annat skapande, validering, auth, ägarskap och hämtning, men inte avbokning, tidsgräns eller statusövergång. `tests/helpers/db.ts` återställer schema och testdata före varje test.
- Inga separata migrationsfiler hittades i den spårade strukturen. Schemat ligger i `db/schema.sql` och återställs av `scripts/db-reset.ts`.

## Förändringar som sannolikt behövs

Planen behöver ta ställning till ett nytt route och en serviceoperation. Tjänstelagret behöver kunna läsa orderns skapandetid och status, kontrollera ägarskap, tidsfönster och tillåten status samt uttrycka förväntade fel som `Result`. `docs/api.md` behöver beskriva kontraktet. Nya tester behöver täcka framgång, tid och fel. En schemaändring är inte ännu motiverad; den fria statuskolumnen kan representera `cancelled`, men statusmodellens framtida begränsning ska bedömas separat.

## Hypoteser och öppna beslut

- Det är sannolikt att tjänstelagret måste läsa `created_at` för att avgöra om avbokningen ryms inom 30 minuter; detta beteende finns inte implementerat.
- User storyn anger inte vilka statusar som får avbrytas, vad en upprepad avbokning ska ge för svar, eller om exakt 30 minuter fortfarande är tillåtet.
- Klockkälla och hantering av samtidiga statusändringar behöver beslutas. Det finns inget nuvarande exempel på orderstatusuppdatering.
- Om kravet tolkas som “inom 30 minuter” är en testbar kandidat att acceptera ålder `<= 30 minuter` och neka ålder `> 30 minuter`; bekräfta gränstolkningen i planen.

## Kontroller som faktiskt utförts

- Lästa dokument: `README.md`, `docs/standard.md`, `docs/api.md` och `docs/user-stories.md`.
- Granskade order-/kundroutes och tjänster, auth/HTTP/Result-kod, `db/schema.sql`, `db/seed.sql`, ordertester och testhjälpare.
- `git status --short --untracked-files=all` visade redan ändrade `package-lock.json` och otrackade `sessions/last-state.md`. De lämnades orörda.
- `npm run typecheck` — godkänd (`tsc --noEmit`, exit code 0).
- `npm run lint` — godkänd (exit code 0).
- Tester kördes inte. `tests/helpers/db.ts` kör `resetDb` i `beforeEach`, vilket kör ett schema som tar bort och återskapar tabeller; ingen databasschemanollställning utfördes.

## Avgränsning

Det tidigare rapporterade felet i `GET /orders/:id/price` är separat från denna user story. Ingen koppling eller grundorsak verifierades i den här researchfasen.
