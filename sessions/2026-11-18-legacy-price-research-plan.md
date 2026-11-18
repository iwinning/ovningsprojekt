# Sessionslogg: modernisering av legacy-prisberäkningen

**Datum:** 2026-11-18  
**Arbetspass:** 2026-11-18 15:28:00–15:41:42 +01:00 (13 min 42 sek; start från användarens tidsstämpel, slut från lokal klocka efter planfasen).
**Omfattning:** Research och Plan endast. Ingen Python-/TypeScript-kod, testkod eller databas ändrad. TDD/build inväntar granskning.

## Research

- Researcher-agenten undersökte prisberäkning, båda anropare, DB-/testsetup, säkerhetsrisker och Windows-interpreterfrågan.
- Rapporter sparade i `docs/work/legacy-price-research.md` och `docs/work/legacy-price-codemap.md`.
- Verifierade beteendedetaljer och syntetiska exempel dokumenterades. Rabattens `valid_from`/`valid_to` ignoreras; trunkering sker mot noll separat för netto och moms.
- Verifierade: tre interpolerade SQL-frågor i prisberäknaren, global importanslutning/autocommit, hårdkodad `python3`, all subprocessfelmappning till 404 och brett ignorerade loggfel.
- Windows-kontroll: `python3`/`python`/`py` kunde inte användas; Node `execFile("python3", ...)` gav felkod 9009. Projektets `.venv` innehåller Python 3.12.14. Detta stöder men bekräftar inte ensam hela HTTP-404-flödet.
- Inga Python- eller API-tester, DB-reset eller databastest kördes. Kända Jest-prisroute-404 är historisk observation; root cause är ännu inte verifierad med endpointkörning i detta arbetspass.
- Vid start fanns `M package-lock.json` och `?? sessions/last-state.md`; de lämnades orörda.

## Plan

- Planner-agenten har ombetts skapa `docs/work/legacy-price-plan.md` med minst fem karakteriseringstester, isolerad DB/teststrategi, interpreteralternativ, tre testdrivna separata refaktorsteg, rollback/expand-contract och VG-mått.
- Planen finns i `docs/work/legacy-price-plan.md`. Den innehåller sju karakteriseringsfall, fem stegvisa test-först-commits, Windows-interpreterförslag, subprocessfelkontrakt, isoleringsgrindar och expand/contract endast om senare verifierat DB-behov uppstår.
- Inga implementationer, migrationsfiler eller tester skapas innan planen granskats och användaren går vidare till TDD.

## Mätningar

- Research-kontroller som faktiskt kördes finns listade i Research-dokumentet. Full testsvit och Python-testsvit kördes inte.
- Arbetstid, testantal under framtida refaktorsteg och token/kostnad återstår att mäta. Ingen kostnad uppskattas som faktiskt utfall.
- `git diff --check` kördes efter dokumentationen utan fel. Kontroll av arbetsytan visade inga ändringar i `src`, `tests`, `jobs` eller `db`; befintliga `package-lock.json` och `sessions/last-state.md` lämnades orörda.
