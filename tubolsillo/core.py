"""Lógica de la app: qué promo aplica, con qué conviene pagar, ahorro, niveles y personalización."""
import unicodedata
from collections import Counter, defaultdict
from datetime import date, timedelta

from .catalog import DAYS, DAYS_PLURAL, METHOD_BY_ID, RUBRO_BY_ID


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return " ".join(s.replace("-", " ").split())


def month_start(d):
    return d.replace(day=1).isoformat()


# ------------------------------------------------------------------ medios del usuario
def user_methods(con, uid):
    ms = {r["method_id"] for r in con.execute("SELECT method_id FROM user_methods WHERE user_id=?", (uid,))}
    ms.add("efectivo")          # el efectivo siempre está
    return ms


def user_org(con, uid):
    r = con.execute("SELECT org_id, role FROM users WHERE id=?", (uid,)).fetchone()
    return r["org_id"] if r and r["role"] == "user" else None


# ------------------------------------------------------------------ qué promo aplica
def same_business(a, b):
    """¿Es el mismo comercio? «Coto» = «Coto Palermo», pero «DIA» ≠ «Comedor Diana» (por palabras enteras, no letras)."""
    import re
    a, b = norm(a).replace("'", ""), norm(b).replace("'", "")
    if not a or not b:
        return False
    short, long_ = sorted((a, b), key=len)
    return bool(re.search(rf"(?:^|\s){re.escape(short)}(?:\s|$)", long_))


def promo_matches_place(p, place):
    """¿La promo vale en este lugar? Por comercio puntual, por cadena (nombre) o por rubro entero."""
    if p["place_id"]:
        return place.get("id") == p["place_id"]
    if p["merchant"]:
        return same_business(p["merchant"], place.get("name"))
    return bool(p["rubro"]) and p["rubro"] == place.get("rubro")


def promo_active(p, d):
    if p["status"] != "publicada":
        return False
    if str(d.weekday()) not in (p["days"] or ""):
        return False
    if p["valid_from"] and d.isoformat() < p["valid_from"]:
        return False
    if p["valid_to"] and d.isoformat() > p["valid_to"]:
        return False
    return True


def visible_promos(con, uid=None):
    """Promos publicadas que esta persona puede ver (las exclusivas de empresa solo para sus empleados)."""
    org = user_org(con, uid) if uid else None
    return con.execute(
        "SELECT p.*, pl.name AS place_name, pl.rubro AS place_rubro, pl.address AS place_address, pl.lat, pl.lng "
        "FROM promos p LEFT JOIN places pl ON pl.id=p.place_id "
        "WHERE p.status='publicada' AND (p.org_id IS NULL OR p.org_id=?)", (org or -1,)).fetchall()


def cap_left(con, uid, p, d):
    if not p["cap_month"]:
        return None
    used = con.execute("SELECT COALESCE(SUM(saved),0) FROM gastos WHERE user_id=? AND promo_id=? AND day>=?",
                       (uid, p["id"], month_start(d))).fetchone()[0]
    return max(0.0, p["cap_month"] - used)


def saving_for(con, uid, p, amount, d):
    if p["min_amount"] and amount < p["min_amount"]:
        return 0.0, cap_left(con, uid, p, d)
    raw = amount * p["pct"] / 100
    left = cap_left(con, uid, p, d)
    return (raw if left is None else min(raw, left)), left


def best_options(con, uid, place, amount, d=None):
    """Para un lugar y un monto: cuánto ahorrás con cada medio de pago que tenés, de mejor a peor."""
    d = d or date.today()
    mine = user_methods(con, uid)
    best = {}
    for p in visible_promos(con, uid):
        if p["method_id"] not in mine or not promo_matches_place(p, place) or not promo_active(p, d):
            continue
        s, left = saving_for(con, uid, p, amount, d)
        cur = best.get(p["method_id"])
        if cur is None or s > cur["saving"]:
            best[p["method_id"]] = {"method_id": p["method_id"], "pct": p["pct"], "saving": round(s, 2), "promo_id": p["id"],
                                    "cap_left": left, "capped": left is not None and amount * p["pct"] / 100 > left,
                                    "conditions": p["conditions"], "is_example": p["is_example"], "min_amount": p["min_amount"]}
    out = list(best.values())
    for m in mine:
        if m not in best:
            out.append({"method_id": m, "pct": 0, "saving": 0.0, "promo_id": None, "cap_left": None, "capped": False,
                        "conditions": None, "is_example": 0, "min_amount": None})
    out.sort(key=lambda o: (-o["saving"], -o["pct"], METHOD_BY_ID.get(o["method_id"], {}).get("kind") == "efectivo"))
    return out


