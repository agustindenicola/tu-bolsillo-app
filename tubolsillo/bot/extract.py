"""Entender promos escritas de cualquier manera y pasarlas a un formato fijo.

Dos extractores:
- reglas: siempre disponible, sin costo; reconoce porcentaje, días, tope, medio de pago y rubro.
- Claude: si hay credenciales de la API de Anthropic, entiende textos difíciles y fotos de carteles.
Los dos devuelven la misma lista de dicts con un nivel de confianza (0 a 1).
"""
import base64
import json
import logging
import os
import re

from ..catalog import METHOD_BY_ID, METHODS, RUBROS
from ..core import norm

log = logging.getLogger(__name__)

DAY_WORDS = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6}
METHOD_IDS = [m["id"] for m in METHODS]
RUBRO_IDS = [r["id"] for r in RUBROS]
MODEL = os.environ.get("TUBOLSILLO_MODEL", "claude-opus-5-5")


# ------------------------------------------------------------------ reglas
def _days(t):
    if re.search(r"todos los dias|todos los días|de lunes a domingo|todas las semanas", t):
        return [0, 1, 2, 3, 4, 5, 6]
    if re.search(r"fines? de semana", t):
        return [5, 6]
    m = re.search(r"(?:de )?\b(lunes|martes|miercoles|jueves|viernes|sabado|domingo)s? a (lunes|martes|miercoles|jueves|viernes|sabado|domingo)s?\b", t)
    if m:
        a, b = DAY_WORDS[m.group(1)], DAY_WORDS[m.group(2)]
        return list(range(a, b + 1)) if a <= b else list(range(a, 7)) + list(range(0, b + 1))
    found = sorted({v for k, v in DAY_WORDS.items() if re.search(rf"\b{k}s?\b", t)})
    return found


def _money(s):
    s = s.replace(".", "").replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _method(t):
    hits = []
    for m in METHODS:
        for a in m["aliases"]:
            a2 = norm(a)
            if len(a2) <= 3:          # alias cortos (ej. "mp"): solo como palabra suelta
                if re.search(rf"\b{re.escape(a2)}\b", t):
                    hits.append((len(a2), m["id"]))
            elif a2 in t:
                hits.append((len(a2), m["id"]))
    if not hits:
        return None
    return max(hits)[1]


def _rubro(t):
    best = None
    for r in RUBROS:
        for w in r["words"]:
            if re.search(rf"\b{re.escape(norm(w))}(?:s|es)?\b", t):
                return r["id"]
    return best


def split_chunks(text):
    """Corta el texto de una página en pedazos que probablemente sean una promo cada uno."""
    parts = re.split(r"\n\s*\n|\s*[•|]\s*", text)
    out = []
    for p in parts:
        p = " ".join(p.split())
        if len(p) > 600:   # bloque muy largo: recién ahí se corta por oraciones
            out += [s for s in re.split(r"(?<=[.!])\s+(?=[A-ZÁÉÍÓÚÑ0-9])", p) if 8 <= len(s) <= 600 and re.search(r"\d{1,2}\s?%", s)]
        elif len(p) >= 8 and re.search(r"\d{1,2}\s?%", p):
            out.append(p)
    return out


NAME = r"[A-ZÁÉÍÓÚÑ0-9][\w'’&.\-áéíóúñÁÉÍÓÚÑ]*(?:\s+(?:de|del|la|el|y|los|las|&)?\s*[A-ZÁÉÍÓÚÑ0-9][\w'’&.\-áéíóúñÁÉÍÓÚÑ]*){0,4}"
STOP = {"tope", "todos", "todas", "ir", "con", "hasta", "vigente", "conoce", "conocer", "ver", "pagando", "valido", "exclusivo",
        "comprando", "plan", "metodos", "cft", "promo", "sin", "lunes", "martes", "miercoles", "jueves", "viernes",
        "sabado", "sabados", "domingo", "domingos", "reintegro", "descuento", "ahorro", "off", "tarjeta", "tarjetas", "nivel",
        "carga", "paga", "compra", "disfruta", "aprovecha", "usa", "viaja", "comprando", "abonando",
        "te", "en", "nuevo", "nueva", "dias", "desde", "exclusiva"}
