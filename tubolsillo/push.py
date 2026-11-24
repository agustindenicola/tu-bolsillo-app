"""Notificaciones: se guardan en la app (centro de avisos) y, si la persona aceptó, llegan al celular (Web Push)."""
import base64
import json
import logging
import os

from .db import DATA_DIR, get_setting, set_setting

log = logging.getLogger(__name__)
VAPID_PEM = os.path.join(DATA_DIR, "vapid_private.pem")


def vapid_public_key(con):
    """Clave pública que el navegador necesita para suscribirse. Se crea una sola vez."""
    pub = get_setting(con, "vapid_public")
    if pub and os.path.exists(VAPID_PEM):
        return pub
    from cryptography.hazmat.primitives import serialization
    from py_vapid import Vapid
    v = Vapid()
    v.generate_keys()
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(VAPID_PEM, "wb") as f:
        f.write(v.private_pem())
    raw = v.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    pub = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    set_setting(con, "vapid_public", pub)
    return pub


def send_push(con, sub, payload):
    from pywebpush import WebPushException, webpush
    try:
        webpush(subscription_info={"endpoint": sub["endpoint"], "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]}},
                data=json.dumps(payload, ensure_ascii=False), vapid_private_key=VAPID_PEM,
                vapid_claims={"sub": "mailto:" + get_setting(con, "contact_email", "contacto@tubolsillo.app")}, timeout=10)
        return True
    except WebPushException as e:
        code = getattr(e.response, "status_code", None)
        if code in (404, 410):   # la suscripción ya no existe (desinstaló o revocó el permiso)
            con.execute("DELETE FROM push_subs WHERE id=?", (sub["id"],))
        else:
            log.warning("Push falló (%s): %s", code, e)
        return False
    except Exception as e:  # noqa: BLE001
        log.warning("Push falló: %s", e)
        return False


def notify(con, uid, title, body, url="#inicio", kind=None, push=True):
    """Guarda el aviso y lo manda al celular. Devuelve cuántos dispositivos lo recibieron."""
    con.execute("INSERT INTO notifications(user_id, title, body, url, kind) VALUES(?,?,?,?,?)", (uid, title, body, url, kind))
    if not push or not os.path.exists(VAPID_PEM):
        return 0
    sent = 0
    for sub in con.execute("SELECT * FROM push_subs WHERE user_id=?", (uid,)).fetchall():
        sent += send_push(con, sub, {"title": title, "body": body, "url": url, "tag": kind or "tubolsillo"})
    return sent
