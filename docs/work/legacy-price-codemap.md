# Codemap: legacy-prisberäkning

**Kontrollerad:** 2026-11-18  
**Omfattning:** Nuvarande beroenden och dataflöde; endast research, ingen kodändring

## Översikt över anropare och flöden

```text
HTTP GET /orders/:id/price
  -> src/routes/orders.ts
       -> requireCustomer / parseId
       -> getOrder(id, customerId)          [ägarskapskontroll]
       -> src/pricing/legacyPrice.ts
            -> execFile("python3", [price_calc.py, id], env=process.env)
                 -> src/legacy/price_calc.py CLI
                      -> global psycopg connection
                      -> calc_price(order_id)
                      -> JSON till stdout / fel-JSON till stderr, exit 1
       <- parse stdout JSON
  -> sendResult / sendError -> HTTP
```

Separat batchflöde:

```text
jobs/nightly_report.py
  -> importerar calc_price och conn från src/legacy/price_calc.py
  -> väljer dagens paid orders med interpolerat datum-SQL
  -> calc_price(id) för varje order
  -> summerar p.total
  -> skriver rapportfil
```

Orderpriser beräknas därmed från två konsumenter: API-bryggan och nattjobbet. CLI:t kan också köras fristående enligt dokumentationen.

## Moduler och ansvar

| Fil | Ansvar | Kända kopplingar/risker |
|---|---|---|
| `src/legacy/price_calc.py` | Läs orderrader och rabatt; Decimal-beräkning; CLI JSON | Global DB-anslutning skapas vid import; autocommit; interpolerad SQL; inget explicit stängande; bara loggning ignorerar fel |
| `src/pricing/legacyPrice.ts` | Starta Python CLI och parsa JSON | Hårdkodad `python3`; subprocessfel felklassas som `not_found`; JSON-parsefel hanteras inte |
| `src/routes/orders.ts` | Auth, ID-validering och orderägarskap före prisanrop | Ägarskap kontrolleras av `getOrder`; gamla route-/HTTP-kontrakt ska bevaras |
| `src/services/orderService.ts` | Orderdata och rabattkod in i databasen | Parametriserar skrivningen; `discountCode` är ändå användarstyrd och når senare legacy-SQL |
| `jobs/nightly_report.py` | Dagens betalda order sammanställs | Direkt importerar global `conn`; interpolerar datum; hanterar inte `None` från prisberäkning |
| `db/schema.sql`, `db/seed.sql` | Datatyper och syntetiska exempel | `unit_price NUMERIC(10,2)`; rabatter har procent/datum men saknar uttrycklig procentconstraint |
| `tests/orders.test.ts` | API-/Jest-test | Prisroute-test för 1042; inte Python-karakterisering |

## Beräkningsflöde

1. Läs orderns rabattkod.
2. Läs samtliga orderrader och summera `quantity * unit_price` med `Decimal`.
3. Om rabattkod finns och matchar en `discounts`-rad, dra av procentandelen från summan. Giltighetsdatum ignoreras.
4. Trunkera nettot mot noll till två decimaler (`int(value * 100) / 100`).
5. Beräkna moms som 25 % av trunkerat netto; trunkera momsen oberoende på samma sätt.
6. Addera netto och moms. JSON serialisering via `str(Decimal)` kan ge varierande antal decimaler.
7. Försök append-logga tid, order-ID och total; alla loggfel tystas.

Syntetiska seed-exempel:

- 1042: netto 950, moms 237,5, total 1187,5.
- 1044: netto 179,91, moms 44,97 (trunkerat), total 224,88.
- 1045: netto 551,65, moms 137,91 (trunkerat), total 689,56; seedrabatten tillämpas trots utgångsdatum.

## Trust boundaries och felvägar

- Kundautentisering och ägarskap kontrolleras före subprocessanropet i API-vägen; direkt användning av CLI/script går runt detta API-skydd.
- Användarstyrd rabattkod läses från DB och interpoleras i Python-SQL. Order-ID interpoleras. Nattjobbsdatum interpoleras separat.
- Python-anslutningens URL kommer från `DATABASE_URL` eller utvecklingsfallback. Global importanslutning gör importordning och testmiljö kritiska.
- Subprocessfel mappar till 404 i TypeScript, oavsett verklig orsak; korrupt stdout kan i stället kasta parsingfel.
- Oväntade Python-DB-fel har ingen tydlig service-/CLI-mappning. Loggfel är tysta; nattjobb kan dereferera `None`.
- Interpreterval `python3` är inte portabelt i verifierad Windows-miljö. Lokal `python3`/`python`/`py` kommandoauflösning fungerar inte, medan projektets `.venv` har Python.

## Kända verifieringsgränser

- Inga Python-karakteriseringstester hittades.
- Agenten körde inte API-/DB-/Python-tester eller reset. Existerande prisintegrationsfel (404 mot väntat 200) är historiskt dokumenterat, ej nyreproducerat under denna research.
- All seeddata är uttryckligen fiktiv. Ingen produktionsdata används.
