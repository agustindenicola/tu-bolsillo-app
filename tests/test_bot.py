"""El bot: entender promos, no duplicarlas, publicar o mandar a revisión, y aprender de las confirmaciones."""
from tubolsillo.bot import register_feedback, run_bot
from tubolsillo.bot.extract import extract_rules
from tubolsillo.bot.fetch import html_to_text
from tubolsillo.bot.verify import upsert_promo


def test_rules_understand_common_phrasings():
    t = ("25% de ahorro en Súper Ejemplo los jueves pagando con MODO. Tope de reintegro $4.000 por mes.\n\n"
         "Fines de semana 15% en ropa y calzado con BBVA.\n\n"
         "30% en Café Ejemplo de martes a jueves pagando con Ualá. Compra mínima $3.000. Tope $1.500.\n\n"
         "Texto sin promo con 10% pero sin medio de pago reconocible.")
    ps = extract_rules(t)
    assert len(ps) == 3
    a, b, c = ps
    assert (a["method_id"], a["pct"], a["days"], a["cap_month"]) == ("modo", 25, [3], 4000)
    assert (b["method_id"], b["days"], b["rubro"]) == ("bbva", [5, 6], "ropa")
    assert (c["method_id"], c["days"], c["min_amount"], c["cap_month"]) == ("uala", [1, 2, 3], 3000, 1500)


def test_rules_confidence_never_auto_publishes(con):
    # las reglas solas nunca superan el umbral: siempre pasan por revisión o por confirmaciones
    for p in extract_rules("20% todos los días en Farmacia Test con Mercado Pago. Tope $2.500 mensual."):
        _, _, status = upsert_promo(con, p, "bot", trust=0.9)
        assert status == "revision"


def test_html_to_text_keeps_one_block_per_card():
    html = "<ul><li><h3>Súper</h3><p>25% en X los lunes con MODO.</p></li><li><p>10% en Y con Ualá.</p></li></ul><script>var a='50% fake con modo'</script>"
    t = html_to_text(html)
    assert "fake" not in t and "25% en X" in t and "\n\n" in t


def test_dedupe_by_fingerprint(con):
    p = {"merchant": "Dedupe SA", "method_id": "modo", "pct": 10, "days": [1], "confidence": 0.9}
    a = upsert_promo(con, p, "bot", trust=1)
    b = upsert_promo(con, dict(p), "bot", trust=1)
    assert a[0] == b[0] and a[1] and not b[1]


def test_expired_promos_are_skipped(con):
    pid, is_new, status = upsert_promo(con, {"merchant": "Vieja", "method_id": "modo", "pct": 10, "days": [1], "valid_to": "2000-01-01"}, "bot")
    assert pid is None and status == "vencida"


def test_feedback_moves_bad_promo_to_review_and_lowers_source_trust(con):
    sid = con.execute("INSERT INTO sources(name, url, kind, enabled, tos_ok, trust) VALUES('S', 'x', 'html', 0, 1, 0.8)").lastrowid
    pid, _, _ = upsert_promo(con, {"merchant": "Quejas SA", "method_id": "modo", "pct": 20, "days": list(range(7)), "confidence": 1},
                             "bot", source_id=sid, trust=0.8, force_status="publicada")
    for _ in range(3):
        res = register_feedback(con, pid, False)
    assert res["status"] == "revision"
    assert con.execute("SELECT trust FROM sources WHERE id=?", (sid,)).fetchone()["trust"] < 0.8


def test_confirmations_publish_a_community_promo(con):
    pid, _, status = upsert_promo(con, {"merchant": "Comunidad SA", "method_id": "uala", "pct": 15, "days": [2], "confidence": 0.5},
                                  "usuario", trust=0.5, force_status="revision")
    assert status == "revision"
    for _ in range(3):
        res = register_feedback(con, pid, True)
    assert res["status"] == "publicada"


def test_links_promo_to_known_place(con):
    plid = con.execute("INSERT INTO places(name, rubro) VALUES('Almacén Don Pepe', 'super')").lastrowid
    pid, _, _ = upsert_promo(con, {"merchant": "Almacén Don Pepe", "method_id": "modo", "pct": 10, "days": [1], "confidence": 1}, "bot", trust=1)
    row = con.execute("SELECT place_id, rubro FROM promos WHERE id=?", (pid,)).fetchone()
    assert row["place_id"] == plid and row["rubro"] == "super"


def test_bot_run_with_fixture_source(con):
    stats = run_bot(con)
    assert stats["found"] >= 8 and not stats["errors"] and stats["extractor"] == "reglas"


def test_unreviewed_real_source_is_not_fetched(con):
    con.execute("INSERT INTO sources(name, url, kind, enabled, tos_ok) VALUES('Sin revisar', 'https://example.com/promos', 'html', 1, 0)")
    stats = run_bot(con)
    assert any("Sin revisar" in e and "términos" in e for e in stats["errors"])
    con.execute("UPDATE sources SET enabled=0 WHERE name='Sin revisar'")