LEADING = {"nuevo", "nueva", "sin", "tope", "exclusivo", "exclusiva", "promo", "beneficios", "beneficio"}
# cadenas conocidas: el rubro sale del nombre aunque la promo no lo diga
CHAIN_RUBRO = {
    "super": ["coto", "dia", "supermercado dia", "vea", "disco", "jumbo", "carrefour", "changomas", "chango mas", "masgo", "la anonima",
              "diarco", "makro", "vital", "maxiconsumo", "cooperativa obrera", "supercoop", "toledo", "josimar", "nini", "libertad", "la reina"],
    "farmacia": ["farmacity", "farmalife", "openfarma", "farmaonline", "simplicity", "get the look", "dr ahorro", "farmacias del puente"],
    "nafta": ["ypf", "app ypf", "axion", "axion energy", "shell", "puma", "gulf"],
    "comida": ["burger king", "mcdonalds", "mostaza", "freddo", "grido", "starbucks", "havanna", "le pain quotidien", "lpq", "rapanui",
               "lucciano", "luccianos", "chungo", "the food market", "pedidosya", "rappi", "la cabrera", "cerini"],
    "transporte": ["cabify", "uber", "didi", "taxi premium", "sube", "aerolineas", "aerolineas arg", "jetsmart", "flybondi"],
    "ropa": ["adidas", "nike", "dexter", "moov", "stock center", "showsport", "grimoldi", "rosen", "on city", "arredo", "cannon"],
    "hogar": ["fravega", "garbarino", "musimundo", "on city", "samsung", "hendel", "easy", "sodimac", "casa silvia"],
    "entretenimiento": ["cinemark", "hoyts", "showcase", "cine express", "tienda nova"],
}
CHAIN_BY_NAME = {norm(n): r for r, names in CHAIN_RUBRO.items() for n in names}


def _chain_rubro(merchant):
    n = norm(merchant).replace("'", "").replace("’", "")
    return CHAIN_BY_NAME.get(n) or next((r for k, r in CHAIN_BY_NAME.items() if len(k) >= 4 and n.startswith(k + " ")), None)
METHOD_WORDS = {norm(a) for m in METHODS for a in m["aliases"] + [m["name"]]}
RUBRO_WORDS = {norm(w) for r in RUBROS for w in r["words"] + [r["generic"], r["name"]]}


def _clean_name(name):
    out = []
    words = name.split()
    while words and norm(words[0]).strip(".:") in LEADING:   # «Nuevo», «Sin tope»: etiquetas, no el nombre
        words = words[1:]
    for w in words:
        if norm(w).strip(".:") in STOP:
            break
        out.append(w)
    name = " ".join(out).strip(" .:-")
    n = norm(name)
    if all(len(w) == 1 for w in n.split()):   # «D L M M J»: letras de un calendario
        return None
    if n in {"la", "el", "los", "las", "the", "ver"} or len(n) < 2 or n in METHOD_WORDS or n in RUBRO_WORDS or n in DAY_WORDS or n.isdigit():
        return None
    return name


MERCHANT_PATTERNS = [
    re.compile(rf"·\s*({NAME})\s*(?:·|,)"),                                                       # MODO: «· Tienda Nova ·»
    re.compile(rf"\d\s?%\s*(?:de\s+)?(?i:reintegro|descuento|ahorro|off)?\s*en\s+({NAME})"),       # 20% de reintegro en Coto
    re.compile(rf"\ben ({NAME})"),                                                                # ... en Farmacia X
    re.compile(rf"\d\s?%\s*(?:de\s+)?(?i:reintegro|descuento|ahorro)\s+({NAME})"),                # 30% de reintegro Burger King
    re.compile(rf"^({NAME})\s+(?:hasta\s+)?\d{{1,2}}\s?%"),                                       # Farmalife 10%
    re.compile(rf"({NAME})\s+(?:hasta\s+)?\d{{1,2}}\s?%"),                                        # Sin tope Ruiz y Roca 15%
    re.compile(rf"\d\s?%\s+({NAME})\s*:"),                                                         # 25% JetSMART :
]


def _merchant(chunk):
    """El comercio, según cómo lo escriben las páginas más comunes."""
    for pat in MERCHANT_PATTERNS:
        for m in pat.finditer(chunk):
            name = _clean_name(m.group(1))
            if name and name[0].isupper():
                return name
    return None


