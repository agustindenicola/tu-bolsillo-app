"""Leer páginas reales de beneficios: tarjetas, medio de la fuente, comercio, vigencia y fuentes recomendadas."""
from conftest import APP, H, login

from tubolsillo.bot import fuentes, run_bot
from tubolsillo.bot.extract import extract_rules
from tubolsillo.bot.fetch import html_to_cards, page_text

# formas reales en que las páginas escriben las promos (simplificadas)
BANCO = """<main><h2>Beneficios</h2><div class="grid">
<div class="card"><h4>30% de reintegro Burger King</h4><h4 class="mobile">30% de reintegro Burger King</h4><p>Tope de reintegro: $6.000</p><p>Todos los días</p><a>Ir a promo ›</a></div>
<div class="card"><h4>20% de reintegro Farmacity</h4><p>Tope de reintegro: $8.000</p><p>Todos los viernes</p></div>
<div class="card"><h4>10% de reintegro App YPF</h4><p>Todos los lunes</p></div>
</div></main>"""
BILLETERA = """<ul><li><div><span>Cooperativa Obrera</span><b>15%</b><span>Miércoles</span><span>Jueves</span></div></li>
<li><div><span>Farmalife</span><b>10%</b><span>Todos los días</span></div></li>
<li><div><span>Supermercado Dia</span><b>15%</b><span>Jueves</span></div></li></ul>"""
AGREGADOR = """<ul><li>20% en DIA : 20% de reintegro · DIA · vigente hasta 2999-03-28</li>
<li>25% en COTO : 25% de reintegro · COTO · vigente hasta 2999-02-28</li>
<li>30% en supermercados : 30% de reintegro · Supermercados · vigente hasta 2999-03-31</li></ul>"""
SEPARADO = """<section><div class="p"><h3>Al super con Cuenta DNI</h3><span>Lunes</span><div><span>20</span><span>%</span></div><span>de ahorro</span></div>
<div class="p"><h3>Comercios de cercanía</h3><span>Lunes a viernes</span><div><span>15</span><span>%</span></div><span>de ahorro</span></div>
<div class="p"><h3>Librerías</h3><span>Lunes y martes</span><div><span>10</span><span>%</span></div><span>de ahorro</span></div></section>"""


def test_cards_one_per_promo_without_repeated_titles():
    cards = html_to_cards(BANCO)
    assert len(cards) == 3
    assert cards[0].count("Burger King") == 1 and "Tope de reintegro: $6.000" in cards[0] and "Farmacity" not in cards[0]
    assert len(html_to_cards(SEPARADO)) == 3 and "20 %" in html_to_cards(SEPARADO)[0]


def test_bank_page_uses_source_method_and_reads_cap_and_days():
    ps = extract_rules(page_text(BANCO), "brubank")
    bk, fc, ypf = ps
    assert (bk["merchant"], bk["method_id"], bk["pct"], bk["cap_month"], bk["days"], bk["rubro"]) == ("Burger King", "brubank", 30, 6000, list(range(7)), "comida")
    assert (fc["merchant"], fc["days"], fc["rubro"]) == ("Farmacity", [4], "farmacia")
    assert (ypf["merchant"], ypf["days"], ypf["rubro"]) == ("App YPF", [0], "nafta")
    # sin medio de la fuente y sin nombrarlo, no se inventa
    assert extract_rules(page_text(BANCO)) == []


def test_wallet_page_merchant_before_percentage():
    ps = extract_rules(page_text(BILLETERA), "personalpay")
    assert [(p["merchant"], p["pct"], p["days"]) for p in ps] == [("Cooperativa Obrera", 15, [2, 3]), ("Farmalife", 10, list(range(7))), ("Supermercado Dia", 15, [3])]
    assert ps[0]["rubro"] == "super" and ps[1]["rubro"] == "farmacia"


def test_aggregator_reads_validity_and_generic_rubro():
    dia, coto, sup = extract_rules(page_text(AGREGADOR), "modo")
    assert (dia["merchant"], dia["valid_to"], dia["rubro"]) == ("DIA", "2999-03-28", "super")
    assert coto["merchant"] == "COTO" and coto["pct"] == 25
    assert sup["merchant"] is None and sup["rubro"] == "super"


def test_split_ranges_of_days_without_de():
    p = extract_rules(page_text(SEPARADO), "cuentadni")
    assert p[1]["days"] == [0, 1, 2, 3, 4] and p[2]["days"] == [0, 1]


def test_install_recommended_is_idempotent(con):
    n = fuentes.install(con, enable=False)
    assert n == len(fuentes.RECOMENDADAS) and fuentes.install(con, enable=False) == 0
    row = con.execute("SELECT * FROM sources WHERE url=?", (fuentes.RECOMENDADAS[0][1],)).fetchone()
    assert row["method_id"] == "modo" and row["enabled"] == 0
    con.execute("DELETE FROM sources WHERE url IN (%s)" % ",".join("?" * len(fuentes.RECOMENDADAS)), [r[1] for r in fuentes.RECOMENDADAS])


