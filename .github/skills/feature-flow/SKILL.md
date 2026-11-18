---
name: feature-flow
description: Genomför en user story i butikens API genom research, plan, TDD-bygg, granskning och verifiering med en separat fil per fas. Använd för kursens nya funktion.
argument-hint: "[user story]"
---

# Feature flow – från krav till verifierat resultat

Följ `docs/standard.md` och repositoryinstruktionerna. Läs `docs/user-stories.md`, befintlig kod och tester först.

**Fas 1: Research.** Kartlägg API, service, databas, ägarskap, befintliga tester och risker. Spara `docs/work/feature-research.md`. Ändra ingen appkod ännu.

**Fas 2: Plan.** Beskriv avgränsning, Givet/När/Så-kriterier, gränsfall, testplan, säkerhet och rollback. Spara `docs/work/feature-plan.md`. Be om godkännande innan större ändringar.

**Fas 3: Build.** Använd `/tdd`: skriv ett nytt misslyckande test för kravet, gör en minimal implementering, kör testet, refaktorera säkert. Spara `docs/work/feature-build.md` inklusive faktiska testresultat och commit-SHA.

**Fas 4: Review.** Granska säkerhet, ägarskap, SQL, Result, kodstandard och testtäckning utan att dölja brister. Spara `docs/work/feature-review.md`.

**Fas 5: Verify.** Kör relevanta tester och `npm test`, `npm run lint`, `npm run typecheck`, `npm run format:check`; dokumentera utfall och tidigare kända fel. Spara `docs/work/feature-verify.md`.

Ta aldrig bort/skip:a befintliga tester. Skapa små spårbara commits, logga arbetspasset i `sessions/` och skriv en ADR i `docs/adr/` för det viktigaste valet. Påstå inte att ett moment är godkänt utan faktisk verifiering.