def extract_rules(text, default_method=None):
    """default_method: el medio de la fuente (en la página de un banco, las promos son de ese banco aunque no lo repitan)."""
    promos = []
    for chunk in split_chunks(text):
        t = norm(chunk)
        m = re.search(r"(\d{1,2}(?:[.,]\d)?)\s?%", t)
        if not m:
            continue
        if len(re.findall(r"\d{1,2}(?:[.,]\d)?\s?%", t)) >= 3 and len(t) > 120:
            continue   # varias promos pegadas en un bloque: mejor no mezclar sus datos
        pct = float(m.group(1).replace(",", "."))
        if not 1 <= pct <= 80:
            continue
        # «pagando con MODO desde ICBC» en la página de ICBC: es de ICBC
        own = default_method and any(re.search(rf"\b{re.escape(norm(a))}\b", t) for a in METHOD_BY_ID[default_method]["aliases"])
        method = default_method if own else (_method(t) or default_method)
        if not method:
            continue
        days = _days(t) or [0, 1, 2, 3, 4, 5, 6]
        cap = None
        mc = re.search(r"tope(?: de reintegro| de devolucion| de descuento)?(?: mensual| por mes)?(?: de)?\s*:?\s*\$\s?([\d\.\s,]+)", t)
        if mc:
            cap = _money(mc.group(1))
        mn = re.search(r"(?:compra|consumo) minim[oa](?: de)?\s*\$\s?([\d\.\s,]+)", t)
        min_amount = _money(mn.group(1)) if mn else None
        rubro = _rubro(t)
        merchant = _merchant(chunk)
        if merchant and _chain_rubro(merchant):
            rubro = _chain_rubro(merchant)
        vt = None
        mv = re.search(r"hasta el (\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?", t)
        mi = re.search(r"hasta (?:el )?(\d{4})-(\d{2})-(\d{2})", chunk)
        if mi:
            vt = f"{mi.group(1)}-{mi.group(2)}-{mi.group(3)}"
        elif mv:
            from datetime import date
            y = int(mv.group(3)) if mv.group(3) else date.today().year
            y = y + 2000 if y < 100 else y
            try:
                vt = date(y, int(mv.group(2)), int(mv.group(1))).isoformat()
            except ValueError:
                vt = None
        # confianza según cuántas piezas se reconocieron con claridad
        conf = 0.45 + 0.1 * bool(_days(t)) + 0.1 * bool(merchant or rubro) + 0.05 * bool(cap)
        promos.append({"merchant": merchant, "rubro": rubro, "method_id": method, "pct": pct, "days": days,
                       "cap_month": cap, "min_amount": min_amount, "conditions": chunk[:300], "valid_to": vt,
                       "confidence": round(min(conf, 0.7), 2), "raw_text": chunk})
    return promos


# ------------------------------------------------------------------ Claude
SCHEMA = {
    "type": "object",
    "properties": {
        "promos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "merchant": {"anyOf": [{"type": "string"}, {"type": "null"}], "description": "Comercio o cadena. null si la promo vale para todo un rubro."},
                    "rubro": {"anyOf": [{"type": "string", "enum": RUBRO_IDS}, {"type": "null"}]},
                    "method_id": {"type": "string", "enum": METHOD_IDS},
                    "pct": {"type": "number", "description": "Porcentaje de descuento o reintegro."},
                    "days": {"type": "array", "items": {"type": "integer", "enum": [0, 1, 2, 3, 4, 5, 6]}, "description": "0 = lunes ... 6 = domingo"},
                    "cap_month": {"anyOf": [{"type": "number"}, {"type": "null"}], "description": "Tope de reintegro por mes y por persona, en pesos."},
                    "min_amount": {"anyOf": [{"type": "number"}, {"type": "null"}]},
                    "conditions": {"type": "string", "description": "Condiciones importantes en una frase corta (QR, cuotas, primera compra, etc.)."},
                    "valid_to": {"anyOf": [{"type": "string", "description": "YYYY-MM-DD"}, {"type": "null"}]},
                    "confidence": {"type": "number", "description": "0 a 1: qué tan seguro estás de que todos los datos son correctos."},
                },
                "required": ["merchant", "rubro", "method_id", "pct", "days", "cap_month", "min_amount", "conditions", "valid_to", "confidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["promos"],
    "additionalProperties": False,
}

SYSTEM = (
    "Extraés promociones de descuento vigentes en Argentina a partir de texto de páginas web o fotos de carteles. "
    "Devolvé solo promos con un porcentaje concreto y un medio de pago reconocible de la lista permitida; si el medio no está en la lista, omití la promo. "
    "No inventes datos: si un dato no aparece, usá null. Los días van de 0 (lunes) a 6 (domingo); si dice 'todos los días', usá los siete. "
    "El tope es por mes y por persona. La confianza debe ser baja si el texto es ambiguo o le faltan datos."
)


def claude_available():
    if os.environ.get("TUBOLSILLO_NO_AI"):
        return False
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_PROFILE"))


def _call_claude(content):
    import anthropic
    client = anthropic.Anthropic()
    resp = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        system=SYSTEM,
        messages=[{"role": "user", "content": content}],
    )
    if resp.stop_reason == "refusal":
        log.warning("Claude no procesó el contenido (refusal)")
        return []
    if resp.stop_reason == "max_tokens":
        log.warning("Respuesta cortada por max_tokens; se descarta")
        return []
    text = next((b.text for b in resp.content if b.type == "text"), "")
    data = json.loads(text)
    out = []
    for p in data.get("promos", []):
        if not (1 <= float(p["pct"]) <= 90) or p["method_id"] not in METHOD_IDS:
            continue
        p["days"] = sorted(set(p["days"])) or [0, 1, 2, 3, 4, 5, 6]
        p["confidence"] = max(0.0, min(1.0, float(p["confidence"])))
        p["raw_text"] = p.get("conditions")
        out.append(p)
    return out


