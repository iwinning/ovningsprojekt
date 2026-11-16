# Research: `GET /orders/:id/price`

## Scope and status

Investigated the failing order-price endpoint without changing application code.
The worktree already had a modified `package-lock.json`; it was left untouched.

## Findings

- `src/pricing/legacyPrice.ts` calls `execFile("python3", ...)`, passing the price
  script and order ID. It inherits `process.env`.
- Any child-process error is converted to a `not_found` result. The route sends
  that result through `sendResult`, so a process-launch failure appears as HTTP
  404 even when the order exists.
- In this Windows shell, `python3` resolves to the Microsoft Store execution
  alias in `WindowsApps`. Running it via Node returned code 9009 and the message
  that Python was not found. The alias is not the project interpreter.
- `.venv\Scripts\python.exe` exists and imports `psycopg` 3.2.3. The venv has
  `python.exe` and `pythonw.exe`, but no `python3.exe`. The test process did not
  have `VIRTUAL_ENV` set or `.venv\Scripts` on `PATH`.
- Thus, TypeScript is not asking uv to select Python: `execFile` asks Windows
  to resolve the literal executable name `python3` using the inherited `PATH`.
  The uv venv does not automatically participate when running npm normally.
  Even prepending this venv to `PATH` would not provide the requested
  `python3.exe` name; invoking npm under uv also needs consideration of that
  executable-name mismatch.
- The database-backed order tests passed, including retrieval and ownership
  checks, while the price test received 404 instead of 200. Its expected total
  was 1187.5. This supports a process-launch failure as the immediate cause;
  the endpoint never produced a price response.

## Baseline

Command:

```text
npm test -- --runTestsByPath tests/orders.test.ts
```

Result: 1 suite failed; 8 tests passed and 1 failed. The only failure was
`GET /orders/:id/price`, which expected HTTP 200 and received HTTP 404. The
separate Node probe of `execFile("python3", ["--version"])` returned code 9009
with the Microsoft Store alias message.

The README says the full suite should contain 16 tests, and an earlier local
observation reported 15/16 passing. The full suite was not run for this
investigation; do not treat that earlier observation as this run's baseline.

## Acceptance criteria for a follow-up fix

- **Givet** a valid order owned by the authenticated customer and a usable
  project Python environment, **När** `GET /orders/:id/price` runs, **Så**
  return HTTP 200 with `net`, `vat`, and `total`, preserving the existing legacy
  calculation and rounding.
- **Givet** a malformed order ID, **När** the endpoint runs, **Så** return HTTP
  400 without launching Python.
- **Givet** an order that is missing or belongs to another customer, **När**
  the endpoint runs, **Så** preserve the existing 404 or 403 behavior and do
  not run the price script.
- **Givet** a Python launch or script failure for an otherwise valid owned
  order, **När** the endpoint runs, **Så** report the failure explicitly rather
  than misrepresenting it as a missing order.

## Short plan (no implementation started)

1. Agree on a robust interpreter selection strategy for Windows/uv and the
   supported runtime environments.
2. Add or adapt focused tests for successful invocation, launch failure, and
   existing invalid-ID/ownership behavior; run the affected test file red.
3. Make the smallest bridge change, rerun the focused test, then run the
   required suite and relevant quality checks.
4. Record measured results and review error/status mapping; preserve the legacy
   price calculation unchanged.

No code changes, new tests, or commits were made during this research.
