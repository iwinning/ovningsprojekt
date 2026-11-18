import importlib.util
import json
import logging
import runpy
import sys
from decimal import Decimal
from pathlib import Path

import psycopg
import pytest


MODULE_PATH = Path(__file__).parents[1] / "src" / "legacy" / "price_calc.py"


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rows = []

    def execute(self, query, params=None):
        self.connection.queries.append((query, params))
        normalized_query = query.lower()
        if "select discount_code from orders" in normalized_query:
            self.rows = [] if self.connection.order_exists is False else [
                (self.connection.discount_code,)
            ]
        elif "select quantity, unit_price from order_lines" in normalized_query:
            self.rows = list(self.connection.lines)
        elif "select percent from discounts" in normalized_query:
            self.rows = (
                [(self.connection.discount_percent,)]
                if self.connection.discount_percent is not None
                else []
            )
        elif "select id from orders where status = 'paid'" in normalized_query:
            self.rows = list(self.connection.paid_order_ids)
        elif "select id, discount_code from orders where id = any" in normalized_query:
            order_ids = params[0]
            self.rows = [
                (order_id, self.connection.batch_orders[order_id])
                for order_id in order_ids
                if order_id in self.connection.batch_orders
            ]
        elif "select order_id, quantity, unit_price from order_lines" in normalized_query:
            order_ids = set(params[0])
            self.rows = [
                row for row in self.connection.batch_lines if row[0] in order_ids
            ]
        elif "select code, percent from discounts" in normalized_query:
            codes = set(params[0])
            self.rows = [
                (code, percent)
                for code, percent in self.connection.batch_discounts.items()
                if code in codes
            ]
        else:
            raise AssertionError(f"Unexpected SQL in fake database: {query}")

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(
        self,
        *,
        order_exists=True,
        discount_code=None,
        lines=(),
        discount_percent=None,
        paid_order_ids=(),
        batch_orders=None,
        batch_lines=(),
        batch_discounts=None,
    ):
        self.order_exists = order_exists
        self.discount_code = discount_code
        self.lines = tuple(lines)
        self.discount_percent = discount_percent
        self.paid_order_ids = list(paid_order_ids)
        self.batch_orders = batch_orders or {}
        self.batch_lines = tuple(batch_lines)
        self.batch_discounts = batch_discounts or {}
        self.queries = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        self.closed = True

    def cursor(self):
        return FakeCursor(self)


@pytest.fixture
def load_price_module(monkeypatch):
    def load(connection):
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost:1/fake_only")
        monkeypatch.setattr(psycopg, "connect", lambda *args, **kwargs: connection)
        module_name = "price_calc_characterization"
        spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, module_name, module)
        spec.loader.exec_module(module)
        module._fake_connection = connection
        module.LOGG = str(Path(__file__).parent)
        return module

    return load


def test_import_does_not_open_a_database_connection(monkeypatch):
    calls = []
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost:1/fake_only")
    monkeypatch.setattr(
        psycopg,
        "connect",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    module_name = "price_calc_import_without_database"
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)

    spec.loader.exec_module(module)

    assert calls == []


def test_calc_price_closes_its_managed_connection(load_price_module):
    connection = FakeConnection(lines=[(1, Decimal("10.00"))])
    module = load_price_module(connection)

    price = module.calc_price(1042)

    assert (price.net, price.vat, price.total) == (
        Decimal("10"),
        Decimal("2.5"),
        Decimal("12.5"),
    )
    assert connection.closed


def test_log_failures_are_reported_without_order_data(
    load_price_module, monkeypatch, caplog
):
    connection = FakeConnection(lines=[(1, Decimal("10.00"))])
    module = load_price_module(connection)

    def fail_open(*_args, **_kwargs):
        raise PermissionError("private path and order data")

    monkeypatch.setattr("builtins.open", fail_open)
    with caplog.at_level(logging.WARNING):
        price = module.calc_price(1042, connection)

    assert price.total == Decimal("12.5")
    assert [record.getMessage() for record in caplog.records] == [
        "Could not write legacy price calculation log."
    ]
    assert "private path" not in caplog.text
    assert "1042" not in caplog.text


def test_price_without_discount_preserves_decimal_values_and_text(load_price_module):
    module = load_price_module(
        FakeConnection(
            lines=[
                (2, Decimal("375.00")),
                (1, Decimal("200.00")),
            ]
        )
    )

    price = module.calc_price(1042, module._fake_connection)

    assert (price.net, price.vat, price.total) == (
        Decimal("950"),
        Decimal("237.5"),
        Decimal("1187.5"),
    )
    assert [str(value) for value in (price.net, price.vat, price.total)] == [
        "950",
        "237.5",
        "1187.5",
    ]


def test_discount_and_vat_are_truncated_separately(load_price_module):
    module = load_price_module(
        FakeConnection(
            discount_code="VAR10",
            lines=[(1, Decimal("199.90"))],
            discount_percent=10,
        )
    )

    price = module.calc_price(1044, module._fake_connection)

    assert (price.net, price.vat, price.total) == (
        Decimal("179.91"),
        Decimal("44.97"),
        Decimal("224.88"),
    )


