import runpy
import sys
from decimal import Decimal
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


REPORT_PATH = Path(__file__).parents[1] / "jobs" / "nightly_report.py"


class ReportCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rows = []

    def execute(self, query, params=None):
        self.connection.queries.append((query, params))
        self.rows = list(self.connection.order_ids)

    def fetchall(self):
        return self.rows


class ReportConnection:
    def __init__(self, order_ids=()):
        self.order_ids = list(order_ids)
        self.queries = []
        self.closed = False

    def cursor(self):
        return ReportCursor(self)

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        self.closed = True


def load_report(monkeypatch, connection, calc_price=None):
    price_module = ModuleType("price_calc")
    price_module.connect_db = lambda: connection
    price_module.calc_price = calc_price or (lambda _order_id, _connection: None)
    monkeypatch.setitem(sys.modules, "price_calc", price_module)
    monkeypatch.setattr(sys, "argv", ["nightly_report.py"])
    return runpy.run_path(str(REPORT_PATH), run_name="legacy_nightly_report")


def test_report_date_is_passed_as_a_sql_parameter(monkeypatch):
    connection = ReportConnection()
    report = load_report(monkeypatch, connection)
    injected_date = "2026-11-18' OR '1'='1"

    report["get_paid_order_ids"](connection, injected_date)

    query, params = connection.queries[0]
    assert "2026-11-18' OR '1'='1" not in query
    assert params == (injected_date,)


def test_report_preserves_sum_and_output_for_paid_orders(monkeypatch):
    connection = ReportConnection(order_ids=[(41,), (42,)])
    prices = {41: Decimal("10.50"), 42: Decimal("2.25")}
    report = load_report(
        monkeypatch,
        connection,
        calc_price=lambda order_id, _connection: SimpleNamespace(total=prices[order_id]),
    )

    output = report["create_report"](connection, "2026-11-18")

    assert output == "2026-11-18: 2 betalda ordrar, totalt 12.75 kr"
    assert connection.queries[0][1] == ("2026-11-18",)


def test_report_fails_clearly_when_price_is_missing(monkeypatch):
    connection = ReportConnection(order_ids=[(41,)])
    report = load_report(monkeypatch, connection)

    with pytest.raises(RuntimeError, match="Pris kunde inte beräknas"):
        report["create_report"](connection, "2026-11-18")
