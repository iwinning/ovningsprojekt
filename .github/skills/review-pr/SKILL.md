---
name: review-pr
description: Granska kursledarens pull request med fokus på säkerhet, arkitektur/struktur och kodstandard, och visa vilken riggkontroll som kan upptäcka varje brist.
argument-hint: "[PR-länk eller branch]"
---

# Review PR – granskning utan ändringar

Läs `docs/standard.md`, det aktuella PR-diffet och relevanta filer och tester. Gör inga kodändringar, commits eller merge.

Rapportera minst följande kategorier var för sig:
1. **Säkerhet** – t.ex. SQL-injektion, behörighet, hemligheter, personuppgifter.
2. **Struktur** – t.ex. N+1-frågor, affärslogik i route, transaktioner, duplikation.
3. **Kodstandard** – namn, JSON-kontrakt, Result-fel, formatering, testkrav.

För varje identifierad brist: ange fil/rad, risk, konkret evidens, rekommenderad åtgärd och den automatiska kontroll eller manuella granskningsregel som skulle upptäcka bristen. Hitta inte på fynd för att fylla en kategori: märk saknade fynd som ej verifierade.

Välj testkommandon som inte förstör data. Spara granskningen i `docs/work/pr-review.md` och en sammanfattning i `sessions/`. Det PR som kursledaren delar ut krävs för slutlig verifiering.