def test_expired_discount_is_still_applied(load_price_module):
    module = load_price_module(
        FakeConnection(
            discount_code="GAMMAL15",
            lines=[(1, Decimal("649.00"))],
            discount_percent=15,
        )
    )

    price = module.calc_price(1045, module._fake_connection)

    assert (price.net, price.vat, price.total) == (
        Decimal("551.65"),
        Decimal("137.91"),
        Decimal("689.56"),
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("1.239"), Decimal("1.23")),
        (Decimal("-1.239"), Decimal("-1.23")),
    ],
)
def test_truncation_is_toward_zero(load_price_module, value, expected):
    module = load_price_module(FakeConnection())

    assert module._kapa(value) == expected


def test_negative_amount_preserves_truncation_and_vat_behavior(load_price_module):
    module = load_price_module(FakeConnection(lines=[(1, Decimal("-1.239"))]))

    price = module.calc_price(1048, module._fake_connection)

    assert (price.net, price.vat, price.total) == (
        Decimal("-1.23"),
        Decimal("-0.3"),
        Decimal("-1.53"),
    )
    assert [str(value) for value in (price.net, price.vat, price.total)] == [
        "-1.23",
        "-0.3",
        "-1.53",
    ]


def test_missing_order_returns_none(load_price_module):
    module = load_price_module(FakeConnection(order_exists=False))

    assert module.calc_price(9999, module._fake_connection) is None


def test_empty_lines_and_unknown_discount_produce_zero(load_price_module):
    module = load_price_module(
        FakeConnection(discount_code="UNKNOWN", lines=[], discount_percent=None)
    )

    price = module.calc_price(1049, module._fake_connection)

    assert (price.net, price.vat, price.total) == (
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
    )
    assert [str(value) for value in (price.net, price.vat, price.total)] == [
        "0",
        "0",
        "0",
    ]


def test_order_id_and_discount_values_are_query_parameters(load_price_module):
    connection = FakeConnection(
        discount_code="VAR' OR 1=1 --",
        lines=[(1, Decimal("10.00"))],
        discount_percent=10,
    )
    module = load_price_module(connection)

    module.calc_price(1044, connection)

    assert [params for _, params in connection.queries] == [
        (1044,),
        (1044,),
        ("VAR' OR 1=1 --",),
    ]


def test_batch_price_calculation_preserves_results_with_constant_query_count(
    load_price_module,
):
    connection = FakeConnection(
        batch_orders={41: None, 42: "SALE10"},
        batch_lines=[
            (41, 2, Decimal("375.00")),
            (41, 1, Decimal("200.00")),
            (42, 1, Decimal("199.90")),
        ],
        batch_discounts={"SALE10": Decimal("10")},
    )
    module = load_price_module(connection)

    prices = module.calc_prices([41, 42], connection)

    assert {
        order_id: (price.net, price.vat, price.total)
        for order_id, price in prices.items()
    } == {
        41: (Decimal("950"), Decimal("237.5"), Decimal("1187.5")),
        42: (Decimal("179.91"), Decimal("44.97"), Decimal("224.88")),
    }
    individual_prices = {
        41: module.calc_price(
            41,
            FakeConnection(
                lines=[
                    (2, Decimal("375.00")),
                    (1, Decimal("200.00")),
                ],
            ),
        ),
        42: module.calc_price(
            42,
            FakeConnection(
                discount_code="SALE10",
                lines=[(1, Decimal("199.90"))],
                discount_percent=Decimal("10"),
            ),
        ),
    }
    assert {
        order_id: (price.net, price.vat, price.total)
        for order_id, price in individual_prices.items()
    } == {
        order_id: (price.net, price.vat, price.total)
        for order_id, price in prices.items()
    }
    assert len(connection.queries) == 3
    assert [query[1] for query in connection.queries] == [
        ([41, 42],),
        ([41, 42],),
        (["SALE10"],),
    ]


def test_characterized_price_values_keep_json_decimal_strings(load_price_module):
    module = load_price_module(
        FakeConnection(
            lines=[
                (2, Decimal("375.00")),
                (1, Decimal("200.00")),
            ]
        )
    )
    price = module.calc_price(1042, module._fake_connection)

    output = json.dumps(
        {"net": str(price.net), "vat": str(price.vat), "total": str(price.total)}
    )

    assert output == '{"net": "950", "vat": "237.5", "total": "1187.5"}'


def test_cli_preserves_json_decimal_strings(monkeypatch, capsys):
    connection = FakeConnection(
        lines=[(2, Decimal("375.00")), (1, Decimal("200.00"))]
    )
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost:1/fake_only")
    monkeypatch.setattr(psycopg, "connect", lambda *_args, **_kwargs: connection)
    monkeypatch.setattr(sys, "argv", [str(MODULE_PATH), "1042"])

    runpy.run_path(str(MODULE_PATH), run_name="__main__")

    assert capsys.readouterr().out == (
        '{"net": "950", "vat": "237.5", "total": "1187.5"}\n'
    )
    assert connection.closed


def test_cli_missing_order_preserves_error_json_and_exit_code(monkeypatch, capsys):
    connection = FakeConnection(order_exists=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost:1/fake_only")
    monkeypatch.setattr(psycopg, "connect", lambda *_args, **_kwargs: connection)
    monkeypatch.setattr(sys, "argv", [str(MODULE_PATH), "9999"])

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(MODULE_PATH), run_name="__main__")

    assert exit_info.value.code == 1
    assert capsys.readouterr().out == '{"error": "finns inte"}\n'
    assert connection.closed