def extract_claude_text(text, source_hint="", default_method=None):
    """Manda el texto completo, en partes si es muy largo (nunca se recorta sin avisar)."""
    import anthropic
    pieces, size = [], 60000
    for i in range(0, len(text), size):
        pieces.append(text[i:i + size])
    out = []
    for i, piece in enumerate(pieces, 1):
        hint = f"\nSi una promo no nombra el medio de pago, usá «{default_method}»: la página es de ese medio." if default_method else ""
        prompt = (f"Fuente: {source_hint}{hint}\nParte {i} de {len(pieces)}.\n\n<pagina>\n{piece}\n</pagina>\n\n"
                  "Extraé todas las promociones de descuento o reintegro.")
        try:
            out += _call_claude([{"type": "text", "text": prompt}])
        except (anthropic.APIConnectionError, anthropic.RateLimitError, anthropic.APIStatusError, json.JSONDecodeError) as e:
            log.warning("Falló la extracción con Claude (%s); se usan reglas", e)
            return None
    return out


def extract_claude_image(path):
    import anthropic
    ext = os.path.splitext(path)[1].lower()
    media = {".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}.get(ext, "image/jpeg")
    with open(path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode()
    try:
        return _call_claude([{"type": "image", "source": {"type": "base64", "media_type": media, "data": data}},
                             {"type": "text", "text": "Esta es una foto o captura de una promoción. Extraé las promociones que se lean."}])
    except (anthropic.APIConnectionError, anthropic.RateLimitError, anthropic.APIStatusError, json.JSONDecodeError) as e:
        log.warning("Falló la lectura de la imagen con Claude: %s", e)
        return None


def extract(text, source_hint="", default_method=None):
    """Usa Claude si está disponible; si no (o si falla), las reglas."""
    if claude_available():
        res = extract_claude_text(text, source_hint, default_method)
        if res is not None:
            return res, "claude"
    return extract_rules(text, default_method), "reglas"


# ------------------------------------------------------------------ foto de un ticket (para cargar un gasto)
TICKET_SCHEMA = {
    "type": "object",
    "properties": {
        "merchant": {"anyOf": [{"type": "string"}, {"type": "null"}], "description": "Nombre del comercio como figura en el ticket."},
        "amount": {"anyOf": [{"type": "number"}, {"type": "null"}], "description": "Total pagado, en pesos."},
        "date": {"anyOf": [{"type": "string", "description": "YYYY-MM-DD"}, {"type": "null"}]},
        "method_id": {"anyOf": [{"type": "string", "enum": METHOD_IDS}, {"type": "null"}], "description": "Medio de pago si se lee en el ticket."},
        "rubro": {"type": "string", "enum": RUBRO_IDS},
        "confidence": {"type": "number", "description": "0 a 1"},
    },
    "required": ["merchant", "amount", "date", "method_id", "rubro", "confidence"],
    "additionalProperties": False,
}
TICKET_SYSTEM = ("Leés tickets y comprobantes de compra de Argentina. Devolvé el comercio, el total pagado, la fecha y, si aparece, "
                 "el medio de pago (solo de la lista permitida). No inventes: si un dato no se lee, usá null.")


def read_ticket(path):
    """Lee la foto de un ticket con Claude. Devuelve un dict o None si no hay IA o falló."""
    if not claude_available():
        return None
    import anthropic
    ext = os.path.splitext(path)[1].lower()
    media = {".png": "image/png", ".webp": "image/webp"}.get(ext, "image/jpeg")
    with open(path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode()
    try:
        client = anthropic.Anthropic()
        resp = client.beta.messages.create(
            model=MODEL, max_tokens=4000, betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": TICKET_SCHEMA}}, system=TICKET_SYSTEM,
            messages=[{"role": "user", "content": [{"type": "image", "source": {"type": "base64", "media_type": media, "data": data}},
                                                   {"type": "text", "text": "Leé este ticket."}]}])
        if resp.stop_reason in ("refusal", "max_tokens"):
            return None
        out = json.loads(next((b.text for b in resp.content if b.type == "text"), "{}"))
        if out.get("amount") is not None and not (0 < float(out["amount"]) < 1e9):
            out["amount"] = None
        return out
    except (anthropic.APIConnectionError, anthropic.RateLimitError, anthropic.APIStatusError, json.JSONDecodeError, ValueError) as e:
        log.warning("No se pudo leer el ticket: %s", e)
        return None
