"""La API: cuentas, seguridad, roles y privacidad."""
from conftest import APP, H, login, new_user


def test_writes_without_app_header_are_rejected(client):
    assert client.post("/api/login", json={}).status_code == 403


def test_register_validates_and_logs_in(client):
    r = client.post("/api/register", json={"email": "mal", "password": "x", "name": "A", "accept_terms": True}, headers=H)
    assert r.status_code == 400
    new_user(client, "nueva@prueba.com")
    me = client.get("/api/me").json
    assert me["user"]["email"] == "nueva@prueba.com" and me["methods"] == ["mercadopago"]
    assert client.post("/api/register", json={"email": "nueva@prueba.com", "password": "clave-segura-1", "name": "B", "accept_terms": True}, headers=H).status_code == 400


def test_login_wrong_password(client):
    new_user(client, "login@prueba.com")
    client.post("/api/logout", headers=H)
    assert client.post("/api/login", json={"email": "login@prueba.com", "password": "otra-cosa"}, headers=H).status_code == 400
    assert client.post("/api/login", json={"email": "login@prueba.com", "password": "clave-segura-1"}, headers=H).status_code == 200


def test_needs_login(client):
    assert client.get("/api/home").status_code == 401


def test_roles_are_enforced(client):
    login(client, "user")
    assert client.get("/api/admin").status_code == 403
    assert client.get("/api/org/comercio").status_code == 403
    client.post("/api/logout", headers=H)
    login(client, "admin")
    assert client.get("/api/admin").status_code == 200


def test_full_purchase_flow(client):
    new_user(client, "flujo@prueba.com", ["mercadopago"])
    o = client.post("/api/options", json={"place_name": "Farmacia del Centro", "amount": 10000}, headers=H).json
    assert o["options"][0]["method_id"] == "mercadopago" and o["options"][0]["saving"] > 0
    g = client.post("/api/gastos", json={"place_name": "Farmacia del Centro", "method_id": "efectivo", "amount": 10000}, headers=H).json
    assert g["missed"] > 0 and g["best_method_name"] == "Mercado Pago"
    lst = client.get("/api/gastos").json
    assert lst["missed"] == g["missed"]
    assert client.delete(f"/api/gastos/{g['id']}", headers=H).status_code == 200


def test_cannot_touch_other_users_data(client):
    new_user(client, "duenio@prueba.com")
    g = client.post("/api/gastos", json={"place_name": "Kiosco X", "method_id": "efectivo", "amount": 1000}, headers=H).json
    other = APP.test_client()
    new_user(other, "otro@prueba.com")
    assert other.delete(f"/api/gastos/{g['id']}", headers=H).status_code == 404


def test_future_dates_rejected(client):
    new_user(client, "futuro@prueba.com")
    r = client.post("/api/gastos", json={"place_name": "X", "method_id": "efectivo", "amount": 100, "day": "2999-01-01"}, headers=H)
    assert r.status_code == 400


def test_learning_is_open_and_marks_read(client):
    new_user(client, "leccion@prueba.com")
    d = client.get("/api/learn").json
    assert d["read"] == 0 and d["total"] >= 15 and d["suggestions"]
    a = client.get("/api/lessons/fci").json                         # todo disponible desde el principio
    assert a["sections"] and a["topic_name"] == "Invertir" and "quiz" not in a
    assert client.get("/api/learn").json["read"] == 1
    assert client.get("/api/lessons/no-existe").status_code == 404


def test_company_panel_hides_small_groups(client, con):
    org = con.execute("INSERT INTO orgs(name, kind, invite_code) VALUES('Chica SA', 'empresa', 'CHICA')").lastrowid
    con.execute("UPDATE users SET org_id=? WHERE email='empresa@tubolsillo.app'", (org,))
    con.commit()
    login(client, "empresa")
    d = client.get("/api/org/empresa").json
    assert d["visible"] is False and "saved_month" not in d
    con.execute("UPDATE users SET org_id=(SELECT id FROM orgs WHERE invite_code='EMPRESA-DEMO') WHERE email='empresa@tubolsillo.app'")


def test_join_company_with_code(client):
    new_user(client, "unirse@prueba.com")
    assert client.post("/api/me/join", json={"code": "NO-EXISTE"}, headers=H).status_code == 400
    assert client.post("/api/me/join", json={"code": "empresa-demo"}, headers=H).json["org"] == "Empresa Ejemplo SA"


def test_export_and_delete_account(client):
    new_user(client, "borrar@prueba.com")
    client.post("/api/gastos", json={"place_name": "Algo", "method_id": "efectivo", "amount": 500}, headers=H)
    data = client.get("/api/me/export").json
    assert data["cuenta"]["email"] == "borrar@prueba.com" and len(data["gastos"]) == 1
    assert client.delete("/api/me", json={"password": "mal"}, headers=H).status_code == 400
    assert client.delete("/api/me", json={"password": "clave-segura-1"}, headers=H).status_code == 200
    assert client.get("/api/me").json["user"] is None


def test_comercio_publishes_only_for_own_places(client, con):
    login(client, "comercio")
    own = client.get("/api/org/comercio").json["places"][0]["id"]
    foreign = con.execute("SELECT id FROM places WHERE org_id IS NULL LIMIT 1").fetchone()["id"]
    body = {"method_id": "modo", "pct": 12, "days": [1, 2]}
    assert client.post("/api/org/comercio/promos", json={**body, "place_id": foreign}, headers=H).status_code == 400
    assert client.post("/api/org/comercio/promos", json={**body, "place_id": own}, headers=H).json["status"] == "publicada"


def test_admin_cannot_enable_unreviewed_source(client):
    login(client, "admin")
    sid = client.post("/api/admin/sources", json={"name": "Banco X", "url": "https://example.com/beneficios"}, headers=H).json["id"]
    assert client.put(f"/api/admin/sources/{sid}", json={"enabled": True}, headers=H).status_code == 400
    assert client.put(f"/api/admin/sources/{sid}", json={"tos_ok": True, "enabled": True}, headers=H).status_code == 200
    client.put(f"/api/admin/sources/{sid}", json={"enabled": False}, headers=H)


def test_push_subscription_requires_https_endpoint(client):
    new_user(client, "push@prueba.com")
    bad = {"subscription": {"endpoint": "http://x", "keys": {"p256dh": "a", "auth": "b"}}}
    assert client.post("/api/push/subscribe", json=bad, headers=H).status_code == 400
    ok = {"subscription": {"endpoint": "https://push.example.com/abc", "keys": {"p256dh": "a", "auth": "b"}}}
    assert client.post("/api/push/subscribe", json=ok, headers=H).status_code == 200


def test_demo_admin_blocked_online(client, monkeypatch):
    from tubolsillo import server
    monkeypatch.setattr(server, "DEMO_ADMIN", False)
    assert client.post("/api/demo-login", json={"role": "admin"}, headers=H).status_code == 403
    assert client.get("/api/catalog").json["demo_admin"] is False
    assert client.post("/api/demo-login", json={"role": "user"}, headers=H).status_code == 200
