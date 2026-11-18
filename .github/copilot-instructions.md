# Projektinstruktioner – butikens API

Du arbetar i kursprojektet **AI-assisterad systemutveckling**. Syftet är att bygga en verifierbar AI-utvecklingsrigg runt en befintlig kodbas, inte att ersätta kodbasen med en ny applikation.

## Läs innan du ändrar kod

- Läs `README.md`, `docs/standard.md`, `docs/api.md` och berörda tester.
- API:t använder TypeScript, Express, PostgreSQL och Jest.
- Den äldre prisberäkningen finns i `src/legacy/price_calc.py`; TypeScript-anropet finns i `src/pricing/legacyPrice.ts`.
- Varje arbetsperiod ska dokumenteras i `sessions/`. Beslut som påverkar arkitekturen ska dokumenteras som ADR i `docs/adr/`.

## Arbetssätt: research → plan → build → review → verify

1. **Research:** kartlägg berörd kod, nuvarande beteende, relevanta tester och risker. Spara resultatet som en fil.
2. **Plan:** skriv Givet/När/Så-acceptanskriterier, avgränsning, risker och vilka tester som behövs. Spara planen.
3. **Build:** skriv först ett relevant test som visar önskat beteende, genomför sedan minsta möjliga kodändring. Spara resultat och referera till commits.
4. **Review:** granska säkerhet, struktur, kodstandard, felhantering och möjliga regressioner. Spara granskningen.
5. **Verify:** kör relevanta tester och kvalitetskontroller, rapportera exakta resultat samt kvarstående fel. Spara verifieringen.

Arbeta i små, begripliga ändringar. Skapa spårbara commits efter verifierade delsteg. Påstå aldrig att ett test passerat om det inte har körts.

## Obligatoriska regler

- **Ta aldrig bort, hoppa över, inaktivera eller försvaga befintliga tester för att få grönt resultat.** Använd inte `skip`, `only` eller motsvarande som genväg.
- Be om godkännande innan destruktiva kommandon, databasåterställning utanför lokal testmiljö, publicering eller ändring av behörigheter.
- Följ `docs/standard.md`: TypeScript camelCase/PascalCase, JSON camelCase, parametriserad SQL, inga N+1-frågor, transaktioner för sammanhängande skrivningar.
- Förväntade tjänstefel returneras som `Result`; routes använder `sendResult`/`sendError`.
- Använd `requireCustomer` och kontrollera ägarskap i tjänstelagret; lita aldrig på kund-ID från request body.
- Bevara befintlig prislogik och avrundning tills karakteriseringstester dokumenterar beteendet. Duplicera inte prislogiken.
- Lägg inte in hemligheter, riktiga personuppgifter eller produktionsdata i kod, promptar, testdata eller loggar.
- Om ett test fallerar: utred orsak och redovisa felet, ändra inte förväntat resultat utan motivering och kravstöd.

## Verifieringskommandon

- TypeScript-tester: `npm test`.
- Lint: `npm run lint`.
- Typkontroll: `npm run typecheck`.
- Formatkontroll: `npm run format:check`.
- Python-tester i Windows-projektets separata uv-miljö: `.\.venv\Scripts\python.exe -m pytest` (när Python-tester finns).

Kör särskilt de berörda testerna först och hela sviten före avslut. Dokumentera faktiska kommandon och utfall i sessionsloggen.

## Historisk baslinje och aktuellt läge

Vid den första lokala Windows-körningen gav GET /orders/:id/price HTTP 404 i stället för 200, eftersom den gamla TypeScript-bryggan startade python3 som inte fungerade lokalt. Felet är åtgärdat med portabel Python-upplösning och separerad felklassning. Senaste lokala slutrapporten i docs/work/legacy-price-quality.md redovisar 47/47 Jesttester, 20/20 Pythontester och 8/8 hooktester. Ändra inte dessa påståenden utan nya faktiska testkörningar.

Det särskilda PR som kursledaren ger på seminariet ska fortfarande granskas med /review-pr. Modellval per agent och projektets behörighetskonfiguration behöver verifieras inför examinationen.
