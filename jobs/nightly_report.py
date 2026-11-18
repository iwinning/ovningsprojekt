# nattlig rapport: summerar dagens betalda ordrar. körs av cron på driftservern.
import os, sys, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "legacy"))
from price_calc import calc_prices, connect_db

def get_paid_order_ids(connection, report_date):
    cur = connection.cursor()
    cur.execute(
        "select id from orders where status = 'paid' and created_at::date = %s::date",
        (report_date,),
    )
    return cur.fetchall()


def create_report(connection, report_date, price_calculator=calc_prices):
    summa = 0
    order_ids = [oid for (oid,) in get_paid_order_ids(connection, report_date)]
    prices = price_calculator(order_ids, connection)
    for oid in order_ids:
        p = prices.get(oid)
        if p is None:
            raise RuntimeError("Pris kunde inte beräknas för en betald beställning.")
        summa += p.total
    return "%s: %d betalda ordrar, totalt %s kr" % (report_date, len(order_ids), summa)


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    report_date = args[0] if args else datetime.date.today().isoformat()
    with connect_db() as conn:
        print(create_report(conn, report_date))


if __name__ == "__main__":
    main()
