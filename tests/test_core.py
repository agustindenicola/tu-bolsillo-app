"""Lógica central: con qué conviene pagar, topes, ahorro perdido, niveles y hábitos."""
from datetime import date, timedelta

from tubolsillo import core
from tubolsillo.bot.verify import upsert_promo
from tubolsillo.learn import ARTICLES, suggestions


def thursday():
    t = date.today()
    return t - timedelta(days=(t.weekday() - 3) % 7)   # el último jueves (o hoy si es jueves)


def make_user(con, email, methods):
    uid = con.execute("INSERT INTO users(email, pass_hash, name, onboarded) VALUES(?, 'x', 'T', 1)", (email,)).lastrowid
    con.executemany("INSERT INTO user_methods(user_id, method_id) VALUES(?,?)", [(uid, m) for m in methods])
    return uid


def make_place(con, name, rubro="super"):
    return dict(con.execute("SELECT * FROM places WHERE id=?", (con.execute("INSERT INTO places(name, rubro) VALUES(?,?)", (name, rubro)).lastrowid,)).fetchone())


def test_best_option_respects_cap_and_methods(con):
    uid = make_user(con, "core1@x.com", ["modo"])
    pl = make_place(con, "Súper Prueba Uno")
    upsert_promo(con, {"place_id": pl["id"], "method_id": "modo", "pct": 25, "days": [3], "cap_month": 1000, "confidence": 1}, "admin", trust=1, force_status="publicada")
    upsert_promo(con, {"place_id": pl["id"], "method_id": "uala", "pct": 40, "days": [3], "confidence": 1}, "admin", trust=1, force_status="publicada")
    opts = core.best_options(con, uid, pl, 10000, thursday())
    assert opts[0]["method_id"] == "modo"                 # Ualá no es suyo: no se ofrece
    assert opts[0]["saving"] == 1000 and opts[0]["capped"]  # 25% de 10.000 = 2.500, pero el tope es 1.000
    assert any(o["method_id"] == "efectivo" for o in opts)  # el efectivo siempre está
    assert all(o["method_id"] != "uala" for o in opts)


def test_cap_is_consumed_by_previous_purchases(con):
    uid = make_user(con, "core2@x.com", ["modo"])
    pl = make_place(con, "Súper Prueba Dos")
    upsert_promo(con, {"place_id": pl["id"], "method_id": "modo", "pct": 20, "days": [3], "cap_month": 3000, "confidence": 1}, "admin", trust=1, force_status="publicada")
    d = thursday()
    first = core.record_gasto(con, uid, pl, "modo", 10000, d)
    assert first["saved"] == 2000
    second = core.best_options(con, uid, pl, 10000, d)[0]
    assert second["saving"] == 1000                         # solo quedan 1.000 de tope este mes


def test_missed_when_paying_cash(con):
    uid = make_user(con, "core3@x.com", ["mercadopago"])
    pl = make_place(con, "Farmacia Prueba", "farmacia")
    upsert_promo(con, {"place_id": pl["id"], "method_id": "mercadopago", "pct": 20, "days": list(range(7)), "confidence": 1}, "admin", trust=1, force_status="publicada")
    r = core.record_gasto(con, uid, pl, "efectivo", 5000)
    assert r["saved"] == 0 and r["missed"] == 1000 and r["best_method"] == "mercadopago"


def test_min_amount_and_inactive_days(con):
    uid = make_user(con, "core4@x.com", ["uala"])
    pl = make_place(con, "Café Prueba", "comida")
    upsert_promo(con, {"place_id": pl["id"], "method_id": "uala", "pct": 30, "days": [3], "min_amount": 3000, "confidence": 1}, "admin", trust=1, force_status="publicada")
    d = thursday()
    assert core.best_options(con, uid, pl, 2000, d)[0]["saving"] == 0          # no llega a la compra mínima
    assert core.best_options(con, uid, pl, 4000, d)[0]["saving"] == 1200
    assert core.best_options(con, uid, pl, 4000, d + timedelta(days=1))[0]["saving"] == 0   # viernes: no aplica