# ------------------------------------------------------------------ gastos
def find_or_create_place(con, uid, name, rubro=None, place_id=None):
    if place_id:
        r = con.execute("SELECT * FROM places WHERE id=?", (place_id,)).fetchone()
        if r:
            return dict(r)
    name = (name or "").strip()[:120] or "Sin nombre"
    r = con.execute("SELECT * FROM places WHERE lower(name)=lower(?)", (name,)).fetchone()
    if r:
        return dict(r)
    rubro = rubro if rubro in RUBRO_BY_ID else guess_rubro(name)
    cur = con.execute("INSERT INTO places(name, rubro, created_by) VALUES(?,?,?)", (name, rubro, uid))
    return dict(con.execute("SELECT * FROM places WHERE id=?", (cur.lastrowid,)).fetchone())


def guess_rubro(text):
    t = norm(text)
    for rid, r in RUBRO_BY_ID.items():
        if any(norm(w) in t for w in r["words"]):
            return rid
    return "otros"


def record_gasto(con, uid, place, method_id, amount, d=None):
    """Guarda un gasto. Calcula lo ahorrado con el medio usado y lo que se perdió por no usar el mejor."""
    d = d or date.today()
    opts = best_options(con, uid, place, amount, d)
    chosen = next((o for o in opts if o["method_id"] == method_id), None) or {"saving": 0.0, "promo_id": None}
    top = opts[0] if opts else chosen
    missed = max(0.0, top["saving"] - chosen["saving"])
    cur = con.execute(
        "INSERT INTO gastos(user_id, place_id, place_name, rubro, method_id, amount, saved, missed, promo_id, day) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (uid, place.get("id"), place["name"], place.get("rubro") or "otros", method_id, amount, chosen["saving"], missed,
         chosen["promo_id"], d.isoformat()))
    if chosen["promo_id"]:
        con.execute("INSERT INTO promo_events(promo_id, kind) VALUES(?, 'use')", (chosen["promo_id"],))
    return {"id": cur.lastrowid, "saved": chosen["saving"], "missed": round(missed, 2), "promo_id": chosen["promo_id"],
            "best_method": top["method_id"] if missed > 0 else None}


def totals(con, uid, d=None):
    d = d or date.today()
    ms = month_start(d)
    q = lambda sql, *a: con.execute(sql, (uid, *a)).fetchone()[0] or 0  # noqa: E731
    return {
        "saved_total": round(q("SELECT SUM(saved) FROM gastos WHERE user_id=?"), 2),
        "saved_month": round(q("SELECT SUM(saved) FROM gastos WHERE user_id=? AND day>=?", ms), 2),
        "spent_month": round(q("SELECT SUM(amount) FROM gastos WHERE user_id=? AND day>=?", ms), 2),
        "missed_month": round(q("SELECT SUM(missed) FROM gastos WHERE user_id=? AND day>=?", ms), 2),
        "uses": q("SELECT COUNT(*) FROM gastos WHERE user_id=? AND saved>0"),
        "count_month": q("SELECT COUNT(*) FROM gastos WHERE user_id=? AND day>=?", ms),
    }


def monthly_series(con, uid, months=6, d=None):
    d = d or date.today()
    out = []
    y, m = d.year, d.month
    for _ in range(months):
        start = date(y, m, 1)
        end = date(y + (m == 12), m % 12 + 1, 1)
        r = con.execute("SELECT COALESCE(SUM(saved),0) s, COALESCE(SUM(amount),0) a FROM gastos WHERE user_id=? AND day>=? AND day<?",
                        (uid, start.isoformat(), end.isoformat())).fetchone()
        out.append({"month": start.isoformat()[:7], "saved": round(r["s"], 2), "spent": round(r["a"], 2)})
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return list(reversed(out))


