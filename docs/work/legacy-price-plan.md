# Plan: modernisering av legacy-prisberäkningen

**Datum:** 2026-11-18  
**Fas:** Plan; ingen kod, databas eller test ändrad eller körd i planfasen.  
**Underlag:** `docs/work/legacy-price-research.md`, `docs/work/legacy-price-codemap.md`, `docs/standard.md`, `docs/rigg.md`, `docs/api.md`.

## Fakta, hypoteser och beslut före byggstart

### Verifierade fakta

- `src/legacy/price_calc.py` använder `Decimal`, trunkerar mot noll till två decimaler och beräknar moms på redan trunkerat netto. Rabattens `valid_from` och `valid_to` ignoreras.
- `str(Decimal)` ger varierande antal decimaler i de serialiserade prisfälten.
- Python-modulen skapar global psycopg-anslutning vid import, interpolerar SQL och tystar loggfel.
- `src/pricing/legacyPrice.ts` använder hårdkodat `python3` och klassar subprocessfel som `not_found`.
- Research körde interpreterprobe men inte API- eller Python-tester. Lokalt fungerade inte `python3`/`python`; projektets `.venv` innehöll Python.
- Pris-endpointens 404 är historisk men rotorsaken har inte bekräftats.
- Ingen verifierad databasförändring behövs för den planerade säkerhets- och livscykelrefaktoreringen.

### Hypotes

Windows-404 kan bero på att `python3` inte startar och att bryggan mappar startfelet till `not_found`/404. Det är ännu inte verifierat genom en ny endpointkörning.

### Byggstartsgater

Före TDD/implementation ska följande beslutas eller verifieras:

1. Bekräfta alla anropare och kompatibilitetskrav för `calc_price` och den importerade `conn`, särskilt nattjobbet.
2. Fastställ interpreterprioritet och override-namn utan maskinspecifika absoluta sökvägar.
3. Fastställ felkontraktet så endast ett giltigt, uttryckligt “order saknas”-svar blir `not_found`; spawn-, DB-, exit- och JSON-fel får inte klassas som saknad order.
4. Verifiera att psycopg-mockens värden motsvarar riktiga returnerade typer för `NUMERIC` och rabattprocent. Rena Python-karakteriseringstester ska inte kräva databas.

## Omfattning

### Ingår

- Lås dagens pris-, rabatt-, moms-, trunkerings-, serialiserings- och CLI-beteende med tester.
- Parametrisera SQL och avlägsna interpolering av order-ID, rabattkod och rapportdatum.
- Avlägsna anslutningens importtidsbiverkning och göra DB-gränsen isolerbar.
- Välj interpreter portabelt och separera order saknas från operativa subprocess-/DB-/JSON-fel.
- Bevara kompatibilitet för både API-bryggan och `jobs/nightly_report.py`.

### Ingår inte utan separat beslut

- Ändra giltighetsregler för rabatter, avrundning/trunkering, momssats eller prisfältens format.
- Ändra order-API:ets behörighetsregler eller andra orderbeteenden.
- Ändra schema, seed eller lägga till migration utan verifierat databehov.
- Omforma nattjobbet utöver vad som krävs för samma DB-livscykel och kontrollerade fel.
- Flytta beräkningslogiken från Python till TypeScript.

## Givet/När/Så — acceptanskriterier

### Bevara affärsbeteende

- **Givet** identiska orderrader och rabattdata från karakteriseringsfallen  
  **När** priset beräknas  
  **Så** returneras samma `Decimal`-värden, inklusive trunkering mot noll och moms beräknad på redan trunkerat netto.

- **Givet** ett `Decimal` vars textrepresentation saknar fasta två decimaler  
  **När** CLI:t serialiserar priset  
  **Så** JSON-strängen matchar nuvarande `str(Decimal)`-format tills en separat formatändring godkänts.

- **Givet** en rabattkod med passerat `valid_to`  
  **När** priset beräknas  
  **Så** rabatten tillämpas fortsatt enligt nuvarande beteende.

### SQL och import

- **Givet** order-ID, rabattkod eller datum som indata  
  **När** SQL körs  
  **Så** skickas värden som parametrar, aldrig inbyggda i SQL-strängen.

- **Givet** en testmiljö utan databasanslutning och fake psycopg-gräns installerad före modulimport  
  **När** prismodulen importeras  
  **Så** öppnas ingen anslutning och modulen kan testas utan DB.

