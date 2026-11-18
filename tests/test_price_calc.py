import importlib.util
import json
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
    ):
        self.order_exists = order_exists
        self.discount_code = discount_code
        self.lines = tuple(lines)
        self.discount_percent = discount_percent
        self.queries = []

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
        module.conn = connection
        module.LOGG = str(Path(__file__).parent)
        return module

    return load


def test_price_without_discount_preserves_decimal_values_and_text(load_price_module):
    module = load_price_module(
        FakeConnection(
            lines=[
                (2, Decimal("375.00")),
                (1, Decimal("200.00")),
            ]
        )
    )

    price = module.calc_price(1042)

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

    price = module.calc_price(1044)

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

    price = module.calc_price(1045)

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

    price = module.calc_price(1048)

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

    assert module.calc_price(9999) is None


def test_empty_lines_and_unknown_discount_produce_zero(load_price_module):
    module = load_price_module(
        FakeConnection(discount_code="UNKNOWN", lines=[], discount_percent=None)
    )

    price = module.calc_price(1049)

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

    module.calc_price(1044)

    assert [params for _, params in connection.queries] == [
        (1044,),
        (1044,),
        ("VAR' OR 1=1 --",),
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
    price = module.calc_price(1042)

    output = json.dumps(
        {"net": str(price.net), "vat": str(price.vat), "total": str(price.total)}
    )

    assert output == '{"net": "950", "vat": "237.5", "total": "1187.5"}'
