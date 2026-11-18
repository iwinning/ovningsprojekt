# Oberoende Fas 4-review: orderavbokning

**Status:** Granskningen är färdig. Implementationen lämnades orörd. Endast denna granskningsrapport skapas/uppdateras.
**Granskad omfattning:** `docs/standard.md`, feature-plan/build, ADR 0001, commits `656508f` och `20700fa`, samt avbokningsroute, tjänst, API-dokumentation, schema, auth/HTTP-hjälpare och `tests/orders.test.ts`.

## Bekräftat fynd

### [P2 – medel] Oväntade DB-fel i avbokningsrouten fångas inte av Express 4

- **Plats:** `src/routes/orders.ts:45-52` (särskilt rad 51); fel återkastas i `src/services/orderService.ts:150-152`. `src/app.ts:5-13` saknar error-middleware. `package.json` anger Express `^4.22.3`.
- **Evidens/reproduktion:** Om `db.connect()` eller en fråga i `cancelOrder` avvisas (t.ex. databasanslutningen bryts), fångar tjänsten felet, försöker `ROLLBACK` och kastar sedan felet vidare. Den nya async-route-handlern anropar/awaitar tjänsten utan `try/catch`, `next(err)` eller async-wrapper. Express 4 vidarebefordrar inte automatiskt avvisade Promise från async-handlers till felhanterarmiddleware. Det kan därför bli en ohanterad Promise-rejektion i stället för ett kontrollerat HTTP 500-svar; med den angivna Node-versionen kan ohanterad rejektion även avsluta processen. Ingen global felhanterare hittades i appen.
- **Konsekvens:** Tillfälliga DB-fel hanteras inte som ett kontrollerat API-fel och kan påverka processens tillgänglighet.
- **Rekommendation:** Fånga route-felet och skicka det till `next(err)` (eller använd en Express-4-kompatibel async-wrapper), och installera central felhantering som returnerar ett generiskt 500-svar. Logga inte personuppgifter eller hemligheter.

## Övriga kontrollpunkter

- SQL för avbokningen använder `$1`/`$2`-parametrar; inga interpolerade requestvärden hittades.
- Kund-ID hämtas via `requireCustomer`/`req.customerId`; tjänsten kontrollerar ägarskap innan ändring. `SELECT ... FOR UPDATE`, statusvillkorad `UPDATE` och transaktionen håller lås och kontrollerar ägarskapet; tid/status hanteras före skrivning.
- Gränsen är inklusive 30 minuter och framtida `created_at` nekas enligt SQL-villkoren. Resultatfel skickas via befintlig `sendResult` med motsvarande 400/403/404/409-kontrakt.
- Ingen N+1-fråga, personlig loggning, hemlighet eller prisavrundningsändring identifierades i den granskade avbokningsändringen. Befintliga ordertester har inte tagits bort eller hoppats över i källan.
- **Testtäckningsbegränsning:** samtidighetstestet täcker två parallella avbokningar, inte en avbokning mot en annan typ av statusändring. Inget separat verifierat fel i låsningen identifierades; detta är en kvarstående täckningsbegränsning, inte ett bekräftat fel i implementationen.

## Teststatus och begränsningar

- **Verify har inte körts.** Inga tester, lint-, typecheck- eller formatkommandon kördes under denna review.
- Enligt `docs/work/feature-build.md` kördes före review: fokuserat avbokningsurval: 11 passerade och 9 filtrerades bort; hela `tests/orders.test.ts`: 19 passerade och 1 misslyckades (det befintliga `GET /orders/:id/price`-testet fick 404 i stället för 200). Buildrapporten beskriver också en tidigare röd körning innan implementationen. Dessa resultat har inte körts om eller verifierats oberoende här.
- Ingen full testsvit, live-databasverifiering, lint, typecheck, formatkontroll eller extern driftkonfiguration granskades/kördes. Reviewen bygger på den begärda diffen, dokumentationen och berörda källfiler.
- **Blockerare:** Reviewen är färdig; det bekräftade felhanteringsfyndet bör åtgärdas före driftsättning. Verify återstår och buildrapportens kända pris-endpoint-fel kvarstår separat.