# ------------------------------------------------------------------ personalización
def habits(con, uid, d=None, days_back=90):
    """Lo que la app aprende de los gastos de cada persona (últimos 90 días)."""
    d = d or date.today()
    rows = con.execute("SELECT * FROM gastos WHERE user_id=? AND day>=? ORDER BY day DESC",
                       (uid, (d - timedelta(days=days_back)).isoformat())).fetchall()
    n = len(rows)
    res = {"n": n, "weekday_rubro": [], "places": [], "cash_share": 0.0, "kind_share": {}, "rubro_share": {},
           "avg_ticket": {}, "prefer_kind": None, "missed_month": totals(con, uid, d)["missed_month"]}
    if not n:
        return res
    by_rubro = Counter(r["rubro"] for r in rows)
    res["rubro_share"] = {k: v / n for k, v in by_rubro.items()}
    wr = Counter((date.fromisoformat(r["day"]).weekday(), r["rubro"]) for r in rows)
    for (wd, rb), c in wr.most_common():
        if c >= 2 and c / by_rubro[rb] >= 0.4 and rb != "otros":
            res["weekday_rubro"].append({"weekday": wd, "rubro": rb, "count": c})
    pl = Counter(r["place_name"] for r in rows)
    res["places"] = [{"name": k, "count": v} for k, v in pl.most_common(5) if v >= 2]
    kinds = Counter(METHOD_BY_ID.get(r["method_id"], {}).get("kind", "otro") for r in rows)
    res["kind_share"] = {k: v / n for k, v in kinds.items()}
    res["cash_share"] = kinds.get("efectivo", 0) / n
    digital = {k: v for k, v in kinds.items() if k != "efectivo"}
    if digital:
        res["prefer_kind"] = max(digital, key=digital.get)
    amounts = defaultdict(list)
    for r in rows:
        amounts[r["rubro"]].append(r["amount"])
    res["avg_ticket"] = {k: sum(v) / len(v) for k, v in amounts.items()}
    return res


def insight_texts(h):
    """Frases para mostrar en «Aprendiendo de vos»."""
    out = []
    for x in h["weekday_rubro"][:2]:
        rb = RUBRO_BY_ID.get(x["rubro"], {}).get("name", x["rubro"]).lower()
        out.append({"icon": "◷", "text": f"Los <b>{DAYS_PLURAL[x['weekday']]}</b> solés gastar en {rb}: te avisamos la noche anterior las promos de {rb}.",
                    "tag": f"{rb.capitalize()} los {DAYS_PLURAL[x['weekday']]}"})
    if h["n"] >= 3 and h["cash_share"] >= 0.15:
        txt = f"Pagás <b>{round(h['cash_share'] * 10)} de cada 10</b> compras en efectivo."
        if h["missed_month"] > 0:
            txt += f" Este mes eso te hizo perder <b>$ {h['missed_month']:,.0f}</b> en descuentos.".replace(",", ".")
        out.append({"icon": "$", "text": txt, "tag": "Usás efectivo"})
    if h["prefer_kind"] == "billetera":
        out.append({"icon": "▣", "text": "Usás más <b>billeteras virtuales</b> que tarjetas: te mostramos primero las promos con QR.", "tag": "Preferís QR"})
    elif h["prefer_kind"] in ("banco", "tarjeta"):
        out.append({"icon": "▭", "text": "Pagás más con <b>tarjeta</b>: te mostramos primero las promos de tus bancos.", "tag": "Preferís tarjeta"})
    for p in h["places"][:1]:
        out.append({"icon": "★", "text": f"Vas seguido a <b>{p['name']}</b>: sus promos aparecen primero.", "tag": p["name"]})
    return out


def score_promo(p, h, place_rubro, user_kind_pref):
    """Qué tan útil es una promo para esta persona: descuento × relevancia según sus hábitos."""
    rel = 1.0
    rel += 1.5 * min(1.0, sum(x["count"] for x in h["places"] if norm(x["name"]) == norm(p["name"])) / 3)
    rel += 1.0 * h["rubro_share"].get(place_rubro, 0)
    if user_kind_pref and METHOD_BY_ID.get(p["method_id"], {}).get("kind") == user_kind_pref:
        rel += 0.3
    return p["pct"] * rel


