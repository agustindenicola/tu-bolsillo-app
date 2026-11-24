"""Envío de mails (recuperar contraseña). Se configura con variables de entorno:

    TUBOLSILLO_SMTP_HOST, TUBOLSILLO_SMTP_PORT (587), TUBOLSILLO_SMTP_USER,
    TUBOLSILLO_SMTP_PASSWORD, TUBOLSILLO_SMTP_FROM (opcional)

Con Gmail: host smtp.gmail.com, puerto 587, usuario = tu mail y una «contraseña de aplicación».
Si no está configurado, no se manda nada y el administrador puede generar el link a mano.
"""
import logging
import os
import smtplib
from email.message import EmailMessage

log = logging.getLogger(__name__)


def configured():
    return bool(os.environ.get("TUBOLSILLO_SMTP_HOST") and os.environ.get("TUBOLSILLO_SMTP_USER"))


def send(to, subject, text):
    if not configured():
        return False
    msg = EmailMessage()
    msg["From"] = os.environ.get("TUBOLSILLO_SMTP_FROM") or f"Tu Bolsillo <{os.environ['TUBOLSILLO_SMTP_USER']}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    try:
        with smtplib.SMTP(os.environ["TUBOLSILLO_SMTP_HOST"], int(os.environ.get("TUBOLSILLO_SMTP_PORT", "587")), timeout=20) as s:
            s.starttls()
            s.login(os.environ["TUBOLSILLO_SMTP_USER"], os.environ.get("TUBOLSILLO_SMTP_PASSWORD", ""))
            s.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError) as e:
        log.warning("No se pudo mandar el mail a %s: %s", to, e)
        return False
