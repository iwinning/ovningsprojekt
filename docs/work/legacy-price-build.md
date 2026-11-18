# Build: modernisering av legacy-prisberäkningen

**Datum:** 2026-11-18  
**Fas:** TDD och implementation; ingen schemaändring eller databas-migration.  
**Underlag:** `legacy-price-research.md`, `legacy-price-codemap.md`, `legacy-price-plan.md`.

## Resultat

- Prisberäkningens `Decimal`-aritmetik, rabattbeteende, trunkering mot noll, momsberäkning och JSON-strängar är oförändrade och karakteriserade med syntetiska fake-DB-data.
- SQL för order-ID, rabattkod och rapportdatum använder parametrar.
- Import av prisberäknaren öppnar inte längre en databasanslutning. `calc_price` kan använda en injicerad anslutning eller öppna/stänga en egen.
- Nattjobbet använder den hanterade anslutningen, parametriserat rapportdatum och ett kontrollerat fel när en betald order saknar beräknat pris.
- Loggfel fångas snävt och rapporteras med en generell varning utan orderdata eller undantagsdetaljer.
- TypeScript-bryggan väljer `LEGACY_PYTHON`, annars projektets `.venv` om den finns och därefter Python från `PATH`. Bara exitkod 1 med exakt saknad-order-JSON blir `not_found`; spawn-, process-, DB- och JSON-fel går till central, sanerad HTTP 500-hantering.
- Prisrouten vidarebefordrar även oväntade fel från orderuppslagningen till Express-felhanteraren. Det specifika Express 4-felet testades före rättningen.
- Ingen schemaändring behövdes; inga riktiga kunduppgifter användes.

## TDD och separata ändringssteg

1. **Karakterisering:** `tests/test_price_calc.py` använder fake psycopg/DB, täcker pris-, rabatt-, moms-, trunkerings-, JSON- och CLI-beteende. Första körningen: `9 passed`. Commit `efaf844aa8d27e76f90b4046ea035b773a1ad723`.
2. **Parametriserad pris-SQL:** testerna verifierade separat querytext och parametrar; innan ändringen saknades SQL-parametrarna. Efter ändringen: `10 passed`. Commit `babda6656cafbddeff6d45473988ccbc1d442c2c`.
3. **Anslutningslivscykel:** importtestet verifierade att import inte ansluter; anslutning injiceras och nattjobbet använder en hanterad anslutning. Efter ändringen: `12 passed`; `py_compile` passerade. Commit `9aec875d381683e2962be683a73d74f6817f6839`.
4. **Nattjobbsfråga och felväg:** test för rapportdatum som SQL-parameter, summering/format och saknat pris. Efter ändringen: `15 passed`; `py_compile` passerade. Commit `5566205ae38950bd2af87bfa1df44ad0248ca7fc`.
5. **Loggfel:** nytt test gick först rött eftersom filfelet tystades. Efter begränsning till `OSError` och generell varning: Python-sviten `16 passed`. Commit `697d51cf187186bc6bb2c5a76aefc45393caf09`.
6. **CLI-kompatibilitet:** tester låser den faktiska JSON-strängen för Decimal-värden och saknad order, inklusive exitkod 1. Python-sviten därefter: `18 passed`. Commit `b6ae0ceb900b63ad838692fd10905e6a913c4926`.
7. **Portabel Python-brygga:** 12 tester skrevs först för resolver, felklassning och sanerat svar. Endast exakt saknad-order-svar mappas till 404; operativa fel avvisas med generiskt fel. Commit `dc3597c66e520552828833e39be5ddce46231d49`.
8. **Interpreter-fallback:** det godkända planalternativet att falla tillbaka till `PATH` verifierades med två nya röda fall, sedan grön efter implementeringen. Även orderuppslagningens oväntade databasfel testades rött före route-rättningen och därefter grönt. Commit `6ab67d75c65d1f537a8060cd633a5f5094038464`.

Samtliga förändringar behöll befintliga tester. Inga tester togs bort, hoppades över eller inaktiverades.

## Verifiering

Jest-integrationen använder `tests/helpers/env.ts`, som vid saknad `TEST_DATABASE_URL` väljer den isolerade databasen `butik_test`. Den fullständiga Jest-körningen genomfördes mot denna testdatabas; ingen annan databasoperation eller manuell reset utfördes.

| Kommando | Utfall |
|---|---|
| `.\.venv\Scripts\python.exe -m pytest -q` | 18 passed |
| `npm test -- --runTestsByPath tests/legacyPrice.test.ts` | 15 passed |
| `npm test` | 43 passed; det tidigare kända pris-endpointtestet returnerade nu 200 |
| `npm run lint` | Godkänd |
| `npm run typecheck` | Godkänd |
| `npm run format:check` | Underkänd: 16 TypeScript-filer rapporterades (inklusive filer utanför ändringen) |
| `npx prettier --check --end-of-line crlf src/pricing/legacyPrice.ts src/routes/orders.ts tests/legacyPrice.test.ts` | Godkänd |
| `.\.venv\Scripts\python.exe -m py_compile src\legacy\price_calc.py jobs\nightly_report.py tests\test_price_calc.py tests\test_nightly_report.py` | Godkänd |
| `git diff --check` | Godkänd |

`npm run format:check` utfall redovisas oförändrat i stället för att formatera orelaterade TypeScript-filer. Den projekttäckande kontrollen rapporterade även formatfel i filer som inte ändrats här.

## Beslut, alternativ och kvarstående risker

- Bevara affärslogiken exakt; ändrad rabattgiltighet, prisformat eller avrundningsregel kräver separat krav och tester.
- Behåll fake DB för Python-karakterisering. Jest-orderintegration körs endast mot `butik_test`; inga destruktiva operationer kördes mot annan databas.
- Anslutningskonfigurationen har override `LEGACY_PYTHON`, lokal venv och sedan PATH-fallback. Alternativet att bara anropa hårdkodat `python3` bevaras inte eftersom det misslyckade på Windows.
- Ingen expand/contract-migration behövs eftersom inget schema- eller datalagringsbehov verifierades.
- `npm run format:check` kvarstår som kvalitetsfel för 16 filer. En senare separat formatningsändring bör först avgränsas och granskas.
- Ingen Review-fas eller slutrapport har startats; arbetet stannar efter Build och verifiering enligt uppgiften.

## Tid och VG-mätpunkter

- Planfasens sessionslogg sluttid: `15:41:42 +01:00`; slutlig verifiering avslutades `16:18:27 +01:00`.
- Mätt väggklockeförlopp mellan dessa observationer: `36 min 45 sek`; detta inkluderar testkörningar och väntan på parallellt arbete och är inte ett mått på aktiv arbetstid.
- Aktiva utvecklingsminuter, token/kostnad och automatisk coverage-mätning saknas; de uppskattas inte.
- Mätbara VG-resultat: Python fake-DB 18/18; Jest fullsvit 43/43; tidigare prisroute-404 försvann i den fulla körningen; lint/typecheck/ändrade TS-filers format godkända; projekttäckande formattering är kvarstående.