def promos_for(con, uid, d=None, rubro=None, q=None, personal=True, only_mine=True):
    """Promos de un día, que la persona puede usar con sus medios, ordenadas por lo que le sirve."""
    d = d or date.today()
    mine = user_methods(con, uid)
    h = habits(con, uid, d) if personal else {"places": [], "rubro_share": {}, "weekday_rubro": []}
    pref = h.get("prefer_kind") if personal else None
    saved_ids = {r["promo_id"] for r in con.execute("SELECT promo_id FROM saves WHERE user_id=?", (uid,))}
    out = []
    for p in visible_promos(con, uid):
        if only_mine and p["method_id"] not in mine:
            continue
        if not promo_active(p, d):
            continue
        pr = p["place_rubro"] or p["rubro"] or "otros"
        if rubro and pr != rubro:
            continue
        name = p["place_name"] or p["merchant"] or RUBRO_BY_ID.get(pr, {}).get("generic", "Comercios adheridos")
        if q and norm(q) not in norm(f"{name} {METHOD_BY_ID.get(p['method_id'], {}).get('name', '')} {p['conditions'] or ''}"):
            continue
        item = promo_dict(p)
        item["score"] = score_promo(item, h, pr, pref) if personal else item["pct"]
        item["habit"] = personal and any(norm(x["name"]) == norm(name) for x in h["places"])
        item["saved"] = p["id"] in saved_ids
        if item["cap_month"]:
            item["cap_left"] = cap_left(con, uid, p, d)
        out.append(item)
    out.sort(key=lambda x: -x["score"])
    return out


def promo_dict(p):
    keys = p.keys()
    pr = (p["place_rubro"] if "place_rubro" in keys else None) or p["rubro"] or "otros"
    name = (p["place_name"] if "place_name" in keys else None) or p["merchant"] or RUBRO_BY_ID.get(pr, {}).get("generic", "Comercios adheridos")
    m = METHOD_BY_ID.get(p["method_id"], {"name": p["method_id"], "kind": "otro", "color": "#777"})
    return {"id": p["id"], "name": name, "place_id": p["place_id"], "rubro": pr, "method_id": p["method_id"], "method": m["name"],
            "method_kind": m["kind"], "method_color": m["color"], "pct": p["pct"], "days": p["days"], "cap_month": p["cap_month"],
            "min_amount": p["min_amount"], "conditions": p["conditions"], "valid_to": p["valid_to"], "source": p["source"],
            "confidence": round(p["confidence"], 2), "ok_count": p["ok_count"], "fail_count": p["fail_count"],
            "is_example": p["is_example"], "address": p["place_address"] if "place_address" in keys else None,
            "lat": p["lat"] if "lat" in keys else None, "lng": p["lng"] if "lng" in keys else None, "status": p["status"],
            "exclusive": bool(p["org_id"]), "source_url": p["source_url"] if str(p["source_url"] or "").startswith("https://") else None}


def tomorrow_digest(con, uid, d=None):
    """El aviso de la noche: las mejores promos de mañana según sus hábitos de ese día."""
    d = d or date.today()
    tm = d + timedelta(days=1)
    h = habits(con, uid, d)
    rubros = [x["rubro"] for x in h["weekday_rubro"] if x["weekday"] == tm.weekday()]
    items = promos_for(con, uid, tm)
    if rubros:
        items = [i for i in items if i["rubro"] in rubros] or items
    items = [i for i in items if not i["is_example"]] or items
    if not items:
        return None
    top = items[0]
    rb = RUBRO_BY_ID.get(top["rubro"], {}).get("name", "").lower()
    title = f"Mañana {DAYS[tm.weekday()].lower()}: {top['pct']:g}% en {top['name']}"
    body = f"Pagando con {top['method']}." + (f" Además hay {len(items) - 1} promos más para vos." if len(items) > 1 else "")
    if rubros:
        body = f"Los {DAYS_PLURAL[tm.weekday()]} solés gastar en {rb}. " + body
    return {"title": title, "body": body, "url": "#promos"}


def haversine_m(lat1, lng1, lat2, lng2):
    from math import asin, cos, radians, sin, sqrt
    dlat, dlng = radians(lat2 - lat1), radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 6371000 * 2 * asin(sqrt(a))


def nearby(con, uid, lat, lng, radius=600, d=None):
    """Comercios cerca con promo hoy (cuando la app está abierta y la persona dio permiso de ubicación)."""
    d = d or date.today()
    out = []
    for p in promos_for(con, uid, d, personal=True):
        if p["lat"] is None or p["lng"] is None:
            continue
        dist = haversine_m(lat, lng, p["lat"], p["lng"])
        if dist <= radius:
            p["distance_m"] = round(dist)
            out.append(p)
    out.sort(key=lambda p: (p["distance_m"], -p["pct"]))
    seen, uniq = set(), []
    for p in out:   # un aviso por comercio: el mejor descuento
        if p["name"] not in seen:
            seen.add(p["name"])
            uniq.append(p)
    return uniq
