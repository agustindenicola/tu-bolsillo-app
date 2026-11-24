"""Servidor web de Tu Bolsillo: API + la app instalable (PWA)."""
import json
import logging
import os
import re
import secrets
import time
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from functools import wraps

from flask import Flask, abort, g, jsonify, request, send_from_directory, session
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash

import hashlib

from . import bot, core, mail, metrics, push, recurring
from .bot import fuentes as bot_fuentes
from .catalog import DAYS, DAYS_SHORT, GLOSSARY, KIND_LABEL, METHOD_BY_ID, METHODS, RUBRO_BY_ID, RUBROS
from .learn import ARTICLE_BY_ID, ARTICLES, TOPICS, suggestions
from .db import UPLOAD_DIR, db, get_setting, init_db, set_setting

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
DEMO = os.environ.get("TUBOLSILLO_DEMO", "1") == "1"
ONLINE = os.environ.get("TUBOLSILLO_HTTPS") == "1"          # publicada en internet (detrás del https del hosting)
DEMO_ADMIN = not ONLINE or os.environ.get("TUBOLSILLO_DEMO_ADMIN") == "1"
app = Flask(__name__, static_folder=None)
if ONLINE:
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax", MAX_CONTENT_LENGTH=8 * 1024 * 1024,
                  PERMANENT_SESSION_LIFETIME=timedelta(days=60),
                  SESSION_COOKIE_SECURE=os.environ.get("TUBOLSILLO_HTTPS") == "1")
log = logging.getLogger("tubolsillo")
_login_attempts = defaultdict(list)


# ------------------------------------------------------------------ utilidades
@app.errorhandler(HTTPException)
def http_error(e):
    if request.path.startswith("/api/"):
        return jsonify(error=e.description), e.code
    return e


@app.errorhandler(Exception)
def any_error(e):
    log.exception("Error en %s", request.path)
    return jsonify(error="Algo salió mal. Probá de nuevo en un momento."), 500


@app.before_request
def guard():
    # protección contra pedidos de otros sitios: toda escritura viene de nuestra app con este encabezado
    if request.path.startswith("/api/") and request.method not in ("GET", "HEAD") and request.headers.get("X-TB") != "1":
        abort(403, "Pedido no permitido")


@app.before_request
def track_activity():
    if "uid" in session and request.path.startswith("/api/") and session.get("act_day") != date.today().isoformat():
        with db() as con:
            con.execute("INSERT OR IGNORE INTO activity(user_id, day) VALUES(?,?)", (session["uid"], date.today().isoformat()))
            con.execute("UPDATE users SET last_seen=datetime('now','localtime') WHERE id=?", (session["uid"],))
        session["act_day"] = date.today().isoformat()


@app.after_request
def headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "same-origin"
    if request.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


def body():
    return request.get_json(silent=True) or {}


def num(v, field, lo=0, hi=1e10, allow_none=False):
    if v in (None, ""):
        if allow_none:
            return None
        abort(400, f"Falta {field}")
    try:
        x = float(str(v).replace(".", "").replace(",", ".")) if isinstance(v, str) and re.fullmatch(r"[\d.]+,\d+|\d{1,3}(\.\d{3})+", v.strip()) else float(v)
    except (TypeError, ValueError):
        abort(400, f"{field} no es un número válido")
    if not lo <= x <= hi:
        abort(400, f"{field} está fuera de rango")
    return x


def current_user():
    if "uid" not in session:
        return None
    if "user" not in g:
        with db() as con:
            r = con.execute("SELECT * FROM users WHERE id=?", (session["uid"],)).fetchone()
        g.user = dict(r) if r else None
    return g.user


def login_required(role=None):
    def deco(fn):
        @wraps(fn)
        def inner(*a, **k):
            u = current_user()
            if not u:
                abort(401, "Iniciá sesión para seguir")
            if role and u["role"] != role and u["role"] != "admin":
                abort(403, "Esta sección es solo para cuentas de " + {"comercio": "comercios", "empresa": "empresas", "admin": "administración"}[role])
            return fn(u, *a, **k)
        return inner
    return deco


def parse_day(v):
    if not v:
        return date.today()
    if re.fullmatch(r"[0-6]", str(v)):   # un día de la semana: la próxima vez que cae
        t = date.today()
        return t + timedelta(days=(int(v) - t.weekday()) % 7)
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        abort(400, "Fecha inválida")


def place_from_body(con, u, b):
    if b.get("place_id"):
        r = con.execute("SELECT * FROM places WHERE id=?", (int(b["place_id"]),)).fetchone()
        if not r:
            abort(400, "Ese lugar no existe")
        return dict(r)
    name = (b.get("place_name") or "").strip()
    if not name:
        abort(400, "Decinos dónde")
    return core.find_or_create_place(con, u["id"], name, b.get("rubro"))


def methods_of(con, uid):
    return sorted(core.user_methods(con, uid) - {"efectivo"})


# ------------------------------------------------------------------ app instalable
@app.get("/")
def index():
    return send_from_directory(STATIC, "index.html")


@app.get("/sw.js")
def sw():
    resp = send_from_directory(STATIC, "sw.js")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["Service-Worker-Allowed"] = "/"
    return resp


@app.get("/manifest.webmanifest")
def manifest():
    return send_from_directory(STATIC, "manifest.webmanifest", mimetype="application/manifest+json")


@app.get("/static/<path:p>")
def static_files(p):
    return send_from_directory(STATIC, p)


# ------------------------------------------------------------------ cuentas
def start_session(uid):
    session.clear()
    session.permanent = True
    session["uid"] = uid


@app.post("/api/register")
def register():
    b = body()
    email = (b.get("email") or "").strip().lower()
    name = (b.get("name") or "").strip()[:60]
    pw = b.get("password") or ""
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        abort(400, "Ese mail no parece válido")
    if len(pw) < 8:
        abort(400, "La contraseña tiene que tener al menos 8 caracteres")
    if not name:
        abort(400, "Decinos tu nombre")
    if not b.get("accept_terms"):
        abort(400, "Para crear la cuenta tenés que aceptar los términos y la política de privacidad")
    with db() as con:
        if con.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            abort(400, "Ya hay una cuenta con ese mail")
        uid = con.execute("INSERT INTO users(email, pass_hash, name, accepted_terms) VALUES(?,?,?,datetime('now','localtime'))",
                          (email, generate_password_hash(pw), name)).lastrowid
        con.execute("INSERT INTO notifications(user_id, title, body, url, kind) VALUES(?,?,?,?,?)",
                    (uid, f"¡Hola, {name}!", "Elegí con qué pagás y empezá a ahorrar en cada compra.", "#inicio", "welcome"))
    start_session(uid)
    return jsonify(ok=True)


