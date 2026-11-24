"""Fuentes reales recomendadas: páginas oficiales de beneficios que el bot puede leer.

Probadas el 2026-11-09: todas permiten lectura automática en su robots.txt. Las marcadas «navegador» arman las promos
con JavaScript y se abren con un navegador invisible (Playwright). Las que no se pueden leer así quedan anotadas abajo para más adelante.
"""

RECOMENDADAS = [
    # nombre, dirección, medio de pago de la página, nota
    ("MODO: promos destacadas", "https://www.modo.com.ar/promos", "modo",
     "Promos de MODO de más de 30 bancos (súper, farmacias, combustible). Trae la fecha de vencimiento."),
    ("Brubank: beneficios", "https://www.brubank.com/beneficios", "brubank",
     "Ojo: algunas promos dependen del plan (One, Plus, Ultra). Revisá las condiciones al aprobar."),
    ("Personal Pay: beneficios", "https://www.personal.com.ar/pay/beneficios", "personalpay", ""),
    ("Cuenta DNI: beneficios", "https://www.bancoprovincia.com.ar/cuentadni/contenidos/cdnibeneficios/", "cuentadni",
     "Muchas son por rubro (súper, comercios de cercanía) y no nombran un comercio."),
    ("Ualá: promociones", "https://www.uala.com.ar/promociones", "uala", ""),
    ("Macro: beneficios", "https://www.macro.com.ar/beneficios", "macro", "Muestra pocas promos destacadas."),
    ("American Express: promociones", "https://www.americanexpress.com/es-ar/beneficios/promociones/", "amex", ""),
    ("Banco Ciudad: beneficios", "https://www.bancociudad.com.ar/beneficios/", "ciudad",
     "Se lee con navegador (la página arma las promos con JavaScript). Muchos comercios de CABA.", "navegador"),
]

# No se pueden leer automáticamente hoy (robots.txt no lo permite o arman las promos con JavaScript).
NO_LEGIBLES = {
    "Mercado Pago": "robots.txt no lo permite; las promos están dentro de su app",
    "Naranja X": "robots.txt no lo permite",
    "BBVA": "robots.txt no lo permite",
    "Supervielle": "robots.txt no lo permite",
    "Prex": "robots.txt no lo permite",
    "Carrefour": "robots.txt no lo permite",
    "La Anónima": "robots.txt no lo permite",
    "Galicia": "con navegador muestra solo un buscador vacío: las promos aparecen después de elegir filtros",
    "Santander": "la página corta la conexión a los programas (error de protocolo), aun con navegador",
    "ICBC": "con navegador se leen los porcentajes, pero los comercios están en imágenes",
    "Jumbo, Disco, Vea, Día, Coto": "las promos bancarias están en imágenes, no en texto",
    "Credicoop, Farmacity, Changomás, Banco Nación, Patagonia, Comafi": "la página de beneficios no muestra promos legibles (redirige, está vacía o da error)",
}

NOTA = "Cargada desde las recomendadas. El bot lee solo lo que permite el robots.txt del sitio. Revisá sus términos antes de abrir la app al público."


def install(con, enable=True):
    """Agrega las recomendadas que falten (no toca las que ya están). Devuelve cuántas agregó."""
    have = {r["url"] for r in con.execute("SELECT url FROM sources")}
    n = 0
    for name, url, method, note, *kind in RECOMENDADAS:
        if url in have:
            continue
        con.execute("INSERT INTO sources(name, url, kind, enabled, tos_ok, trust, notes, method_id) VALUES(?,?,?,?,?, 0.7, ?, ?)",
                    (name, url, kind[0] if kind else "html", int(enable), int(enable), (note + " " + NOTA).strip(), method))
        n += 1
    return n
