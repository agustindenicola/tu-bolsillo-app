"""Datos de ejemplo para probar la app (modo demo). Comercios inventados; promos marcadas como ejemplo."""
import random
from datetime import date, timedelta

from werkzeug.security import generate_password_hash

from . import bot, core
from .bot.verify import upsert_promo

DEMO_PASSWORD = "demo1234"

# comercios inventados, cerca del Obelisco (para probar el aviso por cercanía)
PLACES = [
    ("La Proveeduría", "super", "Av. Corrientes 1200", -34.6040, -58.3830),
    ("Farmacia del Centro", "farmacia", "Sarmiento 1100", -34.6050, -58.3820),
    ("Café Molino", "comida", "Callao 20", -34.6090, -58.3920),
    ("Estación Ruta 9", "nafta", "Av. 9 de Julio 1500", -34.6110, -58.3810),
    ("Parrilla El Fogón", "comida", "Lavalle 900", -34.6020, -58.3790),
    ("Verdulería Doña Rosa", "super", "Uruguay 400", -34.6060, -58.3860),
    ("Pizzería Nápoles", "comida", "Corrientes 1500", -34.6045, -58.3880),
    ("Kiosco La Esquina", "comida", "Talcahuano 300", -34.6055, -58.3850),
]


def _user(con, email, name, role, org_id=None, methods=(), onboarded=1):
    r = con.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if r:
        return r["id"]
    cur = con.execute("INSERT INTO users(email, pass_hash, name, role, org_id, onboarded, accepted_terms) VALUES(?,?,?,?,?,?,datetime('now','localtime'))",
                      (email, generate_password_hash(DEMO_PASSWORD), name, role, org_id, onboarded))
    for m in methods:
        con.execute("INSERT OR IGNORE INTO user_methods(user_id, method_id) VALUES(?,?)", (cur.lastrowid, m))
    return cur.lastrowid