@app.post("/api/login")
def login():
    b = body()
    ip = request.remote_addr or "?"
    now = time.time()
    _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < 600]
    if len(_login_attempts[ip]) >= 10:
        abort(429, "Demasiados intentos. Esperá unos minutos.")
    with db() as con:
        r = con.execute("SELECT id, pass_hash FROM users WHERE email=?", ((b.get("email") or "").strip().lower(),)).fetchone()
    if not r or not check_password_hash(r["pass_hash"], b.get("password") or ""):
        _login_attempts[ip].append(now)
        abort(400, "Mail o contraseña incorrectos")
    start_session(r["id"])
    return jsonify(ok=True)


@app.post("/api/demo-login")
def demo_login():
    if not DEMO:
        abort(404)
    role = body().get("role", "user")
    if role == "admin" and not DEMO_ADMIN:
        abort(403, "La cuenta de administración de ejemplo no está disponible online")
    email = {"user": "demo@tubolsillo.app", "comercio": "comercio@tubolsillo.app", "empresa": "empresa@tubolsillo.app", "admin": "admin@tubolsillo.app"}.get(role)
    with db() as con:
        r = con.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if not r:
        abort(404, "No hay datos de ejemplo cargados")
    start_session(r["id"])
    return jsonify(ok=True)


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@app.get("/api/catalog")
def catalog():
    return jsonify(methods=METHODS, rubros=RUBROS, days=DAYS, days_short=DAYS_SHORT, kinds=KIND_LABEL,
                   glossary=GLOSSARY, demo=DEMO, demo_admin=DEMO and DEMO_ADMIN, ai=bot.claude_available(), mail=mail.configured())


@app.get("/api/me")
def me():
    u = current_user()
    if not u:
        return jsonify(user=None, demo=DEMO)
    with db() as con:
        org = con.execute("SELECT id, name, kind FROM orgs WHERE id=?", (u["org_id"],)).fetchone() if u["org_id"] else None
        unread = con.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND read=0", (u["id"],)).fetchone()[0]
        pub = push.vapid_public_key(con)
        subs = con.execute("SELECT COUNT(*) FROM push_subs WHERE user_id=?", (u["id"],)).fetchone()[0]
        return jsonify(user={k: u[k] for k in ("id", "email", "name", "role", "personal", "notify_hour", "onboarded")},
                       methods=methods_of(con, u["id"]), org=dict(org) if org else None, unread=unread, vapid=pub,
                       push_devices=subs, demo=DEMO, demo_account=u["email"].endswith("@tubolsillo.app"))


@app.put("/api/me")
@login_required()
def update_me(u):
    b = body()
    with db() as con:
        if "name" in b and str(b["name"]).strip():
            con.execute("UPDATE users SET name=? WHERE id=?", (str(b["name"]).strip()[:60], u["id"]))
        if "methods" in b:
            ms = [m for m in b["methods"] if m in METHOD_BY_ID and m != "efectivo"]
            con.execute("DELETE FROM user_methods WHERE user_id=?", (u["id"],))
            con.executemany("INSERT INTO user_methods(user_id, method_id) VALUES(?,?)", [(u["id"], m) for m in ms])
        if "personal" in b:
            con.execute("UPDATE users SET personal=? WHERE id=?", (int(bool(b["personal"])), u["id"]))
        if "notify_hour" in b:
            con.execute("UPDATE users SET notify_hour=? WHERE id=?", (int(num(b["notify_hour"], "hora", 0, 23)), u["id"]))
        if b.get("onboarded"):
            con.execute("UPDATE users SET onboarded=1 WHERE id=?", (u["id"],))
    return jsonify(ok=True)


@app.post("/api/me/join")
@login_required()
def join_org(u):
    code = (body().get("code") or "").strip().upper()
    with db() as con:
        o = con.execute("SELECT * FROM orgs WHERE kind='empresa' AND invite_code=?", (code,)).fetchone()
        if not o:
            abort(400, "Ese código no existe. Pedíselo a Recursos Humanos.")
        con.execute("UPDATE users SET org_id=? WHERE id=?", (o["id"], u["id"]))
    return jsonify(ok=True, org=o["name"])


@app.get("/api/me/export")
@login_required()
def export_me(u):
    with db() as con:
        data = {t: [dict(r) for r in con.execute(f"SELECT * FROM {t} WHERE user_id=?", (u["id"],))]
                for t in ("gastos", "goals", "lessons_done", "notifications", "user_methods", "saves", "recurring", "app_feedback")}
    data["cuenta"] = {k: u[k] for k in ("email", "name", "created_at")}
    resp = jsonify(data)
    resp.headers["Content-Disposition"] = "attachment; filename=mis-datos-tu-bolsillo.json"
    return resp


@app.delete("/api/me")
@login_required()
def delete_me(u):
    with db() as con:
        r = con.execute("SELECT pass_hash FROM users WHERE id=?", (u["id"],)).fetchone()
        if not check_password_hash(r["pass_hash"], body().get("password") or ""):
            abort(400, "La contraseña no es correcta")
        con.execute("UPDATE promos SET created_by=NULL WHERE created_by=?", (u["id"],))
        con.execute("UPDATE places SET created_by=NULL WHERE created_by=?", (u["id"],))
        con.execute("DELETE FROM users WHERE id=?", (u["id"],))
    session.clear()
    return jsonify(ok=True)


# ------------------------------------------------------------------ inicio
@app.get("/api/home")
@login_required()
def home(u):
    with db() as con:
        t = core.totals(con, u["id"])
        h = core.habits(con, u["id"]) if u["personal"] else None
        today = core.promos_for(con, u["id"], personal=bool(u["personal"]))[:6]
        goals = [dict(r) for r in con.execute("SELECT * FROM goals WHERE user_id=? ORDER BY id", (u["id"],))]
        read = {r["lesson_id"] for r in con.execute("SELECT lesson_id FROM lessons_done WHERE user_id=?", (u["id"],))}
        sug = suggestions(t["saved_total"], h, bool(goals), read)
        return jsonify(totals=t, today=today, goals=goals,
                       insights=core.insight_texts(h) if h else [], habits_n=h["n"] if h else 0,
                       suggestion={"id": sug[0]["id"], "title": sug[0]["title"], "min": sug[0]["min"], "summary": sug[0]["summary"]} if sug else None,
                       has_methods=bool(methods_of(con, u["id"])))


