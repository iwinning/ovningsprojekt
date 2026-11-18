# AI-riggen – delar, beslut och verifiering

**Miljö:** VS Code + GitHub Copilot Agent, Windows, Node.js 26, Python 3.12 via uv. Ingen Claude Code krävs.

## Skills

| Skill | Varför | Användning | Kontroll |
|---|---|---|---|
| `/tdd` | Nya krav med test först; undvika kod utan säkerhetsnät | Lägg till test, se rött, bygg grönt, refaktorera | Användes under orderavbokning och Pythonmodernisering. Röda och gröna tester, testkommandon och commits finns i docs/work. |
| `/feature-flow` | Varje fas lämnar en spårbar fil | research → plan → build → review → verify | Användes för orderavbokningen. De fem fasfilerna finns i docs/work/feature-*.md. |
| `/review-pr` | Strukturerad kontroll av kursledarens PR | Säkerhet, struktur och kodstandard | Kör först när kursledarens PR finns och granska fynd med fil/rad. |

## Fyra specialiserade agenter

| Agent | Ansvar | Verktyg (önskade) | Modell |
|---|---|---|---|
| Researcher | Kartlägg, mät baslinje | read, search, execute | GPT-5.6 Luna, reserv GPT-5.3-Codex |
| Planner | Givet/När/Så och risker | read, search | GPT-5.6 Luna, reserv GPT-5.3-Codex |
| Implementer | Små testdrivna ändringar | read, search, edit, execute; tdd | GPT-5.3-Codex, reserv GPT-5.6 Luna |
| Reviewer | Oberoende säkerhets- och standardgranskning | read, search, execute | GPT-5.6 Sol, reserv GPT-5.3-Codex |

Agentfilerna anger nu explicita modellpreferenser (`model`) med en reservmodell samt `model-policy: preferred`. Om den önskade modellen inte finns tillgänglig kan Copilot välja en annan tillgänglig modell. Jag har kontrollerat modellnamnen mot GitHub Copilots dokumentation, men har inte åtkomst till användarens lokala modellväljare och kan därför inte verifiera att varje modell går att välja på kontot. Inga modellkostnader har uppmätts. Granskning och planering görs före implementation; parallella agenter ska inte redigera samma filer.

## Hooks: sex konkreta triggers/åtgärder

Config: `.github/hooks/rigg.json`; program: `.github/hooks/rigg.cjs`.

| Hook | Händelse | Åtgärd |
|---|---|---|
| 1. Återläs minne | sessionStart | Läser `sessions/last-state.md` och ger föregående tekniska läge till agenten |
| 2. Skydda tester | preToolUse | Deny för tydliga försök att ta bort, hoppa över eller isolera tester |
| 3. Begär godkännande | preToolUse | Ask för bl.a. databåterställning, `git reset --hard` och `git clean -f` |
| 4. Kvalitets-/händelsespårning | postToolUse | Registrerar endast tool-namn/tid lokalt, kör `git diff --check` efter edit |
| 5. Minneskontroll | preCompact | Skriver teknisk ögonblicksbild i `.ai-runtime/state.json` |
| 6. Spara minne | sessionEnd | Skriver `sessions/last-state.md` med branch, commit och ändrade filer |

**Begränsningar:** Hook-skriptets mönster är ett skydd mot typiska misstag, inte en fullständig säkerhetsgräns. Kommandon kan skrivas på andra sätt; hooks kan vara inaktiva, och timeouts i Copilot preToolUse är fail-open. Kontrollera därför även `git diff -- tests/` och att testantal inte minskats före varje commit. `sessionEnd` sparar endast tekniska metadata, inte hela konversationen; arbetsbeslut sammanfattas manuellt i en daterad fil i `sessions/`.

## Behörighet: allow / ask / deny

- **Allow (tillåt):** läs kod, sök, kör ofarliga statuskommandon och testkommandon enligt normal Copilot-policy.
- **Ask (fråga):** preToolUse-hook kräver godkännande för riskabla kommandon; ändring av databas och extern publicering ska granskas av användaren.
- **Deny (stoppa):** preToolUse-hook blockerar vissa testborttagningar och testinaktiveringar.

Projektfilen `.vscode/settings.json` använder `chat.permissions.default: default` och `chat.tools.terminal.autoApprove` för att tillåta vanliga läs- och testkommandon samt kräva bekräftelse för riskfyllda kommandon. `chat.tools.edits.autoApprove` kräver godkännande för exempelvis `.env`, `.vscode`-inställningar, hooks, workflows och databasschema. Hooken `protect-tests` ger `permissionDecision: deny` för vissa försök att ta bort eller inaktivera tester. En `false`-regel i VS Code betyder **ask**, inte **deny**; nej-beslutet kommer från hooken. Använd **Manual permissions** i VS Code. Projekthooks är ingen fullständig säkerhetsgräns och inställningarna måste verifieras i användarens faktiska Copilot-session.

## Demo och lokala verifieringar

```powershell
# Kontrollera JSON-konfiguration och åtta beslutsfall utan att starta databas
node --test .github/hooks/rigg.spec.cjs

# Kör ett skyddstest direkt (ska svara permissionDecision=deny)
'{"toolName":"edit","toolArgs":{"path":"tests/orders.test.ts","new_string":"it.skip(\"x\", () => {})"}}' | node .github/hooks/rigg.cjs protect-tests

# Granska teständringar och kodkvalitet
git diff -- tests/
npm run lint
npm run typecheck
npm run format:check
```

Kör en **ny** Copilot Agent-session, välj Copilot som session target och kontrollera Hooks under *Chat: Open Customizations*. För att verifiera minneskedjan: avsluta sessionen, kontrollera `sessions/last-state.md`, starta en ny session och se om föregående branch/commit injiceras. För att verifiera ett stopp: använd en ofarlig simulerad `preToolUse`-händelse, inte verklig borttagning av tester.

## Status inför inlämning

- Ny funktion genom fem faser, TDD och ADR: genomförd. Se docs/work/feature-*.md och docs/adr/0001-order-cancellation-policy.md.
- Legacy-Python: codemap, karakteriseringstester, separata gröna refaktoreringar och reversibel expand/contract-plan genomförda. Se docs/work/legacy-price-*.md.
- Slutlig lokal verifiering enligt sessionslogg: Jest 47/47, pytest 20/20, hooktester 8/8 samt lint, typecheck och format:check godkända. Detta är rapporterade lokala körningar, inte GitHub Actions.
- Testskyddet blockerade först även dokumentation och rättades med ett rött och därefter grönt regressionstest. Åtta hooktester passerar efter rättningen; skyddet är fortfarande inte en fullständig säkerhetsgräns.
- Den särskilda pull request som kursledaren delar ut ska granskas på seminariet och är därför inte genomförd här.
- Modellpreferenser per agent och projektinställningar för allow/ask/deny är inlagda i `.github/agents/` respektive `.vscode/settings.json`. Kontroll i den lokala VS Code-sessionen av tillgängliga modeller och faktiskt behörighetsbeteende återstår.
- Mätningar av faktisk tokenförbrukning och modellkostnad saknas. Det finns i stället uppmätta tidsfönster och SQL-frågeantal i sessionsloggarna.
- Pull request #1 mergades till main. Taggen `inlamning` ska peka på den slutliga versionen av main efter dessa konfigurationsändringar.
