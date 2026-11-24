"""Base de datos SQLite: esquema, conexión y configuración guardada."""
import os
import secrets
import sqlite3
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("TUBOLSILLO_DATA") or os.path.join(BASE_DIR, "datos")
DB_PATH = os.path.join(DATA_DIR, "tubolsillo.db")
UPLOAD_DIR = os.path.join(DATA_DIR, "subidas")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  pass_hash TEXT NOT NULL,
  name TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'user',          -- user | comercio | empresa | admin
  org_id INTEGER REFERENCES orgs(id),         -- empresa a la que pertenece (beneficio) o comercio que administra
  personal INTEGER NOT NULL DEFAULT 1,        -- personalizar con sus gastos
  notify_hour INTEGER NOT NULL DEFAULT 20,    -- hora del aviso diario
  onboarded INTEGER NOT NULL DEFAULT 0,
  last_digest TEXT,                           -- fecha del último aviso diario enviado
  created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS orgs (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  kind TEXT NOT NULL,                         -- empresa | comercio
  invite_code TEXT UNIQUE,
  created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS user_methods (
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  method_id TEXT NOT NULL,
  PRIMARY KEY (user_id, method_id)
);
CREATE TABLE IF NOT EXISTS places (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  rubro TEXT NOT NULL DEFAULT 'otros',
  address TEXT,
  lat REAL, lng REAL,
  org_id INTEGER REFERENCES orgs(id),         -- comercio que lo administra
  is_example INTEGER NOT NULL DEFAULT 0,
  created_by INTEGER REFERENCES users(id),
  created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS places_name ON places(name);
CREATE TABLE IF NOT EXISTS sources (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  url TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'html',          -- html | fixture
  enabled INTEGER NOT NULL DEFAULT 0,
  tos_ok INTEGER NOT NULL DEFAULT 0,          -- alguien revisó que sus términos permiten leerla automáticamente
  trust REAL NOT NULL DEFAULT 0.6,            -- confianza en la fuente (aprende con las confirmaciones)
  ok_count INTEGER NOT NULL DEFAULT 0,
  fail_count INTEGER NOT NULL DEFAULT 0,
  last_run TEXT, last_status TEXT,
  notes TEXT
);
CREATE TABLE IF NOT EXISTS promos (
  id INTEGER PRIMARY KEY,
  place_id INTEGER REFERENCES places(id),     -- un comercio puntual, o NULL
  merchant TEXT,                              -- cadena o comercio por nombre (si no hay place_id)
  rubro TEXT,                                 -- si no hay comercio: vale para todo el rubro
  method_id TEXT NOT NULL,
  pct REAL NOT NULL,
  days TEXT NOT NULL DEFAULT '0123456',       -- días de la semana (0 = lunes)
  cap_month REAL,                             -- tope de reintegro por mes y por persona
  min_amount REAL,
  conditions TEXT,
  valid_from TEXT, valid_to TEXT,
  org_id INTEGER REFERENCES orgs(id),         -- promo exclusiva para empleados de una empresa
  source TEXT NOT NULL,                       -- bot | comercio | admin | usuario | ejemplo
  source_id INTEGER REFERENCES sources(id),
  source_url TEXT,
  confidence REAL NOT NULL DEFAULT 0.5,
  status TEXT NOT NULL DEFAULT 'revision',    -- publicada | revision | rechazada | vencida
  is_example INTEGER NOT NULL DEFAULT 0,
  ok_count INTEGER NOT NULL DEFAULT 0,
  fail_count INTEGER NOT NULL DEFAULT 0,
  fingerprint TEXT UNIQUE,
  raw_text TEXT,
  created_by INTEGER REFERENCES users(id),
  created_at TEXT DEFAULT (datetime('now','localtime')),
  last_seen TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS promos_status ON promos(status);
CREATE TABLE IF NOT EXISTS gastos (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  place_id INTEGER REFERENCES places(id),
  place_name TEXT NOT NULL,
  rubro TEXT NOT NULL DEFAULT 'otros',
  method_id TEXT NOT NULL,
  amount REAL NOT NULL,
  saved REAL NOT NULL DEFAULT 0,              -- lo que ahorró con la promo usada
  missed REAL NOT NULL DEFAULT 0,             -- lo que hubiera ahorrado pagando con el mejor medio
  promo_id INTEGER REFERENCES promos(id),
  day TEXT NOT NULL,                          -- fecha del gasto (YYYY-MM-DD)
  created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS gastos_user_day ON gastos(user_id, day);
CREATE TABLE IF NOT EXISTS feedback (
  id INTEGER PRIMARY KEY,
  user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  promo_id INTEGER NOT NULL REFERENCES promos(id) ON DELETE CASCADE,
  ok INTEGER NOT NULL,
  created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS saves (
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  promo_id INTEGER NOT NULL REFERENCES promos(id) ON DELETE CASCADE,
  PRIMARY KEY (user_id, promo_id)
);
CREATE TABLE IF NOT EXISTS promo_events (
  id INTEGER PRIMARY KEY,
  promo_id INTEGER NOT NULL REFERENCES promos(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,                         -- view | save | use
  created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS goals (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  target REAL NOT NULL,
  created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS lessons_done (
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  lesson_id TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now','localtime')),
  PRIMARY KEY (user_id, lesson_id)
);
CREATE TABLE IF NOT EXISTS notifications (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  url TEXT,
  kind TEXT,
  read INTEGER NOT NULL DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS push_subs (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  endpoint TEXT UNIQUE NOT NULL,
  p256dh TEXT NOT NULL,
  auth TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS bot_runs (
  id INTEGER PRIMARY KEY,
  started TEXT, finished TEXT,
  found INTEGER DEFAULT 0, new INTEGER DEFAULT 0, published INTEGER DEFAULT 0, queued INTEGER DEFAULT 0,
  errors TEXT, extractor TEXT
);
CREATE TABLE IF NOT EXISTS activity (            -- un registro por persona y por día que usa la app (para medir uso)
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  day TEXT NOT NULL,
  PRIMARY KEY (user_id, day)
);
CREATE TABLE IF NOT EXISTS app_feedback (        -- «Contanos qué mejorar»
  id INTEGER PRIMARY KEY,
  user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  kind TEXT NOT NULL DEFAULT 'idea',            -- idea | problema | otro
  text TEXT NOT NULL,
  screen TEXT,
  status TEXT NOT NULL DEFAULT 'nuevo',         -- nuevo | visto
  created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS password_resets (
  token_hash TEXT PRIMARY KEY,                  -- se guarda solo el hash del token
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at TEXT NOT NULL,
  used INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS recurring (           -- gastos fijos que se cargan solos cada mes
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  place_name TEXT NOT NULL,
  rubro TEXT NOT NULL DEFAULT 'servicios',
  method_id TEXT NOT NULL,
  amount REAL NOT NULL,
  day_of_month INTEGER NOT NULL,
  last_month TEXT,                              -- último mes en que se cargó (YYYY-MM)
  created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT
);
"""

DEFAULT_SETTINGS = {
    "ref_tna_plazo_fijo": "30",       # tasa de referencia para la calculadora (la actualiza un admin)
    "ref_tna_remunerada": "25",
    "ref_tna_fecha": "",
    "contact_email": "contacto@tubolsillo.app",
    "publish_threshold": "0.75",      # confianza mínima para que el bot publique solo
    "bot_every_hours": "6",
}


def connect():
    os.makedirs(DATA_DIR, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=20)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA journal_mode=WAL")
    return con


@contextmanager
def db():
    con = connect()
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


# columnas agregadas después de la primera versión (se suman solas a bases existentes)
MIGRATIONS = [
    ("users", "accepted_terms", "TEXT"),   # cuándo aceptó términos y privacidad
    ("users", "last_seen", "TEXT"),
    ("sources", "method_id", "TEXT"),     # medio de pago de la página (las promos de un banco no siempre lo repiten)
]


def init_db():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    with db() as con:
        con.executescript(SCHEMA)
        for table, col, typ in MIGRATIONS:
            if col not in {r[1] for r in con.execute(f"PRAGMA table_info({table})")}:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
        for k, v in DEFAULT_SETTINGS.items():
            con.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k, v))
        # clave para firmar las sesiones: se crea una sola vez
        con.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('secret_key',?)", (secrets.token_hex(32),))


def get_setting(con, key, default=None):
    r = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r["value"] if r and r["value"] is not None else default


def set_setting(con, key, value):
    con.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
