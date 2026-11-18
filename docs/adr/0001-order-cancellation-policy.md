# ADR 0001: Avbokningspolicy och tidskälla för order

- **Status:** Accepterad för user story 2
- **Datum:** 2026-11-16

## Kontext

User story 2 tillåter en kund att avbryta en beställning inom 30 minuter, men definierar inte tillåtna statusar, exakt tidsgräns eller klockkälla. Orderstatus är fri text och orderns `created_at` sätts av PostgreSQL.

## Beslut

- Avbokning tillåts endast när aktuell status är `new`.
- Statusar som inte är `new`, inklusive `cancelled`, ger konflikt; upprepad avbokning är inte idempotent.
- Ålder från 0 till och med 30 minuter accepteras. Framtida skapandetid och ålder över 30 minuter nekas.
- PostgreSQL-klockan är auktoritativ i produktion. Gränstester injicerar en bestämd tid till tjänsten.
- Orderraden låses under transaktionen och statusuppdateringen villkoras på kund och status för att serialisera samtidiga avbokningar/statusändringar.

## Alternativ

Applikationsserverns klocka hade varit lätt att injicera och testa, men kan skilja sig från klockan som satte `created_at`; klockdrift kan därmed ändra beslutet nära gränsen. Att endast ändra `created_at` i testdatabasen undviker produktionsinjektion men gör exakt gränstestning beroende av löpande tid. Vald lösning använder därför DB-tid i produktion och en intern explicit tid endast för deterministiska tester.

## Konsekvenser

- Tidsgräns och framtida tider jämförs i PostgreSQL för att undvika precisionstapp mellan PostgreSQLs mikrosekunder och JavaScripts millisekunder.
- Transaktionen håller orderraden låst genom kontroll och uppdatering.
- Ingen schemaändring krävs; `orders.status` kan lagra `cancelled`.
- Om framtida krav vill tillåta avbokning av exempelvis obetalda statusar måste policyn och testerna uppdateras.
