"""Datos fijos de la app: medios de pago, rubros, niveles, lecciones y glosario.

Los medios de pago son entidades reales que existen en Argentina. Los nombres se usan
solo para identificar con qué paga cada persona; la app no tiene relación con ellas.
"""

# ------------------------------------------------------------------ medios de pago
# kind: billetera | banco | tarjeta | efectivo
# aliases: palabras con las que aparecen en las promos (las usa el bot para reconocerlas)
METHODS = [
    # billeteras virtuales (hoy, el medio más usado para pagar con QR)
    {"id": "mercadopago", "name": "Mercado Pago", "kind": "billetera", "color": "#009ee3", "aliases": ["mercado pago", "mercadopago", "mp"]},
    {"id": "modo", "name": "MODO", "kind": "billetera", "color": "#1f9d55", "aliases": ["modo", "pagando con modo"]},
    {"id": "uala", "name": "Ualá", "kind": "billetera", "color": "#3e6bf0", "aliases": ["ualá", "uala"]},
    {"id": "naranjax", "name": "Naranja X", "kind": "billetera", "color": "#fe5000", "aliases": ["naranja x", "naranjax"]},
    {"id": "cuentadni", "name": "Cuenta DNI", "kind": "billetera", "color": "#00a650", "aliases": ["cuenta dni", "cuentadni"]},
    {"id": "personalpay", "name": "Personal Pay", "kind": "billetera", "color": "#00b2e2", "aliases": ["personal pay"]},
    {"id": "prex", "name": "Prex", "kind": "billetera", "color": "#5a2ca0", "aliases": ["prex"]},
    {"id": "bnamas", "name": "BNA+", "kind": "billetera", "color": "#1b4f9c", "aliases": ["bna+", "bna mas", "billetera bna"]},
    # bancos (tarjetas de débito y crédito de cada banco)
    {"id": "nacion", "name": "Banco Nación", "kind": "banco", "color": "#1b4f9c", "aliases": ["banco nación", "banco nacion", "banco de la nación"]},
    {"id": "provincia", "name": "Banco Provincia", "kind": "banco", "color": "#00863f", "aliases": ["banco provincia", "bapro"]},
    {"id": "ciudad", "name": "Banco Ciudad", "kind": "banco", "color": "#e30613", "aliases": ["banco ciudad"]},
    {"id": "galicia", "name": "Galicia", "kind": "banco", "color": "#f28c00", "aliases": ["galicia", "banco galicia"]},
    {"id": "santander", "name": "Santander", "kind": "banco", "color": "#ec0000", "aliases": ["santander"]},
    {"id": "bbva", "name": "BBVA", "kind": "banco", "color": "#004481", "aliases": ["bbva", "francés"]},
    {"id": "macro", "name": "Macro", "kind": "banco", "color": "#0b2d71", "aliases": ["banco macro", "macro"]},
    {"id": "icbc", "name": "ICBC", "kind": "banco", "color": "#c4161c", "aliases": ["icbc"]},
    {"id": "credicoop", "name": "Credicoop", "kind": "banco", "color": "#00539f", "aliases": ["credicoop"]},
    {"id": "supervielle", "name": "Supervielle", "kind": "banco", "color": "#d9001b", "aliases": ["supervielle"]},
    {"id": "patagonia", "name": "Banco Patagonia", "kind": "banco", "color": "#0067b1", "aliases": ["patagonia"]},
    {"id": "comafi", "name": "Comafi", "kind": "banco", "color": "#00468c", "aliases": ["comafi"]},
    {"id": "brubank", "name": "Brubank", "kind": "banco", "color": "#5b2be0", "aliases": ["brubank"]},
    # tarjetas que no dependen de un banco
    {"id": "naranja", "name": "Tarjeta Naranja", "kind": "tarjeta", "color": "#fe5000", "aliases": ["tarjeta naranja"]},
    {"id": "amex", "name": "American Express", "kind": "tarjeta", "color": "#2e77bb", "aliases": ["american express", "amex"]},
    # efectivo: siempre disponible; algunos comercios hacen descuento por pagar así
    {"id": "efectivo", "name": "Efectivo", "kind": "efectivo", "color": "#6b7d74", "aliases": ["efectivo", "pago en efectivo"]},
]
METHOD_BY_ID = {m["id"]: m for m in METHODS}
KIND_LABEL = {"billetera": "Billeteras", "banco": "Bancos", "tarjeta": "Tarjetas", "efectivo": "Efectivo"}