# ------------------------------------------------------------------ promos
@app.get("/api/promos")
@login_required()
def promos(u):
    d = parse_day(request.args.get("day"))
    with db() as con:
        items = core.promos_for(con, u["id"], d, rubro=request.args.get("rubro") or None, q=request.args.get("q") or None,
                                personal=bool(u["personal"]), only_mine=request.args.get("all") != "1")
        if request.args.get("saved") == "1":
            items = [i for i in items if i["saved"]]
    return jsonify(day=d.isoformat(), weekday=d.weekday(), promos=items)


def promo_row(con, pid):
    r = con.execute("SELECT p.*, pl.name AS place_name, pl.rubro AS place_rubro, pl.address AS place_address, pl.lat, pl.lng "
                    "FROM promos p LEFT JOIN places pl ON pl.id=p.place_id WHERE p.id=?", (pid,)).fetchone()
    if not r:
        abort(404, "Esa promo no existe")
    return r


@app.get("/api/promos/<int:pid>")
@login_required()
def promo_detail(u, pid):
    with db() as con:
        r = promo_row(con, pid)
        if r["status"] != "publicada" and u["role"] != "admin":
            abort(404, "Esa promo ya no está disponible")
        if r["org_id"] and r["org_id"] != u["org_id"] and u["role"] == "user":
            abort(404, "Esa promo no está disponible para vos")
        con.execute("INSERT INTO promo_events(promo_id, kind) VALUES(?, 'view')", (pid,))
        p = core.promo_dict(r)
        p["cap_left"] = core.cap_left(con, u["id"], r, date.today())
        p["saved"] = bool(con.execute("SELECT 1 FROM saves WHERE user_id=? AND promo_id=?", (u["id"], pid)).fetchone())
        p["mine"] = p["method_id"] in core.user_methods(con, u["id"])
        place = {"id": r["place_id"], "name": p["name"], "rubro": p["rubro"]}
        if r["place_id"] or r["merchant"]:
            p["options"] = core.best_options(con, u["id"], place, 10000)
    return jsonify(p)


@app.post("/api/promos/<int:pid>/save")
@login_required()
def promo_save(u, pid):
    with db() as con:
        promo_row(con, pid)
        if con.execute("SELECT 1 FROM saves WHERE user_id=? AND promo_id=?", (u["id"], pid)).fetchone():
            con.execute("DELETE FROM saves WHERE user_id=? AND promo_id=?", (u["id"], pid))
            return jsonify(saved=False)
        con.execute("INSERT INTO saves(user_id, promo_id) VALUES(?,?)", (u["id"], pid))
        con.execute("INSERT INTO promo_events(promo_id, kind) VALUES(?, 'save')", (pid,))
    return jsonify(saved=True)


@app.post("/api/promos/<int:pid>/feedback")
@login_required()
def promo_feedback(u, pid):
    ok = bool(body().get("ok"))
    with db() as con:
        promo_row(con, pid)
        if con.execute("SELECT 1 FROM feedback WHERE user_id=? AND promo_id=? AND created_at>=date('now','localtime')", (u["id"], pid)).fetchone():
            return jsonify(ok=True, repeated=True)
        res = bot.register_feedback(con, pid, ok, u["id"])
        if res and res["status"] == "revision":
            for a in con.execute("SELECT id FROM users WHERE role='admin'").fetchall():
                push.notify(con, a["id"], "Promo con quejas", "Varias personas dicen que una promo no les funcionó. Quedó para revisar.", "#admin", "bot")
    return jsonify(ok=True, **(res or {}))


@app.post("/api/promos/submit")
@login_required()
def promo_submit(u):
    text = (request.form.get("text") or "").strip()[:2000]
    link = (request.form.get("link") or "").strip()[:500]
    if link and not re.match(r"https?://", link):
        abort(400, "El link tiene que empezar con http:// o https://")
    f = request.files.get("image")
    path = None
    if f and f.filename:
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in (".jpg", ".jpeg", ".png", ".webp"):
            abort(400, "La imagen tiene que ser JPG, PNG o WEBP")
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}{ext}")
        f.save(path)
    if not (text or link or path):
        abort(400, "Subí una foto, pegá un link o escribí la promo")
    with db() as con:
        res = bot.read_user_submission(con, u["id"], text=text, image_path=path, link=link)
        if path and not res["promos"]:
            # sin IA no se puede leer la foto: queda guardada para que la lea una persona
            con.execute("INSERT INTO promos(method_id, pct, source, status, raw_text, created_by, conditions, confidence) VALUES(?,?,?,?,?,?,?,?)",
                        ("efectivo", 0, "usuario", "revision", f"[foto] {os.path.basename(path)} {text}".strip(), u["id"], "Foto para revisar", 0))
        for a in con.execute("SELECT id FROM users WHERE role='admin'").fetchall():
            push.notify(con, a["id"], "Nueva promo de un usuario", "Alguien sumó una promo. Está en la cola de revisión.", "#admin", "bot", push=False)
    return jsonify(res)


@app.get("/api/nearby")
@login_required()
def nearby(u):
    lat, lng = num(request.args.get("lat"), "lat", -90, 90), num(request.args.get("lng"), "lng", -180, 180)
    with db() as con:
        return jsonify(core.nearby(con, u["id"], lat, lng)[:3])


# ------------------------------------------------------------------ antes de pagar y gastos
@app.get("/api/places")
@login_required()
def places(u):
    q = (request.args.get("q") or "").strip()
    with db() as con:
        rows = con.execute("SELECT p.id, p.name, p.rubro, p.address, (SELECT COUNT(*) FROM gastos g WHERE g.place_id=p.id AND g.user_id=?) uses "
                           "FROM places p ORDER BY uses DESC, p.name", (u["id"],)).fetchall()
    out = [dict(r) for r in rows if not q or core.norm(q) in core.norm(r["name"])]
    return jsonify(out[:12])


