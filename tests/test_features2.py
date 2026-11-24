"""Recuperar contraseña, comentarios, métricas, gastos fijos, ticket y términos."""
import io
from datetime import date, timedelta

from conftest import APP, H, login, new_user

from tubolsillo import recurring


def test_register_requires_terms(client):
    r = client.post("/api/register", json={"email": "sinterminos@prueba.com", "password": "clave-segura-1", "name": "A"}, headers=H)
    assert r.status_code == 400 and "términos" in r.json["error"]


def test_password_reset_flow(client):
    new_user(client, "olvido@prueba.com")
    client.post("/api/logout", headers=H)
    r = client.post("/api/password/forgot", json={"email": "olvido@prueba.com"}, headers=H).json
    token = r["dev_link"].split("#reset/")[1]                     # local y sin mail: el link se devuelve para seguir
    # mismo resultado para un mail que no existe (no revela cuentas)
    other = client.post("/api/password/forgot", json={"email": "noexiste@prueba.com"}, headers=H).json
    assert other["ok"] and "dev_link" not in other
    assert client.post("/api/password/reset", json={"token": token, "password": "corta"}, headers=H).status_code == 400
    assert client.post("/api/password/reset", json={"token": token, "password": "nueva-clave-123"}, headers=H).status_code == 200
    assert client.get("/api/me").json["user"]["email"] == "olvido@prueba.com"
    # el link se usa una sola vez
    assert client.post("/api/password/reset", json={"token": token, "password": "otra-clave-456"}, headers=H).status_code == 400
    client.post("/api/logout", headers=H)
    assert client.post("/api/login", json={"email": "olvido@prueba.com", "password": "nueva-clave-123"}, headers=H).status_code == 200


def test_admin_can_generate_reset_link(client):
    new_user(APP.test_client(), "ayuda@prueba.com")
    login(client, "admin")
    r = client.post("/api/admin/reset-link", json={"email": "ayuda@prueba.com"}, headers=H).json
    assert "#reset/" in r["link"]
    assert client.post("/api/admin/reset-link", json={"email": "nadie@prueba.com"}, headers=H).status_code == 404


def test_feedback_reaches_admin(client):
    new_user(client, "opina@prueba.com")
    assert client.post("/api/feedback", json={"kind": "idea", "text": "x"}, headers=H).status_code == 400
    assert client.post("/api/feedback", json={"kind": "problema", "text": "No me cargó el gasto", "screen": "pagar"}, headers=H).status_code == 200
    adm = APP.test_client()
    login(adm, "admin")
    m = adm.get("/api/admin/metrics").json
    f = next(x for x in m["feedback"] if x["text"] == "No me cargó el gasto")
    assert f["kind"] == "problema" and f["screen"] == "pagar" and f["status"] == "nuevo"
    adm.put(f"/api/admin/feedback/{f['id']}", json={"seen": True}, headers=H)
    assert next(x for x in adm.get("/api/admin/metrics").json["feedback"] if x["id"] == f["id"])["status"] == "visto"


def test_metrics_shape_and_activity_tracking(client):
    new_user(client, "activo@prueba.com")
    client.get("/api/home")
    adm = APP.test_client()
    login(adm, "admin")
    m = adm.get("/api/admin/metrics").json
    assert m["active_7d"] >= 1 and len(m["weeks"]) == 8 and m["funnel"][0]["step"] == "Se registraron"
    assert m["funnel"][0]["n"] >= m["funnel"][1]["n"] >= m["funnel"][2]["n"]


def test_recurring_expenses(client, con):
    new_user(client, "fijos@prueba.com", ["mercadopago"])
    today = date.today()
    # un día que ya pasó este mes: no se carga solo hasta el mes que viene
    r = client.post("/api/recurring", json={"place_name": "Alquiler", "amount": 300000, "day_of_month": 1, "method_id": "mercadopago", "rubro": "hogar"}, headers=H)
    assert r.status_code == 200
    items = client.get("/api/recurring").json
    assert items[0]["place_name"] == "Alquiler"
    uid = client.get("/api/me").json["user"]["id"]
    n_before = con.execute("SELECT COUNT(*) FROM gastos WHERE user_id=?", (uid,)).fetchone()[0]
    if today.day > 1:
        assert n_before == 0
    # el mes que viene se carga solo, una sola vez
    nxt = (today.replace(day=28) + timedelta(days=5)).replace(day=2)
    recurring.run_due(con, nxt)
    recurring.run_due(con, nxt)
    rows = con.execute("SELECT * FROM gastos WHERE user_id=? AND place_name='Alquiler'", (uid,)).fetchall()
    assert len(rows) == n_before + 1 and rows[-1]["day"] == nxt.replace(day=1).isoformat()
    con.commit()   # liberar la base para que el servidor pueda escribir
    assert client.delete(f"/api/recurring/{items[0]['id']}", headers=H).status_code == 200
    assert client.post("/api/recurring", json={"place_name": "X", "amount": 10, "day_of_month": 40, "method_id": "mercadopago"}, headers=H).status_code == 400


def test_recurring_day_31_in_short_month():
    assert recurring.due_day(31, date(2026, 2, 10)) == 28
    assert recurring.due_day(15, date(2026, 2, 10)) == 15


def test_ticket_needs_ai(client):
    new_user(client, "ticket@prueba.com")
    r = client.post("/api/ticket", data={"image": (io.BytesIO(b"x"), "t.jpg")}, headers=H, content_type="multipart/form-data")
    assert r.status_code == 400 and "IA" in r.json["error"]


def test_ticket_with_ai_mocked(client, monkeypatch):
    import importlib
    from tubolsillo import bot
    extract = importlib.import_module("tubolsillo.bot.extract")
    monkeypatch.setattr(bot, "claude_available", lambda: True)
    monkeypatch.setattr(extract, "read_ticket", lambda path: {"merchant": "Súper Test", "amount": 1234.5, "date": "2999-01-01",
                                                              "method_id": "modo", "rubro": "super", "confidence": 0.9})
    new_user(client, "ticket2@prueba.com")
    r = client.post("/api/ticket", data={"image": (io.BytesIO(b"x"), "t.jpg")}, headers=H, content_type="multipart/form-data").json
    assert r["merchant"] == "Súper Test" and r["date"] is None          # una fecha futura se descarta


def test_export_includes_new_data(client):
    new_user(client, "exporta@prueba.com", ["mercadopago"])
    client.post("/api/recurring", json={"place_name": "Gimnasio", "amount": 20000, "day_of_month": 28, "method_id": "mercadopago"}, headers=H)
    client.post("/api/feedback", json={"kind": "otro", "text": "Muy buena la app"}, headers=H)
    d = client.get("/api/me/export").json
    assert d["recurring"][0]["place_name"] == "Gimnasio" and d["app_feedback"][0]["text"] == "Muy buena la app"
