# price_calc.py
# prisberakning for ordrar. skriven 2019, flyttad hit fran gamla admin-systemet.
# OBS rör inte avrundningen, ekonomi har stämt av mot den.

import os, sys, json, datetime, logging
from decimal import Decimal
import psycopg

DB = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/butik")

MOMS = 25
LOGG = os.path.join(os.path.dirname(__file__), "price_calc.log")


def connect_db():
    return psycopg.connect(DB, autocommit=True)


class Pris:
    def __init__(self, net, vat, total):
        self.net = net
        self.vat = vat
        self.total = total


def _kapa(x):
    # två decimaler
    return Decimal(int(x * 100)) / 100


def calc_price(order_id, connection=None):
    if connection is None:
        with connect_db() as managed_connection:
            return _calc_price(order_id, managed_connection)
    return _calc_price(order_id, connection)


def calc_prices(order_ids, connection=None):
    if connection is None:
        with connect_db() as managed_connection:
            return _calc_prices(order_ids, managed_connection)
    return _calc_prices(order_ids, connection)


def _calc_price(order_id, connection):
    cur = connection.cursor()
    cur.execute("select discount_code from orders where id = %s", (order_id,))
    rad = cur.fetchone()
    if rad == None:
        return None
    kod = rad[0]

    cur.execute(
        "select quantity, unit_price from order_lines where order_id = %s",
        (order_id,),
    )
    summa = Decimal(0)
    lines = cur.fetchall()

    discount = None
    if kod:
        cur.execute("select percent from discounts where code = %s", (kod,))
        discount = cur.fetchone()

    return _calculate_price(order_id, kod, lines, discount)


def _calc_prices(order_ids, connection):
    order_ids = list(dict.fromkeys(order_ids))
    if not order_ids:
        return {}

    cur = connection.cursor()
    cur.execute(
        "select id, discount_code from orders where id = ANY(%s)",
        (order_ids,),
    )
    orders = dict(cur.fetchall())

    cur.execute(
        "select order_id, quantity, unit_price from order_lines "
        "where order_id = ANY(%s) order by order_id, id",
        (order_ids,),
    )
    lines_by_order = {}
    for order_id, quantity, unit_price in cur.fetchall():
        lines_by_order.setdefault(order_id, []).append((quantity, unit_price))

    discount_codes = list(dict.fromkeys(code for code in orders.values() if code))
    discounts = {}
    if discount_codes:
        cur.execute(
            "select code, percent from discounts where code = ANY(%s)",
            (discount_codes,),
        )
        discounts = dict(cur.fetchall())

    return {
        order_id: _calculate_price(
            order_id,
            discount_code,
            lines_by_order.get(order_id, ()),
            (discounts[discount_code],) if discount_code in discounts else None,
        )
        for order_id, discount_code in orders.items()
    }


def _calculate_price(order_id, discount_code, lines, discount):
    summa = Decimal(0)
    for quantity, unit_price in lines:
        summa = summa + quantity * unit_price
    if discount_code and discount:
        summa = summa - summa * discount[0] / 100

    net = _kapa(summa)
    vat = _kapa(net * MOMS / 100)
    total = net + vat

    try:
        with open(LOGG, "a") as log_file:
            log_file.write(
                "%s %s %s\n" % (datetime.datetime.now().isoformat(), order_id, total)
            )
    except OSError:
        logging.getLogger(__name__).warning(
            "Could not write legacy price calculation log."
        )

    return Pris(net, vat, total)


if __name__ == "__main__":
    p = calc_price(int(sys.argv[1]))
    if p is None:
        print(json.dumps({"error": "finns inte"}))
        sys.exit(1)
    print(json.dumps({"net": str(p.net), "vat": str(p.vat), "total": str(p.total)}))
