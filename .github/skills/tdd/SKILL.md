---
name: tdd
description: Använd testdriven utveckling (rött-grönt-refaktorera) när du bygger en ny endpoint, ändrar beteende, rättar en bugg eller moderniserar befintlig kod i butikens API.
argument-hint: "[funktion eller fel som ska arbetas med]"
---

# TDD – testdrivet arbetsflöde

## Förberedelse

1. Läs `docs/standard.md`, `docs/api.md`, relevanta implementationer och befintliga tester.
2. Kontrollera den aktuella baslinjen och notera **befintliga fel separat** från nya fel. Exempel: det har tidigare observerats ett lokalt fel i `GET /orders/:id/price`; dess grundorsak är ännu inte verifierad.
3. Definiera minst ett acceptanskriterium med **Givet / När / Så** innan kod ändras. Ange lyckat fall och rimliga fel-, ägarskaps- och gränsfall.

## Rött

4. Lägg till ett litet test för det **nya** kravet. Ta inte bort eller försvaga gamla tester.
5. Kör enbart berörd testfil och notera exakt varför det nya testet fallerar. Om ett gammalt test redan fallerar, skilj ut det i rapporten.

## Grönt

6. Gör minsta möjliga ändring i produktionskoden för att uppfylla kravet.
7. Kör om testet och notera utfallet. Ändra inte krav eller förväntat värde bara för att få grönt.

## Refaktorera och verifiera

8. Förbättra endast kod som har stöd av testerna. Var extra försiktig med prisavrundning och gammal Python-kod.
9. Kör berörda tester, sedan `npm test`, `npm run lint`, `npm run typecheck` och `npm run format:check` när de är relevanta.
10. Granska parametriserad SQL, behörighetskontroller, Result-fel, API-statuskoder och frånvaro av personuppgifter/hemligheter.

## Redovisa

Skriv en kort TDD-rapport med:
- Krav och acceptanskriterier (Givet/När/Så).
- Rött: vilket nytt test som fallerade och varför.
- Grönt: kodändringen och det uppmätta testresultatet.
- Refaktorering: vad som förbättrades.
- Exakta testkommandon, antal godkända/underkända, befintliga fel och kvarstående risker.
- Filer, eventuell commit och nästa steg.

Spara arbetspassets sammanfattning i `sessions/` och se till att en annan person kan återuppta arbetet därifrån. Redovisa endast faktiskt genomförda körningar och mätningar.