### Felkontrakt och portabilitet

- **Givet** ett giltigt CLI-svar som uttryckligen anger att ordern saknas  
  **När** TypeScript-bryggan hanterar det  
  **Så** mappas det till `not_found`.

- **Givet** interpreter-startfel, oväntad exitkod, DB-fel eller ogiltig JSON  
  **När** bryggan hanterar felet  
  **Så** rapporteras det inte som `not_found`, och intern feltext, stderr, SQL eller credentials exponeras inte i HTTP-svar.

- **Givet** en inloggad kund som äger en order och en fungerande interpreter/DB  
  **När** pris-endpointen anropas  
  **Så** bevaras nuvarande prisfält och belopp.

- **Givet** en saknad order eller en order som ägs av annan kund  
  **När** pris-endpointen anropas  
  **Så** bevaras route-/ägarskapsresultatet och ett subprocessfel misstas inte för saknad order.

## Karakteriseringstester

Skapa rena Python-tester med syntetiska värden och fake DB. Lås både numeriska resultat och CLI-strängar där det anges.

1. **Utan rabatt, varierande Decimal-skala**  
   Rader: `(2, Decimal("375.00"))`, `(1, Decimal("200.00"))`.  
   Förväntat: `net=Decimal("950")`, `vat=Decimal("237.5")`, `total=Decimal("1187.5")`; JSON-strängar `"950"`, `"237.5"`, `"1187.5"`.

2. **Rabatt och separat trunkering av moms**  
   Rad `(1, Decimal("199.90"))`, rabatt 10 %.  
   Förväntat: netto `179.91`, moms `44.97` efter trunkering av `44.9775`, total `224.88`; JSON-strängarna matchar dessa representationer.

3. **Utgången rabatt fortsätter tillämpas**  
   Rad `(1, Decimal("649.00"))`, rabatt 15 %, `valid_to` före testdatum.  
   Förväntat: netto `551.65`, moms `137.91` efter trunkering, total `689.56`; datum ignoreras.

4. **Trunkering mot noll, inte avrundning**  
   `_kapa(Decimal("1.239")) == Decimal("1.23")` och `_kapa(Decimal("-1.239")) == Decimal("-1.23")`.  
   Detta karakteriserar nuvarande funktion; testet inför inte ny valideringsregel.

5. **Negativt belopp genom hela kedjan**  
   Fake rad ger `Decimal("-1.239")`, ingen rabatt.  
   Förväntat: netto `-1.23`, moms `-0.3`, total `-1.53`; JSON-strängar `"-1.23"`, `"-0.3"`, `"-1.53"`.

6. **Order saknas**  
   Första orderfrågan returnerar ingen rad.  
   Förväntat: `calc_price` returnerar `None`; CLI skriver `{"error": "finns inte"}` följt av newline och exitkod 1. Endast detta giltiga saknas-order-svar får mappas till `not_found`.

7. **Tomma rader/ingen matchande rabatt**  
   Order finns, inga rader, rabattkod finns men rabattfrågan returnerar ingen rad.  
   Förväntat: netto, moms och total `Decimal("0")`; JSON-strängarna `"0"`, `"0"`, `"0"`.

Seedordrarna 1042/1044/1045 är ytterligare syntetiska kontrollvärden, inte krav på att rena tester startar DB.

## DB-isolering och fixtures

- Innan Python-modulen importeras: ställ in en explicit test-`DATABASE_URL` och placera en fake `psycopg`-/connection-gräns i `sys.modules`, så kan testerna inte öppna en verklig anslutning.
- Efter att importen gjorts biverkningsfri ska importtestet dessutom verifiera att `connect` inte anropas.
- Cursor/fake-DB ger deterministiska rader och kontrollerar SQL samt parameterlistor separat. Testet ska inte kräva verklig testdatabas för prislogik.
- CLI-testet använder kontrollerade argument och fake DB; ingen schema-reset.
- TypeScript-bryggtester mockar `node:child_process` före import av bryggan och provar separat success, explicit not-found JSON, spawnfel, annan exitkod, stderr och korrupt stdout.
- Endpointintegration mot DB får köras först efter att `TEST_DATABASE_URL` verifierats, resetbeteendet granskats och test-DB-isolering bekräftats. `db/schema.sql` innehåller `DROP TABLE`; ingen reset i planfasen.