# ------------------------------------------------------------------ rubros
RUBROS = [
    {"id": "super", "generic": "Supermercados", "name": "Súper", "icon": "🛒", "words": ["supermercado", "súper", "super", "almacén", "almacen", "hipermercado", "mayorista", "autoservicio", "verdulería", "verduleria", "carnicería", "carniceria"]},
    {"id": "comida", "generic": "Gastronomía", "name": "Comida", "icon": "🍽", "words": ["restaurante", "restaurant", "gastronomía", "gastronomia", "bar", "café", "cafe", "cafetería", "heladería", "pizzería", "pizzeria", "delivery", "comida", "parrilla", "panadería", "panaderia"]},
    {"id": "nafta", "generic": "Estaciones de servicio", "name": "Nafta", "icon": "⛽", "words": ["combustible", "nafta", "estación de servicio", "estaciones de servicio", "ypf", "shell", "axion", "puma"]},
    {"id": "farmacia", "generic": "Farmacias", "name": "Farmacia", "icon": "💊", "words": ["farmacia", "farmacias", "perfumería", "perfumeria"]},
    {"id": "ropa", "generic": "Ropa y calzado", "name": "Ropa", "icon": "👕", "words": ["indumentaria", "ropa", "calzado", "zapatillas", "moda"]},
    {"id": "hogar", "generic": "Hogar y electro", "name": "Hogar", "icon": "🏠", "words": ["electro", "electrodomésticos", "hogar", "ferretería", "ferreteria", "muebles", "deco"]},
    {"id": "transporte", "generic": "Transporte", "name": "Transporte", "icon": "🚌", "words": ["sube", "transporte", "colectivo", "taxi", "peaje", "estacionamiento"]},
    {"id": "entretenimiento", "generic": "Salidas y entretenimiento", "name": "Salidas", "icon": "🎬", "words": ["cine", "teatro", "espectáculos", "streaming", "entradas", "recitales"]},
    {"id": "servicios", "generic": "Pago de servicios", "name": "Servicios", "icon": "💡", "words": ["servicios", "luz", "gas", "agua", "internet", "celular", "telefonía"]},
    {"id": "otros", "generic": "Comercios adheridos", "name": "Otros", "icon": "•", "words": []},
]
RUBRO_BY_ID = {r["id"]: r for r in RUBROS}

DAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
DAYS_PLURAL = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábados", "domingos"]
DAYS_SHORT = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

GLOSSARY = [
    ("TNA", "Tasa nominal anual: el interés que te pagan en un año, sin reinvertir los intereses."),
    ("TEA", "Tasa efectiva anual: lo que ganás en un año si reinvertís los intereses. Es mayor que la TNA."),
    ("FCI", "Fondo común de inversión: juntás tu plata con la de otras personas y la invierte un equipo profesional."),
    ("Money market", "Tipo de fondo muy tranquilo, parecido a una cuenta remunerada. Se puede rescatar en el día."),
    ("Cuotaparte", "La unidad en la que se divide un fondo común de inversión."),
    ("Bono", "Un préstamo a un gobierno o empresa que te devuelve capital e intereses."),
    ("CEDEAR", "Certificado que se compra en pesos y representa acciones de empresas del exterior."),
    ("ALyC", "Agente de liquidación y compensación: la entidad registrada en la CNV donde se abre la cuenta para invertir."),
    ("CNV", "Comisión Nacional de Valores: el organismo que regula y registra a quienes operan en el mercado de capitales."),
    ("Reintegro", "Parte de una compra que te devuelven después (en la tarjeta o en la billetera), según la promo."),
    ("Tope de reintegro", "El máximo que te devuelven por una promo en un período, aunque gastes más."),
]
