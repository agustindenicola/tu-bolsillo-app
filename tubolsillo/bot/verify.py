"""Verificar promos extraídas, decidir si se publican y aprender de las confirmaciones."""
import hashlib
from datetime import date

from ..core import norm, same_business
from ..db import get_setting


def fingerprint(p):
    key = "|".join([norm(p.get("merchant") or ""), p.get("rubro") or "", str(p.get("place_id") or ""), p["method_id"],
                    f"{float(p['pct']):g}", "".join(str(d) for d in sorted(p["days"]))])
    return hashlib.sha1(key.encode()).hexdigest()


def threshold(con):
    return float(get_setting(con, "publish_threshold", "0.75"))


def link_place(con, p):
    """Si la promo nombra un comercio que ya conocemos, la vincula (hereda rubro y ubicación)."""
    if p.get("place_id") or not p.get("merchant"):
        return p
    m = norm(p["merchant"])
    for pl in con.execute("SELECT id, name, rubro FROM places").fetchall():
        n = norm(pl["name"])
        if m and n and (m == n or (min(len(m), len(n)) >= 4 and same_business(m, n))):
            return {**p, "place_id": pl["id"], "rubro": p.get("rubro") or pl["rubro"]}
    return p


def upsert_promo(con, p, source, source_id=None, trust=0.6, source_url=None, is_example=False, created_by=None, force_status=None):
    """Guarda una promo extraída. Si ya existía, la refresca. Devuelve (id, nueva?, estado)."""
    p = link_place(con, p)
    today = date.today().isoformat()
    if p.get("valid_to") and p["valid_to"] < today:
        return None, False, "vencida"
    fp = fingerprint(p)
    conf = round(float(p.get("confidence", 0.5)) * (0.5 + trust / 2), 3)   # la confianza en la fuente pesa
    row = con.execute("SELECT id, status, confidence FROM promos WHERE fingerprint=?", (fp,)).fetchone()
    if row:
        con.execute("UPDATE promos SET last_seen=datetime('now','localtime'), confidence=MAX(confidence, ?), valid_to=COALESCE(?, valid_to) WHERE id=?",
                    (conf, p.get("valid_to"), row["id"]))
        return row["id"], False, row["status"]
    status = force_status or ("publicada" if conf >= threshold(con) else "revision")
    cur = con.execute(
        "INSERT INTO promos(place_id, merchant, rubro, method_id, pct, days, cap_month, min_amount, conditions, valid_to, org_id, "
        "source, source_id, source_url, confidence, status, is_example, fingerprint, raw_text, created_by) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (p.get("place_id"), p.get("merchant"), p.get("rubro"), p["method_id"], float(p["pct"]), "".join(str(d) for d in sorted(p["days"])),
         p.get("cap_month"), p.get("min_amount"), (p.get("conditions") or "")[:300] or None, p.get("valid_to"), p.get("org_id"),
         source, source_id, source_url, conf, status, int(is_example), fp, (p.get("raw_text") or "")[:600] or None, created_by))
    return cur.lastrowid, True, status


def expire_old(con):
    today = date.today().isoformat()
    return con.execute("UPDATE promos SET status='vencida' WHERE status IN ('publicada','revision') AND valid_to IS NOT NULL AND valid_to < ?",
                       (today,)).rowcount


def register_feedback(con, promo_id, ok, user_id=None):
    """«Me funcionó» / «No me la aplicaron». Ajusta la confianza de la promo y de su fuente.

    Si una promo acumula más fallas que aciertos (con al menos 3 fallas), vuelve a revisión.
    """
    con.execute("INSERT INTO feedback(user_id, promo_id, ok) VALUES(?,?,?)", (user_id, promo_id, int(bool(ok))))
    col = "ok_count" if ok else "fail_count"
    con.execute(f"UPDATE promos SET {col}={col}+1 WHERE id=?", (promo_id,))
    p = con.execute("SELECT * FROM promos WHERE id=?", (promo_id,)).fetchone()
    if not p:
        return None
    # confianza bayesiana: lo que dijo el extractor cuenta como 2 opiniones; cada usuario suma una
    conf = (p["confidence"] * 2 + p["ok_count"]) / (2 + p["ok_count"] + p["fail_count"])
    status = p["status"]
    if p["fail_count"] >= 3 and p["fail_count"] > p["ok_count"] and status == "publicada":
        status = "revision"
    elif status == "revision" and p["ok_count"] >= 3 and p["ok_count"] >= 3 * p["fail_count"] and p["source"] != "ejemplo":
        status = "publicada"
    con.execute("UPDATE promos SET confidence=?, status=? WHERE id=?", (round(conf, 3), status, promo_id))
    if p["source_id"]:
        con.execute(f"UPDATE sources SET {col}={col}+1 WHERE id=?", (p["source_id"],))
        s = con.execute("SELECT ok_count, fail_count FROM sources WHERE id=?", (p["source_id"],)).fetchone()
        con.execute("UPDATE sources SET trust=? WHERE id=?", (round((s["ok_count"] + 1.2) / (s["ok_count"] + s["fail_count"] + 2), 3), p["source_id"]))
    return {"confidence": round(conf, 3), "status": status}
