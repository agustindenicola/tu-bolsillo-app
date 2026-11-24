"""Traer el texto de una fuente de promos, respetando lo que cada sitio permite (robots.txt)."""
import logging
import os
import re
import urllib.robotparser
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)
UA = "TuBolsilloBot/0.1 (+https://tubolsillo.app/bot)"
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


class FetchError(Exception):
    pass


def allowed_by_robots(url):
    parts = urlparse(url)
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(urljoin(f"{parts.scheme}://{parts.netloc}", "/robots.txt"))
    try:
        rp.read()
    except Exception:
        return True   # sin robots.txt accesible: se asume permitido
    return rp.can_fetch(UA, url)


def html_to_text(html):
    """Texto legible, con un bloque por elemento (cada tarjeta o párrafo suele ser una promo)."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "header"]):
        tag.decompose()
    blocks = []
    for el in soup.find_all(["article", "li", "p", "section", "div", "td", "h2", "h3", "h4"]):
        if el.find(["article", "li", "p", "section", "div", "td"]):
            continue   # solo los bloques más chicos, para no duplicar texto
        t = " ".join(el.get_text(" ").split())
        if t:
            blocks.append(t)
    if not blocks:
        blocks = [" ".join(soup.get_text(" ").split())]
    return "\n\n".join(blocks)


PCT = re.compile(r"\d{1,2}(?:[.,]\d)?\s?%")


def _card_text(el):
    """Texto de un bloque, sin repetir frases (muchas páginas duplican el título para celular y compu)."""
    seen, parts = set(), []
    for s in el.stripped_strings:
        s = " ".join(s.split())
        if len(s) >= 4 and s in seen:
            continue
        seen.add(s)
        parts.append(s)
    return " ".join(parts)


DAY_LETTERS = {"D": "domingo", "L": "lunes", "M": None, "X": "miércoles", "J": "jueves", "V": "viernes", "S": "sábado"}
WEEK_FROM_SUNDAY = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"]
WEEK_FROM_MONDAY = WEEK_FROM_SUNDAY[1:] + WEEK_FROM_SUNDAY[:1]


def _active_days(soup):
    """Calendarios de 7 letras (D L M M J V S) donde los días de la promo están resaltados: se pasan a texto."""
    # por identidad: dos calendarios iguales son elementos distintos (un set los juntaría en uno)
    parents = {id(s.parent.parent): s.parent.parent for s in soup.find_all(string=lambda s: s and s.strip() in DAY_LETTERS) if s.parent.parent}
    for parent in parents.values():
        kids = [k for k in parent.find_all(recursive=False) if k.get_text(strip=True)]
        letters = [k.get_text(strip=True) for k in kids]
        if len(kids) != 7 or not all(x in DAY_LETTERS for x in letters):
            continue
        week = WEEK_FROM_SUNDAY if letters[0] == "D" else WEEK_FROM_MONDAY
        active = [week[i] for i, k in enumerate(kids) if any(c in ("active", "activo", "selected", "on") for c in (k.get("class") or []))]
        for k in kids:
            k.decompose()
        parent.append(" Días: " + (", ".join(active) if active else "todos los días") + " ")


def html_to_cards(html):
    """Una línea por tarjeta de promo: el bloque más grande alrededor de cada porcentaje que no incluye otra promo."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "header"]):
        tag.decompose()
    for tag in soup.select("[hidden], .d-none"):   # lo que la página no muestra
        tag.decompose()
    _active_days(soup)
    cards, seen = [], set()
    for node in soup.find_all(string=lambda s: s and "%" in s):
        el = node.parent
        txt = _card_text(el)
        for _ in range(3):                      # el número y el % a veces están en elementos separados
            if PCT.search(txt) or el.parent is None:
                break
            el = el.parent
            txt = _card_text(el)
        n = len(PCT.findall(txt))
        if not n:
            continue
        while el.parent is not None and el.parent.name not in ("body", "html", "[document]"):
            ptxt = _card_text(el.parent)
            if len(ptxt) > 500 or len(PCT.findall(ptxt)) != n:
                break
            el, txt = el.parent, ptxt
        if id(el) not in seen:
            seen.add(id(el))
            cards.append(txt)
    out = []
    for c in cards:
        if c not in out and not any(c != o and c in o for o in cards):
            out.append(c)
    return out


def page_text(html):
    """Si la página tiene tarjetas de promos, devuelve una por bloque; si no, el texto común."""
    cards = html_to_cards(html)
    return "\n\n".join(cards) if len(cards) >= 3 else html_to_text(html)


def render_with_browser(url):
    """Para páginas que arman las promos con JavaScript: las abre en un navegador invisible y devuelve el HTML ya armado.

    El bot se presenta con su propio nombre (no se hace pasar por una persona) y solo entra donde robots.txt lo permite.
    Usa Playwright con el navegador que haya: Edge o Chrome instalados, o el Chromium de Playwright.
    """
    try:
        from playwright.sync_api import Error as PWError, sync_playwright
    except ImportError as e:
        raise FetchError("Falta el navegador para esta fuente: instalá «pip install playwright» y «playwright install chromium»") from e
    with sync_playwright() as p:
        browser = None
        for channel in (os.environ.get("TUBOLSILLO_BROWSER"), "msedge", "chrome", None):
            try:
                browser = p.chromium.launch(channel=channel) if channel else p.chromium.launch()
                break
            except PWError:
                continue
        if browser is None:
            raise FetchError("No encontré un navegador: instalá «playwright install chromium»")
        try:
            page = browser.new_page(user_agent=UA, locale="es-AR", viewport={"width": 1280, "height": 2000})
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(5000)
            for _ in range(4):   # bajar para que carguen las promos de más abajo
                page.mouse.wheel(0, 3000)
                page.wait_for_timeout(1000)
            return page.content()
        except PWError as e:
            raise FetchError(f"No se pudo abrir la página en el navegador: {str(e).splitlines()[0]}") from e
        finally:
            browser.close()


def fetch_source(src):
    """Devuelve el texto de la fuente. Las fuentes 'fixture' son páginas de ejemplo guardadas en el proyecto."""
    if src["kind"] == "fixture":
        path = os.path.join(FIXTURES, os.path.basename(src["url"]))
        if not os.path.exists(path):
            raise FetchError(f"No existe la página de ejemplo {src['url']}")
        with open(path, encoding="utf-8") as f:
            return page_text(f.read())
    if not src["tos_ok"]:
        raise FetchError("Fuente sin revisar: falta confirmar que sus términos permiten leerla automáticamente")
    if not allowed_by_robots(src["url"]):
        raise FetchError("El sitio no permite lectura automática (robots.txt)")
    if src["kind"] == "navegador":
        return page_text(render_with_browser(src["url"]))
    try:
        r = requests.get(src["url"], headers={"User-Agent": UA, "Accept-Language": "es-AR,es"}, timeout=40)
        r.raise_for_status()
    except requests.RequestException as e:
        raise FetchError(f"No se pudo leer la página: {e}") from e
    return page_text(r.text)