def test_bot_passes_source_method(con, monkeypatch):
    from tubolsillo.bot import fetch
    import importlib
    botmod = importlib.import_module("tubolsillo.bot")
    monkeypatch.setattr(botmod, "fetch_source", lambda src: page_text(BANCO) if src["kind"] == "html" else fetch.fetch_source(src))
    sid = con.execute("INSERT INTO sources(name, url, kind, enabled, tos_ok, method_id) VALUES('Banco prueba', 'https://banco.example/b', 'html', 1, 1, 'brubank')").lastrowid
    run_bot(con, only_source=sid)
    rows = con.execute("SELECT merchant, method_id, status FROM promos WHERE source_id=?", (sid,)).fetchall()
    assert {r["merchant"] for r in rows} == {"Burger King", "Farmacity", "App YPF"}
    assert all(r["method_id"] == "brubank" and r["status"] == "revision" for r in rows)   # sin IA, todo pasa por revisión
    con.commit()

    adm = APP.test_client()
    login(adm, "admin")
    d = adm.get("/api/admin").json
    src = next(s for s in d["sources"] if s["id"] == sid)
    assert src["pending"] == 3 and d["recommended_missing"] == len(fuentes.RECOMENDADAS)
    assert any(q.get("source_name") == "Banco prueba" for q in d["queue"])
    assert adm.post(f"/api/admin/sources/{sid}/approve-all", headers=H).json["approved"] == 3
    assert adm.put(f"/api/admin/sources/{sid}", json={"method_id": "macro"}, headers=H).status_code == 200
    src = next(s for s in adm.get("/api/admin").json["sources"] if s["id"] == sid)
    assert src["published"] == 3 and src["pending"] == 0 and src["method_id"] == "macro"
    adm.put(f"/api/admin/sources/{sid}", json={"enabled": False}, headers=H)


CALENDARIO = """<div class="grid">
<div class="card"><h5>Librería Ejemplo</h5><p>20% de descuento</p><div class="dias"><i></i><span>D</span><span>L</span><span>M</span><span>M</span><span class="active">J</span><span>V</span><span>S</span></div></div>
<div class="card"><div class="d-none">Nuevo</div><h5>Atlántica</h5><p>15% de descuento</p><div class="dias"><span>D</span><span class="active">L</span><span>M</span><span>M</span><span>J</span><span>V</span><span class="active">S</span></div></div>
<div class="card"><h5>Woopy</h5><p>10% de descuento</p><span hidden>2x1</span></div></div>"""


def test_highlighted_day_letters_and_hidden_labels():
    cards = html_to_cards(CALENDARIO)
    assert "Días: jueves" in cards[0] and "Nuevo" not in cards[1] and "2x1" not in cards[2]
    a, b, c = extract_rules(page_text(CALENDARIO), "ciudad")
    assert (a["merchant"], a["days"]) == ("Librería Ejemplo", [3])
    assert (b["merchant"], b["days"]) == ("Atlántica", [0, 5])
    assert c["merchant"] == "Woopy" and c["method_id"] == "ciudad"


def test_own_method_wins_when_page_mentions_modo():
    p = extract_rules("30% de ahorro en Heladería Sol pagando con MODO desde ICBC Mobile.", "icbc")[0]
    assert p["method_id"] == "icbc" and p["merchant"] == "Heladería Sol"


def test_same_business_by_whole_words():
    from tubolsillo.core import same_business
    assert same_business("Coto", "Coto Palermo") and same_business("DIA", "Supermercado Dia")
    assert not same_business("DIA", "Comedor Diana") and not same_business("Vea", "Veana Deco")
    assert same_business("Lucciano's", "Luccianos")


def test_more_merchant_shapes():
    assert extract_rules("Tienda Nova UNICO : 30% de reintegro · Tienda Nova · vigente hasta 2999-04-30", "modo")[0]["merchant"] == "Tienda Nova"
    assert extract_rules("Sin tope Ruiz y Roca 15% de descuento 10 cuotas sin interés", "ciudad")[0]["merchant"] == "Ruiz y Roca"
    assert extract_rules("30% de reintegro Rock & Feller’s Tope de reintegro: $30.000", "brubank")[0]["merchant"] == "Rock & Feller’s"
    assert extract_rules("30% de reintegro La cabrera Tope de reintegro: $30.000", "brubank")[0]["merchant"] is None   # mejor nada que «La»
    # varias promos pegadas en un bloque largo: no se mezclan
    pegadas = ("Miércoles 10 % de ahorro Beneficio en farmacias y perfumerías Miércoles y jueves 10 % Vamos al super sin excusas "
               "Jueves 20 % Date un gustito Sábado 30 % con Cuenta DNI")
    assert extract_rules(pegadas, "cuentadni") == []


def test_promos_gone_from_the_page_are_retired(con, monkeypatch):
    import importlib
    botmod = importlib.import_module("tubolsillo.bot")
    page = {"html": "<ul>" + "".join(f"<li>{10 + i}% de reintegro en Comercio{i} todos los días</li>" for i in range(6)) + "</ul>"}
    monkeypatch.setattr(botmod, "fetch_source", lambda src: page_text(page["html"]))
    sid = con.execute("INSERT INTO sources(name, url, kind, enabled, tos_ok, method_id) VALUES('Retiro', 'https://r.example', 'html', 1, 1, 'macro')").lastrowid
    run_bot(con, only_source=sid)
    assert con.execute("SELECT COUNT(*) FROM promos WHERE source_id=? AND status='revision'", (sid,)).fetchone()[0] == 6
    page["html"] = page["html"].replace("<li>15% de reintegro en Comercio5 todos los días</li>", "")   # una promo ya no está
    run_bot(con, only_source=sid)
    gone = con.execute("SELECT merchant FROM promos WHERE source_id=? AND status='vencida'", (sid,)).fetchall()
    assert [r["merchant"] for r in gone] == ["Comercio5"]
    page["html"] = "<p>Página en mantenimiento</p>"   # si la página carga mal, no se borra todo
    run_bot(con, only_source=sid)
    assert con.execute("SELECT COUNT(*) FROM promos WHERE source_id=? AND status='revision'", (sid,)).fetchone()[0] == 5
    con.execute("UPDATE sources SET enabled=0 WHERE id=?", (sid,))
    con.commit()