def test_rubro_wide_and_chain_promos(con):
    uid = make_user(con, "core5@x.com", ["cuentadni", "bbva"])
    upsert_promo(con, {"rubro": "nafta", "method_id": "cuentadni", "pct": 10, "days": list(range(7)), "confidence": 1}, "admin", trust=1, force_status="publicada")
    upsert_promo(con, {"merchant": "Cadena Zeta", "method_id": "bbva", "pct": 15, "days": list(range(7)), "confidence": 1}, "admin", trust=1, force_status="publicada")
    est = {"id": None, "name": "Estación cualquiera", "rubro": "nafta"}
    assert core.best_options(con, uid, est, 10000)[0]["saving"] == 1000
    suc = {"id": None, "name": "Cadena Zeta Sucursal Centro", "rubro": "ropa"}
    assert core.best_options(con, uid, suc, 10000)[0]["method_id"] == "bbva"


def test_learning_content_is_complete():
    ids = [a["id"] for a in ARTICLES]
    assert len(ids) == len(set(ids)) >= 15
    for a in ARTICLES:
        assert a["sections"] and all(sc["h"] and sc["p"] for sc in a["sections"]) and a["summary"]


def test_suggestions_follow_habits():
    cash = suggestions(0, {"cash_share": 0.5, "missed_month": 0}, True, set())
    assert cash[0]["id"] == "inflacion"
    rich = [a["id"] for a in suggestions(30000, {"cash_share": 0, "missed_month": 0}, True, {"remunerada", "plazofijo"})]
    assert "money-market" in rich and "remunerada" not in rich      # no repite lo ya leído
    assert suggestions(0, None, False, set())[0]["id"] == "fondo-emergencia"


def test_habits_detect_weekday_and_cash(con):
    uid = make_user(con, "core7@x.com", ["modo"])
    pl = make_place(con, "Súper Hábitos")
    k = make_place(con, "Kiosco Hábitos", "comida")
    d = thursday()
    for w in range(4):
        core.record_gasto(con, uid, pl, "modo", 20000, d - timedelta(weeks=w))
        core.record_gasto(con, uid, k, "efectivo", 1000, d - timedelta(weeks=w, days=1))
    h = core.habits(con, uid)
    assert any(x["weekday"] == 3 and x["rubro"] == "super" for x in h["weekday_rubro"])
    assert 0.4 <= h["cash_share"] <= 0.6
    tags = [i["tag"] for i in core.insight_texts(h)]
    assert "Súper los jueves" in tags and "Usás efectivo" in tags


def test_personal_ranking_puts_frequent_places_first(con):
    uid = make_user(con, "core8@x.com", ["modo", "uala"])
    fav = make_place(con, "Lugar Favorito", "comida")
    other = make_place(con, "Lugar Nuevo", "comida")
    for pl, pct in ((fav, 10), (other, 15)):
        upsert_promo(con, {"place_id": pl["id"], "method_id": "modo", "pct": pct, "days": list(range(7)), "confidence": 1}, "admin", trust=1, force_status="publicada")
    for i in range(4):
        core.record_gasto(con, uid, fav, "uala", 3000, date.today() - timedelta(days=i * 2))
    ranked = [p["name"] for p in core.promos_for(con, uid) if p["name"] in ("Lugar Favorito", "Lugar Nuevo")]
    assert ranked[0] == "Lugar Favorito"                      # aunque tenga menos %, va donde ya compra
    plain = [p["name"] for p in core.promos_for(con, uid, personal=False) if p["name"] in ("Lugar Favorito", "Lugar Nuevo")]
    assert plain[0] == "Lugar Nuevo"                          # sin personalizar: el mayor %


def test_exclusive_promos_only_for_members(con):
    org = con.execute("INSERT INTO orgs(name, kind, invite_code) VALUES('Org Test', 'empresa', 'ORG-T')").lastrowid
    member = make_user(con, "core9@x.com", ["mercadopago"])
    con.execute("UPDATE users SET org_id=? WHERE id=?", (org, member))
    outsider = make_user(con, "core10@x.com", ["mercadopago"])
    pl = make_place(con, "Óptica Exclusiva", "otros")
    upsert_promo(con, {"place_id": pl["id"], "method_id": "mercadopago", "pct": 30, "days": list(range(7)), "org_id": org, "confidence": 1}, "admin", trust=1, force_status="publicada")
    assert any(p["name"] == "Óptica Exclusiva" for p in core.promos_for(con, member))
    assert not any(p["name"] == "Óptica Exclusiva" for p in core.promos_for(con, outsider))