@app.post("/api/options")
@login_required()
def options(u):
    b = body()
    amount = num(b.get("amount"), "el monto", 1, 1e9)
    with db() as con:
        place = place_from_body(con, u, b) if b.get("place_id") else {"id": None, "name": (b.get("place_name") or "").strip(),
                                                                        "rubro": b.get("rubro") or core.guess_rubro(b.get("place_name") or "")}
        if not place.get("id") and place["name"]:
            r = con.execute("SELECT * FROM places WHERE lower(name)=lower(?)", (place["name"],)).fetchone()
            if r:
                place = dict(r)
        return jsonify(place=place, options=core.best_options(con, u["id"], place, amount))


@app.post("/api/gastos")
@login_required()
def add_gasto(u):
    b = body()
    amount = num(b.get("amount"), "el monto", 1, 1e9)
    method = b.get("method_id")
    if method not in METHOD_BY_ID:
        abort(400, "Elegí cómo pagaste")
    d = parse_day(b.get("day")) if b.get("day") else date.today()
    if d > date.today():
        abort(400, "La fecha no puede ser futura")
    with db() as con:
        place = place_from_body(con, u, b)
        res = core.record_gasto(con, u["id"], place, method, amount, d)
        if res["best_method"]:
            res["best_method_name"] = METHOD_BY_ID[res["best_method"]]["name"]
        res["totals"] = core.totals(con, u["id"])
    return jsonify(res)


@app.get("/api/gastos")
@login_required()
def list_gastos(u):
    month = request.args.get("month") or date.today().isoformat()[:7]
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        abort(400, "Mes inválido")
    y, m = map(int, month.split("-"))
    start, end = date(y, m, 1), date(y + (m == 12), m % 12 + 1, 1)
    with db() as con:
        rows = [dict(r) for r in con.execute("SELECT * FROM gastos WHERE user_id=? AND day>=? AND day<? ORDER BY day DESC, id DESC",
                                             (u["id"], start.isoformat(), end.isoformat()))]
        series = core.monthly_series(con, u["id"], 6, start)
        totals = core.totals(con, u["id"])
    by_kind, by_rubro = Counter(), Counter()
    for r in rows:
        by_kind[METHOD_BY_ID.get(r["method_id"], {}).get("kind", "otro")] += r["amount"]
        by_rubro[r["rubro"]] += r["amount"]
    return jsonify(month=month, gastos=rows, spent=sum(r["amount"] for r in rows), saved=sum(r["saved"] for r in rows),
                   missed=sum(r["missed"] for r in rows), by_kind=by_kind, by_rubro=by_rubro, series=series, totals=totals)


@app.delete("/api/gastos/<int:gid>")
@login_required()
def del_gasto(u, gid):
    with db() as con:
        n = con.execute("DELETE FROM gastos WHERE id=? AND user_id=?", (gid, u["id"])).rowcount
    if not n:
        abort(404, "Ese gasto no existe")
    return jsonify(ok=True)


# ------------------------------------------------------------------ aprender
@app.get("/api/learn")
@login_required()
def learn(u):
    with db() as con:
        t = core.totals(con, u["id"])
        read = {r["lesson_id"] for r in con.execute("SELECT lesson_id FROM lessons_done WHERE user_id=?", (u["id"],))}
        goals = [dict(r) for r in con.execute("SELECT * FROM goals WHERE user_id=? ORDER BY id", (u["id"],))]
        rates = {k: float(get_setting(con, k, "0")) for k in ("ref_tna_plazo_fijo", "ref_tna_remunerada")}
        rates["fecha"] = get_setting(con, "ref_tna_fecha", "")
        h = core.habits(con, u["id"]) if u["personal"] else None
    card = lambda a: {"id": a["id"], "title": a["title"], "min": a["min"], "summary": a["summary"], "read": a["id"] in read}  # noqa: E731
    topics = [{**tp, "articles": [card(a) for a in ARTICLES if a["topic"] == tp["id"]]} for tp in TOPICS]
    return jsonify(saved=t["saved_total"], topics=topics, suggestions=[card(a) for a in suggestions(t["saved_total"], h, bool(goals), read)],
                   read=len(read & set(ARTICLE_BY_ID)), total=len(ARTICLES), goals=goals, rates=rates, glossary=GLOSSARY)


@app.get("/api/lessons/<lid>")
@login_required()
def lesson(u, lid):
    a = ARTICLE_BY_ID.get(lid) or abort(404, "Ese tema no existe")
    with db() as con:   # abrirlo cuenta como leído
        con.execute("INSERT OR IGNORE INTO lessons_done(user_id, lesson_id) VALUES(?,?)", (u["id"], lid))
    topic = next(tp for tp in TOPICS if tp["id"] == a["topic"])
    related = [{"id": x["id"], "title": x["title"]} for x in ARTICLES if x["topic"] == a["topic"] and x["id"] != lid]
    return jsonify({**a, "topic_name": topic["name"], "related": related})


@app.post("/api/goals")
@login_required()
def add_goal(u):
    b = body()
    name = (b.get("name") or "").strip()[:60] or abort(400, "Ponele un nombre al objetivo")
    target = num(b.get("target"), "el monto", 1000, 1e10)
    with db() as con:
        gid = con.execute("INSERT INTO goals(user_id, name, target) VALUES(?,?,?)", (u["id"], name, target)).lastrowid
    return jsonify(id=gid)


@app.delete("/api/goals/<int:gid>")
@login_required()
def del_goal(u, gid):
    with db() as con:
        con.execute("DELETE FROM goals WHERE id=? AND user_id=?", (gid, u["id"]))
    return jsonify(ok=True)


