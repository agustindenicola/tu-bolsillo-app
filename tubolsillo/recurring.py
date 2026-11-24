"""Gastos fijos: se cargan solos el día del mes que eligió cada persona."""
import calendar
from datetime import date

from . import core
from .push import notify


def due_day(dom, d):
    """El día que toca este mes (si eligió 31 y el mes tiene 30, el último día)."""
    return min(dom, calendar.monthrange(d.year, d.month)[1])


def run_due(con, d=None):
    d = d or date.today()
    month = d.isoformat()[:7]
    n = 0
    for r in con.execute("SELECT * FROM recurring WHERE (last_month IS NULL OR last_month<?)", (month,)).fetchall():
        if d.day < due_day(r["day_of_month"], d):
            continue
        place = core.find_or_create_place(con, r["user_id"], r["place_name"], r["rubro"])
        day = date(d.year, d.month, due_day(r["day_of_month"], d))
        res = core.record_gasto(con, r["user_id"], place, r["method_id"], r["amount"], day)
        con.execute("UPDATE recurring SET last_month=? WHERE id=?", (month, r["id"]))
        extra = f" Con la promo ahorraste $ {res['saved']:,.0f}.".replace(",", ".") if res["saved"] else ""
        notify(con, r["user_id"], "Gasto fijo cargado", f"Sumamos {r['place_name']} por $ {r['amount']:,.0f}.".replace(",", ".") + extra, "#gastos", "recurring")
        n += 1
    return n