## Windows interpreter och 404-verifiering

**Förslag:** stöd en valfri `LEGACY_PYTHON`-override. Om den saknas, prova projektets venv med plattformsanpassad relativ path (`.venv/Scripts/python.exe` i Windows, `.venv/bin/python` på POSIX), därefter dokumenterade PATH-kandidater. Ingen absolut användarspecifik sökväg.

**Alternativ:** hårdkodat `python3` är enklast men felar i undersökt Windows-miljö. Enbart `python` eller Microsoft Store-alias löste inte det observerade läget. Enbart env-variabel är flexibel men kräver lokal konfiguration och kan lämnas oinställd. Venv först med explicit override föreslås; valet måste bekräftas vid byggstart.

**Verifieringsordning:**

1. Interpreterresolver-enhetstest och ofarlig `--version`-probe via exakt vald executable.
2. Mockade bryggtester för `ENOENT`/spawnfel, giltigt exit 1 med exakt saknad-order-JSON, annan exitkod/DB-fel och felaktig stdout. Endast explicit saknad-order-resultat ger `not_found`.
3. Python-karakteriseringstester med fake DB.
4. Efter godkännande av isolering: endpointtest mot testdatabasen, redovisa HTTP-status, executable, spawn-/exitkod, stdout och stderr separat.
5. Jämför med historisk 404; även om problemet kvarstår, undersök route, ägarskap och testmiljö innan rotorsak påstås.

Researchens interpreterprobe lyckades inte köra `python3`; den bekräftar inte ensam hela HTTP-404-flödet.

## Små testdrivna steg och föreslagen commitordning

Varje steg börjar med relevanta tester, gör minsta ändring, kör berörda tester gröna och kontrollerar diff/testintegritet. Kör gröna relevanta tester efter varje steg. Skapa inte en commit med avsiktligt rött arbetsläge.

1. **Karakterisering/fixtures** — skapa Python-fallen ovan och mockade bryggfelstester. För importbiverkningsfallet: gör den testade importgränsen safe/mockad så testet karakteriserar nuvarande beräkningsbeteende utan att kontakta DB.  
   Commitförslag: `test: characterize legacy price behavior`.
2. **Parametriserad SQL** — skriv först tester för order-ID, rabattkod och batchdatum som parametrar; parametrisera Python-frågorna och minsta nödvändiga indatahantering utan prisändring.  
   Commitförslag: `fix: parameterize legacy pricing queries`.
3. **DB-livscykel/import** — testa import utan anslutning och fake-connection injektion; ta bort global importanslutning och uppdatera nattjobbet att använda hanterad anslutning. Säkerställ stängning vid fel.  
   Commitförslag: `refactor: isolate legacy pricing database access`.
4. **Interpreter och subprocessfel** — testa prioritering/kandidater och felklasser; implementera resolver och skilj saknad order från operativa fel.  
   Commitförslag: `fix: resolve legacy Python portably and classify failures`.
5. **Integration/regression** — uppdatera endpointassertioner vid behov, bevara samtliga gamla tester; kör API-regression efter att test-DB bekräftats.  
   Commitförslag: `test: verify legacy price endpoint behavior`.

Efter varje commit: notera kommando, resultat och testantal; kontrollera `git diff -- tests/` så inga tester tagits bort eller inaktiverats. Senare full verify-ordning: Python-tester, mockade TS-bryggtester, godkända DB-endpointtester, `npm test`, `npm run test:legacy`, `npm run typecheck`, `npm run lint`, `npm run format:check`.

## Säkerhet, felhantering och loggning

- Parametrisera all Python-/TypeScript-SQL: separat args för order-ID, rabattkod och datum.
- Validera importerbart order-ID där gränsen kräver; CLI-konvertering ensam skyddar inte direkt funktionsanrop.
- Separera förväntad saknad order från DB-/interpreter-/JSON-fel. HTTP-svar får inte innehålla stderr, SQL, anslutningsdetaljer eller hemligheter.
- Ta bort global anslutning vid import; använd explicit anslutningslivscykel och stäng resursen deterministiskt för API- och batchkonsumenter.
- Ersätt tyst brett `except: pass` med begränsad felhantering. Logga inte rabattkod, personuppgifter, credentials eller subprocessmiljö. Bedöm nödvändig diagnostik och filplacering.
- Nattjobbet ska inte dereferera `None` vid prisfel; fel ska ge kontrollerad jobbfelväg/exitstatus.
- Ingen pris-/rabatt-/momslogik ändras i säkerhetsstegen.