# ------------------------------------------------------------------ avisos
@app.get("/api/notifications")
@login_required()
def notifications(u):
    with db() as con:
        rows = [dict(r) for r in con.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 50", (u["id"],))]
        digest = core.tomorrow_digest(con, u["id"])
    return jsonify(items=rows, preview=digest)


@app.post("/api/notifications/read")
@login_required()
def notifications_read(u):
    with db() as con:
        con.execute("UPDATE notifications SET read=1 WHERE user_id=?", (u["id"],))
    return jsonify(ok=True)


@app.post("/api/push/subscribe")
@login_required()
def push_subscribe(u):
    s = body().get("subscription") or {}
    ep, keys = s.get("endpoint"), s.get("keys") or {}
    if not (ep and str(ep).startswith("https://") and keys.get("p256dh") and keys.get("auth")):
        abort(400, "Suscripción inválida")
    with db() as con:
        con.execute("INSERT INTO push_subs(user_id, endpoint, p256dh, auth) VALUES(?,?,?,?) "
                    "ON CONFLICT(endpoint) DO UPDATE SET user_id=excluded.user_id, p256dh=excluded.p256dh, auth=excluded.auth",
                    (u["id"], ep, keys["p256dh"], keys["auth"]))
    return jsonify(ok=True)


@app.post("/api/push/unsubscribe")
@login_required()
def push_unsubscribe(u):
    with db() as con:
        con.execute("DELETE FROM push_subs WHERE user_id=? AND endpoint=?", (u["id"], body().get("endpoint")))
    return jsonify(ok=True)


@app.post("/api/push/test")
@login_required()
def push_test(u):
    with db() as con:
        dg = core.tomorrow_digest(con, u["id"]) or {"title": "Tu Bolsillo", "body": "Así te van a llegar los avisos.", "url": "#inicio"}
        sent = push.notify(con, u["id"], dg["title"], dg["body"], dg["url"], "test")
    return jsonify(sent=sent)


# ------------------------------------------------------------------ panel para comercios
def org_places(con, u):
    return [dict(r) for r in con.execute("SELECT * FROM places WHERE org_id=? ORDER BY name", (u["org_id"],))] if u["org_id"] else []


@app.get("/api/org/comercio")
@login_required("comercio")
def comercio_panel(u):
    with db() as con:
        pls = org_places(con, u)
        ids = [p["id"] for p in pls] or [-1]
        qs = ",".join("?" * len(ids))
        promos_ = []
        for r in con.execute(f"SELECT p.*, pl.name place_name, pl.rubro place_rubro, pl.address place_address, pl.lat, pl.lng "
                             f"FROM promos p JOIN places pl ON pl.id=p.place_id WHERE p.place_id IN ({qs}) ORDER BY p.status, p.id DESC", ids):
            d = core.promo_dict(r)
            ev = Counter({e["kind"]: e["n"] for e in con.execute(
                "SELECT kind, COUNT(*) n FROM promo_events WHERE promo_id=? AND created_at>=datetime('now','-30 days') GROUP BY kind", (r["id"],))})
            d["stats"] = {"view": ev["view"], "save": ev["save"], "use": ev["use"]}
            promos_.append(d)
        tot = Counter()
        for p in promos_:
            tot.update(p["stats"])
        org = con.execute("SELECT name FROM orgs WHERE id=?", (u["org_id"],)).fetchone() if u["org_id"] else None
    return jsonify(org=org["name"] if org else None, places=pls, promos=promos_, totals=tot)


@app.post("/api/org/comercio/places")
@login_required("comercio")
def comercio_place(u):
    b = body()
    name = (b.get("name") or "").strip()[:120] or abort(400, "Falta el nombre del local")
    rubro = b.get("rubro") if b.get("rubro") in RUBRO_BY_ID else "otros"
    with db() as con:
        pid = con.execute("INSERT INTO places(name, rubro, address, lat, lng, org_id, created_by) VALUES(?,?,?,?,?,?,?)",
                          (name, rubro, (b.get("address") or "")[:200] or None, num(b.get("lat"), "lat", -90, 90, True),
                           num(b.get("lng"), "lng", -180, 180, True), u["org_id"], u["id"])).lastrowid
    return jsonify(id=pid)


def promo_from_form(b):
    days = sorted({int(x) for x in (b.get("days") or []) if str(x) in "0123456"})
    if not days:
        abort(400, "Elegí al menos un día")
    if b.get("method_id") not in METHOD_BY_ID:
        abort(400, "Elegí el medio de pago")
    vt = b.get("valid_to") or None
    if vt:
        vt = parse_day(vt).isoformat()
    return {"method_id": b["method_id"], "pct": num(b.get("pct"), "el porcentaje", 1, 90), "days": days,
            "cap_month": num(b.get("cap_month"), "el tope", 0, 1e9, True) or None, "min_amount": num(b.get("min_amount"), "la compra mínima", 0, 1e9, True) or None,
            "conditions": (b.get("conditions") or "").strip()[:300] or None, "valid_to": vt, "confidence": 0.95}


@app.post("/api/org/comercio/promos")
@login_required("comercio")
def comercio_promo(u):
    b = body()
    with db() as con:
        pls = {p["id"] for p in org_places(con, u)}
        if u["role"] != "admin" and int(b.get("place_id") or 0) not in pls:
            abort(400, "Elegí uno de tus locales")
        p = {**promo_from_form(b), "place_id": int(b["place_id"])}
        pid, is_new, status = bot.upsert_promo(con, p, "comercio", trust=1.0, created_by=u["id"], force_status="publicada")
        if not is_new:
            abort(400, "Ya tenés publicada una promo igual")
    return jsonify(id=pid, status=status)


@app.post("/api/org/comercio/promos/<int:pid>/end")
@login_required("comercio")
def comercio_promo_end(u, pid):
    with db() as con:
        r = promo_row(con, pid)
        if u["role"] != "admin" and r["place_id"] not in {p["id"] for p in org_places(con, u)}:
            abort(403, "Esa promo no es de tus locales")
        con.execute("UPDATE promos SET status='vencida', valid_to=date('now','localtime','-1 day') WHERE id=?", (pid,))
    return jsonify(ok=True)


# ------------------------------------------------------------------ panel para empresas (beneficio para empleados)
MIN_GROUP = 5   # con menos personas no se muestran totales, para que nadie sea identificable


@app.get("/api/org/empresa")
@login_required("empresa")
def empresa_panel(u):
    with db() as con:
        org = con.execute("SELECT * FROM orgs WHERE id=?", (u["org_id"],)).fetchone() if u["org_id"] else None
        if not org:
            abort(400, "Tu cuenta no tiene una empresa asociada")
        members = [r["id"] for r in con.execute("SELECT id FROM users WHERE org_id=? AND role='user'", (org["id"],))]
        n = len(members)
        res = {"org": org["name"], "code": org["invite_code"], "members": n, "min_group": MIN_GROUP, "visible": n >= MIN_GROUP}
        if n >= MIN_GROUP:
            qs = ",".join("?" * n)
            ms = core.month_start(date.today())
            res["active_month"] = con.execute(f"SELECT COUNT(DISTINCT user_id) FROM gastos WHERE user_id IN ({qs}) AND day>=?", (*members, ms)).fetchone()[0]
            res["saved_month"] = round(con.execute(f"SELECT COALESCE(SUM(saved),0) FROM gastos WHERE user_id IN ({qs}) AND day>=?", (*members, ms)).fetchone()[0])
            res["saved_total"] = round(con.execute(f"SELECT COALESCE(SUM(saved),0) FROM gastos WHERE user_id IN ({qs})", members).fetchone()[0])
            res["articles_read"] = con.execute(f"SELECT COUNT(*) FROM lessons_done WHERE user_id IN ({qs})", members).fetchone()[0]
        res["promos"] = [core.promo_dict(r) for r in con.execute(
            "SELECT p.*, pl.name place_name, pl.rubro place_rubro, pl.address place_address, pl.lat, pl.lng FROM promos p "
            "LEFT JOIN places pl ON pl.id=p.place_id WHERE p.org_id=? ORDER BY p.id DESC", (org["id"],))]
        res["places"] = [dict(r) for r in con.execute("SELECT id, name FROM places ORDER BY name")]
    return jsonify(res)


@app.post("/api/org/empresa/code")
@login_required("empresa")
def empresa_code(u):
    code = "EMP-" + secrets.token_hex(3).upper()
    with db() as con:
        con.execute("UPDATE orgs SET invite_code=? WHERE id=?", (code, u["org_id"]))
    return jsonify(code=code)


@app.post("/api/org/empresa/promos")
@login_required("empresa")
def empresa_promo(u):
    b = body()
    p = {**promo_from_form(b), "org_id": u["org_id"]}
    if b.get("place_id"):
        p["place_id"] = int(b["place_id"])
    elif b.get("merchant"):
        p["merchant"] = str(b["merchant"]).strip()[:120]
    else:
        p["rubro"] = b.get("rubro") if b.get("rubro") in RUBRO_BY_ID else abort(400, "Elegí un comercio o un rubro")
    with db() as con:
        pid, is_new, status = bot.upsert_promo(con, p, "admin", trust=1.0, created_by=u["id"], force_status="publicada")
    return jsonify(id=pid, status=status)


# ------------------------------------------------------------------ administración
@app.get("/api/admin")
@login_required("admin")
def admin_panel(u):
    with db() as con:
        queue = [core.promo_dict(r) | {"raw_text": r["raw_text"], "source_url": r["source_url"], "source": r["source"],
                                       "source_name": r["source_name"]} for r in con.execute(
            "SELECT p.*, pl.name place_name, pl.rubro place_rubro, pl.address place_address, pl.lat, pl.lng, s.name source_name FROM promos p "
            "LEFT JOIN places pl ON pl.id=p.place_id LEFT JOIN sources s ON s.id=p.source_id "
            "WHERE p.status='revision' AND (?=0 OR p.source_id=?) ORDER BY p.fail_count DESC, p.id DESC LIMIT 400",
            (int(request.args.get("source") or 0), int(request.args.get("source") or 0)))]
        sources = [dict(r) for r in con.execute(
            "SELECT s.*, (SELECT COUNT(*) FROM promos p WHERE p.source_id=s.id AND p.status='revision') pending, "
            "(SELECT COUNT(*) FROM promos p WHERE p.source_id=s.id AND p.status='publicada') published FROM sources s ORDER BY s.id")]
        recommended_missing = len({r[1] for r in bot_fuentes.RECOMENDADAS} - {s["url"] for s in sources})
        runs = [dict(r) for r in con.execute("SELECT * FROM bot_runs ORDER BY id DESC LIMIT 8")]
        stats = {k: con.execute(q).fetchone()[0] for k, q in {
            "usuarios": "SELECT COUNT(*) FROM users WHERE role='user'",
            "promos_publicadas": "SELECT COUNT(*) FROM promos WHERE status='publicada'",
            "en_revision": "SELECT COUNT(*) FROM promos WHERE status='revision'",
            "gastos_mes": f"SELECT COUNT(*) FROM gastos WHERE day>='{core.month_start(date.today())}'",
            "ahorro_total": "SELECT COALESCE(ROUND(SUM(saved)),0) FROM gastos",
            "dispositivos_push": "SELECT COUNT(*) FROM push_subs"}.items()}
        settings = {k: get_setting(con, k, "") for k in ("ref_tna_plazo_fijo", "ref_tna_remunerada", "ref_tna_fecha", "publish_threshold",
                                                        "bot_every_hours", "contact_email")}
    return jsonify(queue=queue, sources=sources, runs=runs, stats=stats, settings=settings, ai=bot.claude_available(),
                   recommended_missing=recommended_missing, not_readable=bot_fuentes.NO_LEGIBLES)


@app.post("/api/admin/promos/<int:pid>")
@login_required("admin")
def admin_promo(u, pid):
    b = body()
    with db() as con:
        r = promo_row(con, pid)
        if b.get("action") == "reject":
            con.execute("UPDATE promos SET status='rechazada' WHERE id=?", (pid,))
        elif b.get("action") == "approve":
            fields = {}
            if "pct" in b:
                fields["pct"] = num(b["pct"], "el porcentaje", 1, 90)
            if "method_id" in b and b["method_id"] in METHOD_BY_ID:
                fields["method_id"] = b["method_id"]
            if "days" in b:
                fields["days"] = "".join(sorted({str(int(x)) for x in b["days"] if str(x) in "0123456"})) or r["days"]
            if "cap_month" in b:
                fields["cap_month"] = num(b["cap_month"], "el tope", 0, 1e9, True) or None
            if "merchant" in b:
                fields["merchant"] = (b["merchant"] or "").strip()[:120] or None
            if "conditions" in b:
                fields["conditions"] = (b["conditions"] or "").strip()[:300] or None
            if r["pct"] <= 0 and "pct" not in fields:
                abort(400, "Completá el porcentaje antes de aprobar")
            sets = ", ".join(f"{k}=?" for k in fields)
            con.execute(f"UPDATE promos SET {sets + ', ' if sets else ''}status='publicada', confidence=MAX(confidence, 0.8) WHERE id=?",
                        (*fields.values(), pid))
            if r["source_id"]:   # que un humano apruebe también suma confianza a la fuente
                con.execute("UPDATE sources SET ok_count=ok_count+1, trust=MIN(0.98, trust+0.02) WHERE id=?", (r["source_id"],))
        else:
            abort(400, "Acción inválida")
    return jsonify(ok=True)


@app.post("/api/admin/sources/<int:sid>/approve-all")
@login_required("admin")
def admin_source_approve_all(u, sid):
    """Aprueba de una vez todo lo pendiente de una fuente (para cuando ya la revisaste y confiás en ella)."""
    with db() as con:
        con.execute("SELECT id FROM sources WHERE id=?", (sid,)).fetchone() or abort(404, "Esa fuente no existe")
        n = con.execute("UPDATE promos SET status='publicada', confidence=MAX(confidence, 0.8) WHERE source_id=? AND status='revision' AND pct>0",
                        (sid,)).rowcount
        if n:
            con.execute("UPDATE sources SET ok_count=ok_count+1, trust=MIN(0.98, trust+0.02) WHERE id=?", (sid,))
    return jsonify(approved=n)


@app.post("/api/admin/sources/recommended")
@login_required("admin")
def admin_sources_recommended(u):
    with db() as con:
        n = bot_fuentes.install(con)
    return jsonify(added=n)


@app.post("/api/admin/bot/run")
@login_required("admin")
def admin_bot_run(u):
    with db() as con:
        stats = bot.run_bot(con)
        set_setting(con, "bot_last_run", datetime.now().isoformat(timespec="seconds"))
    return jsonify(stats)


@app.post("/api/admin/sources")
@login_required("admin")
def admin_add_source(u):
    b = body()
    name = (b.get("name") or "").strip()[:80] or abort(400, "Falta el nombre")
    url = (b.get("url") or "").strip()
    if not re.match(r"https://", url):
        abort(400, "La dirección tiene que empezar con https://")
    with db() as con:
        method = b.get("method_id") if b.get("method_id") in METHOD_BY_ID else None
        kind = "navegador" if b.get("browser") else "html"
        sid = con.execute("INSERT INTO sources(name, url, kind, enabled, tos_ok, notes, method_id) VALUES(?,?,?, 0, 0, ?, ?)",
                          (name, url[:500], kind, (b.get("notes") or "")[:300], method)).lastrowid
    return jsonify(id=sid)


@app.put("/api/admin/sources/<int:sid>")
@login_required("admin")
def admin_edit_source(u, sid):
    b = body()
    with db() as con:
        s = con.execute("SELECT * FROM sources WHERE id=?", (sid,)).fetchone() or abort(404, "Esa fuente no existe")
        tos = int(bool(b.get("tos_ok", s["tos_ok"])))
        enabled = int(bool(b.get("enabled", s["enabled"])))
        if enabled and not tos and s["kind"] != "fixture":
            abort(400, "Antes de activarla, confirmá que revisaste sus términos de uso")
        trust = num(b.get("trust", s["trust"]), "la confianza", 0, 1)
        method = b.get("method_id", s["method_id"])
        method = method if method in METHOD_BY_ID else None
        con.execute("UPDATE sources SET enabled=?, tos_ok=?, trust=?, notes=?, method_id=? WHERE id=?",
                    (enabled, tos, trust, (b.get("notes", s["notes"]) or "")[:300], method, sid))
    return jsonify(ok=True)


@app.put("/api/admin/settings")
@login_required("admin")
def admin_settings(u):
    b = body()
    with db() as con:
        for k in ("ref_tna_plazo_fijo", "ref_tna_remunerada"):
            if k in b:
                set_setting(con, k, str(num(b[k], "la tasa", 0, 500)))
                set_setting(con, "ref_tna_fecha", date.today().isoformat())
        if "publish_threshold" in b:
            set_setting(con, "publish_threshold", str(num(b["publish_threshold"], "el umbral", 0.5, 1)))
        if "bot_every_hours" in b:
            set_setting(con, "bot_every_hours", str(num(b["bot_every_hours"], "las horas", 1, 168)))
        if "contact_email" in b and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", str(b["contact_email"])):
            set_setting(con, "contact_email", b["contact_email"])
    return jsonify(ok=True)


# ------------------------------------------------------------------ recuperar contraseña
RESET_HOURS = 2


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def make_reset_link(con, uid):
    token = secrets.token_urlsafe(32)
    con.execute("INSERT INTO password_resets(token_hash, user_id, expires_at) VALUES(?,?,datetime('now','localtime',?))",
                (_hash(token), uid, f"+{RESET_HOURS} hours"))
    return f"{request.host_url.rstrip('/')}/#reset/{token}"


@app.post("/api/password/forgot")
def password_forgot():
    email = (body().get("email") or "").strip().lower()
    ip = request.remote_addr or "?"
    now = time.time()
    _login_attempts["forgot-" + ip] = [t for t in _login_attempts["forgot-" + ip] if now - t < 3600]
    if len(_login_attempts["forgot-" + ip]) >= 5:
        abort(429, "Demasiados pedidos. Probá de nuevo en un rato.")
    _login_attempts["forgot-" + ip].append(now)
    res = {"ok": True, "mail": mail.configured()}
    with db() as con:
        r = con.execute("SELECT id, name FROM users WHERE email=?", (email,)).fetchone()
        if r:
            link = make_reset_link(con, r["id"])
            sent = mail.send(email, "Recuperá tu contraseña de Tu Bolsillo",
                             f"Hola, {r['name']}.\n\nPara elegir una contraseña nueva, entrá a este link (vale {RESET_HOURS} horas):\n\n{link}\n\n"
                             "Si no lo pediste vos, ignorá este mail: tu contraseña sigue igual.\n\nTu Bolsillo")
            if not sent:
                log.info("Link para recuperar contraseña de %s: %s", email, link)
                if not ONLINE:   # solo probando en la propia compu: se muestra el link para poder seguir
                    res["dev_link"] = link
    # misma respuesta exista o no la cuenta, para no revelar qué mails están registrados
    return jsonify(res)


@app.post("/api/password/reset")
def password_reset():
    b = body()
    pw = b.get("password") or ""
    if len(pw) < 8:
        abort(400, "La contraseña tiene que tener al menos 8 caracteres")
    with db() as con:
        r = con.execute("SELECT * FROM password_resets WHERE token_hash=? AND used=0 AND expires_at>datetime('now','localtime')",
                        (_hash(str(b.get("token") or "")),)).fetchone()
        if not r:
            abort(400, "El link venció o ya se usó. Pedí uno nuevo.")
        con.execute("UPDATE users SET pass_hash=? WHERE id=?", (generate_password_hash(pw), r["user_id"]))
        con.execute("UPDATE password_resets SET used=1 WHERE user_id=?", (r["user_id"],))
    start_session(r["user_id"])
    return jsonify(ok=True)


@app.post("/api/admin/reset-link")
@login_required("admin")
def admin_reset_link(u):
    email = (body().get("email") or "").strip().lower()
    with db() as con:
        r = con.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone() or abort(404, "No hay ninguna cuenta con ese mail")
        link = make_reset_link(con, r["id"])
    return jsonify(link=link, hours=RESET_HOURS)


# ------------------------------------------------------------------ «Contanos qué mejorar»
@app.post("/api/feedback")
@login_required()
def send_feedback(u):
    b = body()
    text = (b.get("text") or "").strip()[:2000]
    if len(text) < 3:
        abort(400, "Contanos un poco más")
    kind = b.get("kind") if b.get("kind") in ("idea", "problema", "otro") else "otro"
    with db() as con:
        con.execute("INSERT INTO app_feedback(user_id, kind, text, screen) VALUES(?,?,?,?)", (u["id"], kind, text, (b.get("screen") or "")[:40]))
        for a in con.execute("SELECT id FROM users WHERE role='admin'").fetchall():
            push.notify(con, a["id"], "Nuevo comentario" if kind != "problema" else "Alguien reportó un problema", text[:120], "#admin", "feedback")
    return jsonify(ok=True)


@app.put("/api/admin/feedback/<int:fid>")
@login_required("admin")
def admin_feedback(u, fid):
    with db() as con:
        con.execute("UPDATE app_feedback SET status=? WHERE id=?", ("visto" if body().get("seen", True) else "nuevo", fid))
    return jsonify(ok=True)


@app.get("/api/admin/metrics")
@login_required("admin")
def admin_metrics(u):
    with db() as con:
        res = metrics.usage(con)
        res["feedback"] = [dict(r) for r in con.execute(
            "SELECT f.*, u.name AS user_name, u.email AS user_email FROM app_feedback f LEFT JOIN users u ON u.id=f.user_id "
            "ORDER BY (f.status='nuevo') DESC, f.id DESC LIMIT 50")]
    return jsonify(res)


# ------------------------------------------------------------------ gastos fijos
@app.get("/api/recurring")
@login_required()
def list_recurring(u):
    with db() as con:
        return jsonify([dict(r) for r in con.execute("SELECT * FROM recurring WHERE user_id=? ORDER BY day_of_month", (u["id"],))])


@app.post("/api/recurring")
@login_required()
def add_recurring(u):
    b = body()
    name = (b.get("place_name") or "").strip()[:120] or abort(400, "Decinos qué es (ej: Alquiler, Internet)")
    if b.get("method_id") not in METHOD_BY_ID:
        abort(400, "Elegí con qué lo pagás")
    rubro = b.get("rubro") if b.get("rubro") in RUBRO_BY_ID else "servicios"
    amount = num(b.get("amount"), "el monto", 1, 1e9)
    dom = int(num(b.get("day_of_month"), "el día", 1, 31))
    today = date.today()
    # si el día ya pasó este mes, arranca el mes que viene (no se carga solo un gasto viejo)
    last = today.isoformat()[:7] if today.day > recurring.due_day(dom, today) else None
    with db() as con:
        rid = con.execute("INSERT INTO recurring(user_id, place_name, rubro, method_id, amount, day_of_month, last_month) VALUES(?,?,?,?,?,?,?)",
                          (u["id"], name, rubro, b["method_id"], amount, dom, last)).lastrowid
        recurring.run_due(con)
    return jsonify(id=rid)


@app.delete("/api/recurring/<int:rid>")
@login_required()
def del_recurring(u, rid):
    with db() as con:
        if not con.execute("DELETE FROM recurring WHERE id=? AND user_id=?", (rid, u["id"])).rowcount:
            abort(404, "Ese gasto fijo no existe")
    return jsonify(ok=True)


# ------------------------------------------------------------------ foto del ticket
@app.post("/api/ticket")
@login_required()
def ticket(u):
    if not bot.claude_available():
        abort(400, "Leer tickets necesita la IA activada")
    f = request.files.get("image")
    if not f or not f.filename:
        abort(400, "Sacale una foto al ticket")
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        abort(400, "La imagen tiene que ser JPG, PNG o WEBP")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    path = os.path.join(UPLOAD_DIR, f"ticket-{uuid.uuid4().hex}{ext}")
    f.save(path)
    try:
        from .bot.extract import read_ticket
        out = read_ticket(path)
    finally:
        try:
            os.remove(path)   # el ticket no se guarda: solo se usa para completar el formulario
        except OSError:
            pass
    if not out or (not out.get("merchant") and not out.get("amount")):
        abort(400, "No pudimos leer el ticket. Probá con otra foto, con buena luz y derecha.")
    if out.get("date"):
        try:
            if date.fromisoformat(out["date"]) > date.today():
                out["date"] = None
        except ValueError:
            out["date"] = None
    return jsonify(out)


def create_app(seed_demo=None):
    init_db()
    with db() as con:
        app.secret_key = get_setting(con, "secret_key")
        push.vapid_public_key(con)
        if seed_demo if seed_demo is not None else DEMO:
            from .seed import seed_demo as _seed
            _seed(con)
            if not DEMO_ADMIN:   # online, nadie entra como admin con la contraseña de ejemplo
                con.execute("UPDATE users SET pass_hash=? WHERE email='admin@tubolsillo.app'", (generate_password_hash(secrets.token_urlsafe(24)),))
        # administrador inicial desde la configuración del hosting
        email = (os.environ.get("TUBOLSILLO_ADMIN_EMAIL") or "").strip().lower()
        pw = os.environ.get("TUBOLSILLO_ADMIN_PASSWORD") or ""
        if email and len(pw) >= 8:
            r = con.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
            if r:
                con.execute("UPDATE users SET role='admin' WHERE id=?", (r["id"],))
            else:
                con.execute("INSERT INTO users(email, pass_hash, name, role, onboarded) VALUES(?,?,?,?,1)",
                            (email, generate_password_hash(pw), "Administración", "admin"))
    return app