def seed_demo(con):
    if con.execute("SELECT 1 FROM users WHERE email='demo@tubolsillo.app'").fetchone():
        return False
    rnd = random.Random(7)
    # organizaciones
    com = con.execute("INSERT INTO orgs(name, kind) VALUES('La Proveeduría (ejemplo)', 'comercio')").lastrowid
    emp = con.execute("INSERT INTO orgs(name, kind, invite_code) VALUES('Empresa Ejemplo SA', 'empresa', 'EMPRESA-DEMO')").lastrowid
    ids = {}
    for name, rubro, addr, lat, lng in PLACES:
        ids[name] = con.execute("INSERT INTO places(name, rubro, address, lat, lng, is_example, org_id) VALUES(?,?,?,?,?,1,?)",
                                (name, rubro, addr, lat, lng, com if name == "La Proveeduría" else None)).lastrowid
    # fuente de ejemplo para el bot, y una corrida inicial
    con.execute("INSERT INTO sources(name, url, kind, enabled, tos_ok, trust, notes) VALUES(?,?,?,?,?,?,?)",
                ("Página de ejemplo", "beneficios_ejemplo.html", "fixture", 1, 1, 0.9,
                 "Página guardada en el proyecto para probar el bot. Las fuentes reales se agregan desde el panel de administración."))
    bot.run_bot(con)
    # en el demo, el admin ya revisó lo que encontró el bot
    con.execute("UPDATE promos SET status='publicada' WHERE source='bot' AND is_example=1")
    # promos que no vienen del bot: descuentos por efectivo, una exclusiva de empresa y una que cargó el comercio
    extra = [
        ({"place_id": ids["Kiosco La Esquina"], "method_id": "efectivo", "pct": 5, "days": list(range(7)), "conditions": "Descuento del comercio por pagar en efectivo."}, "comercio"),
        ({"place_id": ids["Verdulería Doña Rosa"], "method_id": "efectivo", "pct": 10, "days": list(range(7)), "conditions": "10% pagando en efectivo."}, "comercio"),
        ({"place_id": ids["Pizzería Nápoles"], "method_id": "efectivo", "pct": 10, "days": [3, 4], "conditions": "Jueves y viernes, en efectivo."}, "comercio"),
        ({"place_id": ids["La Proveeduría"], "method_id": "mercadopago", "pct": 15, "days": [3], "cap_month": 3000, "conditions": "Jueves con el QR de la billetera."}, "comercio"),
        ({"place_id": ids["Farmacia del Centro"], "method_id": "uala", "pct": 25, "days": list(range(7)), "cap_month": 2000,
          "conditions": "Exclusivo para empleados de Empresa Ejemplo SA.", "org_id": emp}, "admin"),
    ]
    for p, src in extra:
        p.setdefault("confidence", 0.95)
        upsert_promo(con, p, src, trust=1.0, is_example=True, force_status="publicada")
    # una promo que subió un usuario y espera revisión (para ver la cola del admin)
    upsert_promo(con, {"merchant": "Panadería La Espiga", "rubro": "comida", "method_id": "naranjax", "pct": 20, "days": [0, 1, 2, 3, 4],
                       "cap_month": 1000, "conditions": "Lunes a viernes con QR (foto de un cartel).", "confidence": 0.6},
                 "usuario", trust=0.5, is_example=True, force_status="revision")

    # usuarios demo
    demo = _user(con, "demo@tubolsillo.app", "Agustín", "user", emp, ["mercadopago", "modo", "uala", "galicia", "cuentadni"])
    _user(con, "comercio@tubolsillo.app", "La Proveeduría", "comercio", com)
    _user(con, "empresa@tubolsillo.app", "RR.HH. Empresa Ejemplo", "empresa", emp)
    _user(con, "admin@tubolsillo.app", "Administración", "admin")
    con.execute("INSERT INTO goals(user_id, name, target) VALUES(?,?,?)", (demo, "Vacaciones", 300000))
    con.execute("INSERT INTO lessons_done(user_id, lesson_id) VALUES(?, 'inflacion')", (demo,))

    # historial de 90 días con hábitos claros: súper los jueves, café martes/miércoles, nafta domingos, kiosco en efectivo
    today = date.today()
    place = lambda n: dict(con.execute("SELECT * FROM places WHERE id=?", (ids[n],)).fetchone())  # noqa: E731
    for back in range(90, 0, -1):
        d = today - timedelta(days=back)
        wd = d.weekday()
        if wd == 3:
            core.record_gasto(con, demo, place("La Proveeduría"), "modo", rnd.randrange(18000, 36000, 500), d)
        if wd in (1, 2) and rnd.random() < 0.7:
            core.record_gasto(con, demo, place("Café Molino"), rnd.choice(["uala", "uala", "efectivo"]), rnd.randrange(3000, 6000, 100), d)
        if wd == 6 and rnd.random() < 0.6:
            core.record_gasto(con, demo, place("Estación Ruta 9"), rnd.choice(["cuentadni", "galicia"]), rnd.randrange(20000, 40000, 1000), d)
        if rnd.random() < 0.25:
            core.record_gasto(con, demo, place("Kiosco La Esquina"), "efectivo", rnd.randrange(1500, 4000, 100), d)
        if wd == 4 and rnd.random() < 0.5:
            core.record_gasto(con, demo, place("Pizzería Nápoles"), rnd.choice(["efectivo", "mercadopago"]), rnd.randrange(9000, 18000, 500), d)
        if rnd.random() < 0.08:
            core.record_gasto(con, demo, place("Farmacia del Centro"), "mercadopago", rnd.randrange(5000, 15000, 500), d)
    # movimiento de ejemplo en las promos del comercio (vistas y guardadas), para su panel
    for r in con.execute("SELECT id FROM promos WHERE place_id=?", (ids["La Proveeduría"],)).fetchall():
        for kind, n in (("view", rnd.randint(600, 1300)), ("save", rnd.randint(120, 320))):
            con.executemany("INSERT INTO promo_events(promo_id, kind, created_at) VALUES(?,?,datetime('now','localtime',?))",
                            [(r["id"], kind, f"-{rnd.randint(0, 29)} days") for _ in range(n)])
    con.execute("INSERT INTO notifications(user_id, title, body, url, kind) VALUES(?,?,?,?,?)",
                (demo, "Bienvenido a Tu Bolsillo", "Esta es una cuenta de prueba con datos de ejemplo. Probá cargar un gasto o abrir una lección.", "#inicio", "welcome"))

    # compañeros de trabajo (para el panel de empresa, que solo muestra totales con 5 personas o más)
    for i in range(6):
        u = _user(con, f"empleado{i + 1}@tubolsillo.app", f"Empleado {i + 1}", "user", emp, ["mercadopago", rnd.choice(["modo", "uala", "galicia"])])
        for back in range(1, 40, rnd.choice([3, 4, 5])):
            d = today - timedelta(days=back)
            core.record_gasto(con, u, place(rnd.choice(list(ids))), rnd.choice(["mercadopago", "efectivo"]), rnd.randrange(3000, 25000, 500), d)
        if i % 2 == 0:
            con.execute("INSERT OR IGNORE INTO lessons_done(user_id, lesson_id) VALUES(?, 'inflacion')", (u,))
    con.execute("INSERT INTO recurring(user_id, place_name, rubro, method_id, amount, day_of_month, last_month) VALUES(?,?,?,?,?,?,?)",
                (demo, "Internet y celular", "servicios", "mercadopago", 32000, 10, date.today().isoformat()[:7]))
    # actividad de ejemplo y comentarios, para que el panel de administración tenga números
    for u_id in [demo] + [r["id"] for r in con.execute("SELECT id FROM users WHERE email LIKE 'empleado%'")]:
        for back in range(0, 60, rnd.choice([1, 2, 3, 6])):
            con.execute("INSERT OR IGNORE INTO activity(user_id, day) VALUES(?,?)", (u_id, (today - timedelta(days=back)).isoformat()))
    con.executemany("INSERT INTO app_feedback(user_id, kind, text, screen) VALUES(?,?,?,?)", [
        (demo, "idea", "Estaría bueno poder cargar el gasto sacándole una foto al ticket.", "pagar"),
        (demo, "problema", "En la farmacia no me aplicaron el 20% con Mercado Pago, decía que era solo con débito.", "promos")])
    return True