## DB expand/contract om verifierat behov uppstår

**Nuvarande beslut: ingen migration.** Befintligt `NUMERIC` räcker för planerad refaktorering och ingen verifierad schemaändring behövs.

Om separat krav senare visar DB-behov: gör en ny migrationplan och granska före implementation. Reversibel expand/contract:

1. **Expand:** lägg till kompatibel/additiv struktur, behåll befintlig kolumn/läsning.
2. Deploya kod som kan läsa gammal och ny struktur.
3. Backfilla; verifiera antal/rimlighet med reversibla kontrollfrågor.
4. Växla skrivning/läsning först när båda är kompatibla.
5. **Contract:** ta bort gammal struktur först efter att alla konsumenter migrerats och rollbackfönster passerat.
6. Rollback återställer kod först; behåll gammal struktur/data under rollbackfönstret.

Ingen migration eller schemaändring ingår i denna plan.

## Framtida filer som kan beröras

- `src/legacy/price_calc.py` — parametriserad SQL, biverkningsfri import, kontrollerad anslutning och fel-/logghantering.
- `src/pricing/legacyPrice.ts` — portabel interpreterupplösning och korrekt subprocess-/JSON-felklassning.
- `jobs/nightly_report.py` — kompatibel DB-livscykel, parametriserat datum och kontrollerat prisfel.
- `tests/test_price_calc.py` — Python-karakteriserings-, isolerings- och SQL-parametertester.
- `tests/legacyPrice.test.ts` — mockad interpreterresolver/brygga/felklassning.
- `tests/orders.test.ts` — endpointregression vid behov; befintliga tester behålls.
- `README.md` — dokumentera interpreter-overridens namn om `LEGACY_PYTHON` väljs.

Ej planerat: `db/schema.sql`, `db/seed.sql`, migrationsfiler, testdatabas-reset, kund-/orderpriser utanför legacyflödet.

## Risker, rollback och alternativ

- Decimal- eller serialiseringsändring riskerar API-beteendeskifte. Mitigering: exakta karakteriseringsassertioner; formatändring kräver separat beslut.
- Att ta bort global anslutning utan att migrera nattjobbet bryter batchkonsumenten. Mitigering: uppdatera och testa båda anroparna i samma livscykelsteg.
- Interpreterfel kan fortsätta maskeras som 404. Mitigering: separata mockade spawn-/exit-/JSON-fall.
- Fel DB-reset kan förstöra data. Mitigering: rena fake-DB-tester först; verifiera test-URL innan reset; aldrig köra reset mot utvecklings-/produktions-DB.
- Rollback: backa separata commits i omvänd ordning och behåll karakteriseringstester. Interpreteroverride kan stödja återställning men återgå inte till att kalla alla fel `not_found`.
- Alternativ: behåll global anslutning och mocka endast import i tester — mindre förändring men lämnar importbiverkning och skör jobbisolering. Att flytta all prislogik till TypeScript är större beteenderisk, rekommenderas inte före stabil karakterisering.
- Jämför test-först stegvis refaktorering mot en samlad refaktor före test: tid per steg, fel fångade, resultat, rollbackbarhet och antal regressionsloopar.

## VG-mätpunkter

Registrera framtida uppmätta fakta i build/verify, inte uppskattningar:

- aktiv arbetstid per fas och commit;
- testantal före/efter, körda/pass/fail och exakta kommandon/exitkoder;
- om/hur ofta testdatabas reset kördes och bevis på isolering;
- token/kostnad endast om tillgängligt i verktyget, annars markera ej tillgängligt;
- konkreta före/efter kontroller för SQL-interpolering, importanslutning, felklassning, loggning och interpreterval;
- stegvis test-först jämfört med samlad refaktor enligt tid, funna fel, testresultat och rollbackbarhet.

Research rapporterade kontroller cirka 15:28 +01:00 2026-11-18. Implementationstid, testantal/resultat och kostnad är inte uppmätta ännu.

**Stoppvillkor:** Detta är en plan för granskning. Kör inga tester, starta ingen TDD/implementation och gör ingen DB-ändring förrän byggstart, interpreterstrategi, felkontrakt och testisolering har granskats och beslutats.
