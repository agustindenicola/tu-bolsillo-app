"""Tareas automáticas: correr el bot cada tantas horas, mandar el aviso de la noche y vencer promos."""
import logging
import threading
import time
from datetime import date, datetime, timedelta

from . import bot, core, recurring
from .db import db, get_setting, set_setting
from .push import notify

log = logging.getLogger(__name__)


def run_bot_if_due(con, now=None):
    now = now or datetime.now()
    every = float(get_setting(con, "bot_every_hours", "6"))
    last = get_setting(con, "bot_last_run")
    if last and datetime.fromisoformat(last) > now - timedelta(hours=every):
        return None
    set_setting(con, "bot_last_run", now.isoformat(timespec="seconds"))
    stats = bot.run_bot(con)
    if stats["queued"]:
        for a in con.execute("SELECT id FROM users WHERE role='admin'").fetchall():
            notify(con, a["id"], "Promos para revisar", f"El bot encontró {stats['queued']} promos que necesitan tu revisión.", "#admin", "bot")
    return stats


def send_digests(con, now=None):
    """A la hora que eligió cada persona, el aviso con las mejores promos de mañana según sus hábitos."""
    now = now or datetime.now()
    today = now.date().isoformat()
    sent = 0
    users = con.execute("SELECT id FROM users WHERE role='user' AND onboarded=1 AND notify_hour=? AND (last_digest IS NULL OR last_digest<?)",
                        (now.hour, today)).fetchall()
    for u in users:
        con.execute("UPDATE users SET last_digest=? WHERE id=?", (today, u["id"]))
        dg = core.tomorrow_digest(con, u["id"], now.date())
        if dg:
            notify(con, u["id"], dg["title"], dg["body"], dg["url"], "digest")
            sent += 1
    return sent


def cap_alerts(con, d=None):
    """Aviso cuando a una promo que usás le queda poco tope este mes (una vez por promo y por mes)."""
    d = d or date.today()
    ms = core.month_start(d)
    rows = con.execute(
        "SELECT g.user_id, g.promo_id, SUM(g.saved) used, p.cap_month FROM gastos g JOIN promos p ON p.id=g.promo_id "
        "WHERE g.day>=? AND p.cap_month IS NOT NULL GROUP BY g.user_id, g.promo_id", (ms,)).fetchall()
    n = 0
    for r in rows:
        left = r["cap_month"] - r["used"]
        if 0 < left <= r["cap_month"] * 0.2:
            kind = f"cap-{r['promo_id']}-{ms[:7]}"
            if con.execute("SELECT 1 FROM notifications WHERE user_id=? AND kind=?", (r["user_id"], kind)).fetchone():
                continue
            p = core.promo_dict(con.execute("SELECT p.*, pl.name place_name, pl.rubro place_rubro, pl.address place_address, pl.lat, pl.lng "
                                            "FROM promos p LEFT JOIN places pl ON pl.id=p.place_id WHERE p.id=?", (r["promo_id"],)).fetchone())
            notify(con, r["user_id"], "Te queda poco tope", f"En {p['name']} con {p['method']} te quedan $ {left:,.0f} de reintegro este mes.".replace(",", "."),
                   "#promos", kind)
            n += 1
    return n


def tick():
    with db() as con:
        try:
            run_bot_if_due(con)
        except Exception:  # noqa: BLE001
            log.exception("Bot")
        try:
            recurring.run_due(con)
            send_digests(con)
            cap_alerts(con)
        except Exception:  # noqa: BLE001
            log.exception("Avisos")


def start():
    def loop():
        while True:
            tick()
            time.sleep(60)
    threading.Thread(target=loop, daemon=True, name="tareas").start()
