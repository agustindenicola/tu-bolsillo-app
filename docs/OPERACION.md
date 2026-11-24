# Tu Bolsillo

App para pagar menos en cada compra, ver cuánto ahorrás y aprender a invertir.
Se instala en el celular desde el navegador (PWA) y manda notificaciones.

## Probarla en tu compu

```
pip install -r requirements.txt
python run.py
```

Abrí http://127.0.0.1:8770 y entrá con una cuenta de ejemplo (botones *Persona*, *Comercio*, *Empresa*, *Administración*).
Contraseña de todas las cuentas de ejemplo: `demo1234`.

- Sin datos de ejemplo: `python run.py --sin-demo`
- Crear un administrador: `python run.py crear-admin tu@mail.com`
- Correr el bot una vez: `python run.py bot`
- Pruebas automáticas: `python -m pytest`

Los datos quedan en la carpeta `datos/` (base de datos, claves de notificaciones y fotos subidas).

## Publicarla en internet (Railway)

La app necesita un servidor prendido siempre (para el bot y los avisos) y **https** (para las notificaciones).
Railway lo resuelve con pocos clics. Costo aproximado al arrancar: USD 5 por mes.

1. **Subí el código a GitHub.**
2. Entrá a **railway.com**, creá una cuenta e iniciá sesión con GitHub.
3. **New Project → Deploy from GitHub repo →** elegí `tu-bolsillo-app`. Railway detecta el `Dockerfile` solo.
4. En el servicio, **Settings → Volumes → Add volume**, con *mount path* `/data`. Ahí se guardan los datos: sin esto se borran en cada actualización.
5. En **Variables**, cargá:

   | Variable | Valor | Para qué |
   |---|---|---|
   | `TUBOLSILLO_ADMIN_EMAIL` | tu mail | crea tu cuenta de administrador |
   | `TUBOLSILLO_ADMIN_PASSWORD` | una contraseña larga | la contraseña de esa cuenta |
   | `TUBOLSILLO_DEMO` | `1` para mostrarla con datos de ejemplo, `0` para uso real | cuentas y promos de ejemplo |
   | `ANTHROPIC_API_KEY` | tu clave de la API de Claude (opcional) | el bot entiende textos difíciles y fotos de carteles, y se activa «Completar con la foto del ticket» |
   | `TUBOLSILLO_SMTP_HOST`, `TUBOLSILLO_SMTP_PORT`, `TUBOLSILLO_SMTP_USER`, `TUBOLSILLO_SMTP_PASSWORD` | datos de un mail (opcional) | para que la gente recupere su contraseña sola por mail. Con Gmail: `smtp.gmail.com`, `587`, tu mail y una «contraseña de aplicación» |

6. **Settings → Networking → Generate Domain.** Te da una dirección `https://….up.railway.app`. Esa es la app.

Cada vez que subas cambios a GitHub (`git push`), Railway la actualiza sola. Los datos del volumen no se tocan.

> Ya vienen configurados en el `Dockerfile`: `TUBOLSILLO_HTTPS=1` (cookies seguras y la cuenta demo de administración desactivada online), `TUBOLSILLO_DATA=/data` y `PORT`.
> Tiene que correr **una sola instancia** (la base es SQLite y las tareas automáticas corren adentro): no aumentes las réplicas.

## Instalarla en el celular y probar los avisos

- **Android (Chrome):** abrí la dirección → menú ⋮ → *Instalar app*. Después, Perfil → *Notificaciones* → activar → *Mandarme un aviso de prueba*.
- **iPhone (Safari, iOS 16.4 o más):** abrí la dirección → *Compartir* → *Agregar a inicio*. Abrí la app desde el ícono y activá las notificaciones en Perfil. En iPhone los avisos solo funcionan con la app instalada.

## Para cuando la use gente de verdad

- **Recuperar contraseña:** «¿Te olvidaste la contraseña?» en la pantalla de entrada. Con mail configurado, le llega un link (vale 2 horas, se usa una vez). Sin mail, generás el link en Administración → Recuperar la contraseña de alguien y se lo mandás.
- **Comentarios:** el botón 💬 de arriba (y en Perfil) abre «Contanos qué mejorar». Los ves en Administración → Comentarios de la gente.
- **Números de uso:** Administración → ¿La usan y vuelven? (activos por semana, retención y el recorrido desde que se registran hasta que la usan seguido).
- **Términos y privacidad:** se aceptan al crear la cuenta y están en Perfil. Revisalos y ajustalos antes de abrirla al público.
- **Gastos fijos:** en Gastos. Se cargan solos el día del mes elegido.

## El bot de promos

- Corre solo cada 6 horas (se cambia en Administración → Ajustes).
- Sin clave de Claude entiende las promos con reglas: lo que encuentra queda **para revisar** en el panel de administración.
- Con `ANTHROPIC_API_KEY` usa Claude (modelo `claude-opus-5-5`) y lee también fotos de carteles. Lo que tiene alta confianza se publica solo.
- **Fuentes recomendadas:** en Administración → Fuentes del bot está el botón «Agregar las recomendadas». Son páginas oficiales que el bot puede leer: MODO, Brubank, Personal Pay, Cuenta DNI, Ualá, Macro, American Express y Banco Ciudad. Banco Ciudad arma sus promos con JavaScript: el bot la abre con un navegador invisible (Playwright, ya incluido en el `Dockerfile`; en la compu usa Edge o Chrome). Cada fuente tiene su medio de pago, porque en la página de un banco las promos son de ese banco aunque no lo repitan. Hay también un botón para aprobar de una vez todo lo pendiente de una fuente. La lista de las que todavía no se pueden leer está en `tubolsillo/bot/fuentes.py`.
- **Otras fuentes:** agregalas en Administración → Fuentes del bot. Arrancan apagadas: antes de activarlas, revisá que los términos de uso del sitio permitan leerlo automáticamente. El bot además respeta el `robots.txt` de cada sitio.
- Cada "me funcionó / no me funcionó" de los usuarios ajusta la confianza de la promo y de su fuente. Una promo con varias quejas vuelve sola a revisión.

## Reglas que la app respeta

- **No recomienda inversiones:** solo informa y enseña. Recomendar inversiones está regulado por la CNV.
- **No pide claves bancarias** ni números de tarjeta: alcanza con saber qué medios usa cada persona.
- **Empresas y comercios solo ven totales**, nunca datos de una persona. El panel de empresa muestra números recién cuando hay 5 personas o más.
- Cada persona puede **descargar sus datos y borrar su cuenta** desde Perfil.
- Las promos de ejemplo están marcadas como **ejemplo**.

## Estructura

```
run.py                  arranque y comandos
tubolsillo/
  catalog.py            medios de pago, rubros, niveles, lecciones, glosario
  db.py                 base de datos
  core.py               con qué pagar, topes, ahorro, hábitos, personalización
  server.py             API y paneles
  push.py               notificaciones (Web Push)
  scheduler.py          bot periódico, aviso de la noche, alertas de tope
  seed.py               datos de ejemplo
  bot/                  buscar, entender (reglas o Claude), verificar y aprender
  static/               la app (pantallas, ícono, instalación)
tests/                  pruebas automáticas
```
