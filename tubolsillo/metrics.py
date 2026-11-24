"""Números de uso para el panel de administración: ¿la gente la usa y vuelve?"""
from datetime import date, timedelta


def week_start(d):
    return d - timedelta(days=d.weekday())


def usage(con, today=None):
    today = today or date.today()
    users = "SELECT id FROM users WHERE role='user'"
    q = lambda sql, *a: con.execute(sql, a).fetchone()[0] or 0  # noqa: E731
    d7, d30 = (today - timedelta(days=6)).isoformat(), (today - timedelta(days=29)).isoformat()
    res = {
        "total": q(f"SELECT COUNT(*) FROM ({users})"),
        "new_7d": q("SELECT COUNT(*) FROM users WHERE role='user' AND created_at>=?", d7),
        "active_7d": q(f"SELECT COUNT(DISTINCT user_id) FROM activity WHERE day>=? AND user_id IN ({users})", d7),
        "active_30d": q(f"SELECT COUNT(DISTINCT user_id) FROM activity WHERE day>=? AND user_id IN ({users})", d30),
        "gastos_7d": q("SELECT COUNT(*) FROM gastos WHERE created_at>=?", d7),
        "feedback_new": q("SELECT COUNT(*) FROM app_feedback WHERE status='nuevo'"),
    }
    # últimas 8 semanas: personas activas y gastos cargados
    weeks = []
    ws = week_start(today)
    for i in range(7, -1, -1):
        a = ws - timedelta(weeks=i)
        b = a + timedelta(days=7)
        weeks.append({"week": a.isoformat(),
                      "active": q(f"SELECT COUNT(DISTINCT user_id) FROM activity WHERE day>=? AND day<? AND user_id IN ({users})", a.isoformat(), b.isoformat()),
                      "gastos": q("SELECT COUNT(*) FROM gastos WHERE created_at>=? AND created_at<?", a.isoformat(), b.isoformat())})
    res["weeks"] = weeks
    # retención: de los activos hace dos semanas, cuántos volvieron la semana pasada
    a2, a1 = ws - timedelta(weeks=2), ws - timedelta(weeks=1)
    prev = {r[0] for r in con.execute(f"SELECT DISTINCT user_id FROM activity WHERE day>=? AND day<? AND user_id IN ({users})", (a2.isoformat(), a1.isoformat()))}
    last = {r[0] for r in con.execute(f"SELECT DISTINCT user_id FROM activity WHERE day>=? AND day<? AND user_id IN ({users})", (a1.isoformat(), ws.isoformat()))}
    res["retention"] = {"base": len(prev), "returned": len(prev & last), "pct": round(len(prev & last) / len(prev) * 100) if prev else None}
    # recorrido: de registrarse a usarla seguido
    res["funnel"] = [
        {"step": "Se registraron", "n": res["total"]},
        {"step": "Eligieron medios de pago", "n": q(f"SELECT COUNT(DISTINCT user_id) FROM user_methods WHERE user_id IN ({users})")},
        {"step": "Cargaron un gasto", "n": q(f"SELECT COUNT(DISTINCT user_id) FROM gastos WHERE user_id IN ({users})")},
        {"step": "Cargaron 5 o más", "n": q(f"SELECT COUNT(*) FROM (SELECT user_id FROM gastos WHERE user_id IN ({users}) GROUP BY user_id HAVING COUNT(*)>=5)")},
        {"step": "Volvieron otra semana", "n": q(f"SELECT COUNT(*) FROM (SELECT user_id FROM activity WHERE user_id IN ({users}) "
                                                   "GROUP BY user_id HAVING COUNT(DISTINCT strftime('%Y-%W', day))>=2)")},
    ]
    return res
