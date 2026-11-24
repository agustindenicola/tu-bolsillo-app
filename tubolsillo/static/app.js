/* Tu Bolsillo — la app. Pantallas, navegación y conexión con el servidor. */
(() => {
  "use strict";
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const root = $("#root");
  const S = { me: null, cat: null, installEvt: null, home: null, pay: {} };

  // ---------------------------------------------------------------- utilidades
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = v => "$ " + Math.round(Number(v) || 0).toLocaleString("es-AR");
  const pctTxt = v => `${Number(v).toLocaleString("es-AR", { maximumFractionDigits: 1 })}%`;
  const todayIso = () => { const d = new Date(); return new Date(d - d.getTimezoneOffset() * 6e4).toISOString().slice(0, 10); };
  const addDays = (iso, n) => { const d = new Date(iso + "T12:00"); d.setDate(d.getDate() + n); return d.toISOString().slice(0, 10); };
  const wd = iso => (new Date(iso + "T12:00").getDay() + 6) % 7;   // 0 = lunes
  const fdate = iso => { if (!iso) return ""; const [y, m, d] = iso.split("-"); return `${+d}/${+m}${y !== String(new Date().getFullYear()) ? "/" + y.slice(2) : ""}`; };
  const longDate = () => new Date().toLocaleDateString("es-AR", { weekday: "long", day: "numeric", month: "long" });
  const method = id => S.cat.methods.find(m => m.id === id) || { id, name: id, kind: "otro", color: "#888" };
  const rubro = id => S.cat.rubros.find(r => r.id === id) || { id, name: "Otros", icon: "•" };
  const PALETTE = ["#c0582f", "#2f8f5b", "#8a5a2b", "#b5452c", "#4d8a2a", "#5b6b8c", "#a83a3a", "#7a5aa8", "#2c7a8a", "#a07a1f"];
  const colorFor = name => PALETTE[[...String(name)].reduce((a, c) => a + c.charCodeAt(0), 0) % PALETTE.length];
  const initials = name => String(name).split(/\s+/).filter(w => w.length > 2 || /^[A-ZÁÉÍÓÚ]/.test(w)).slice(0, 2).map(w => w[0]).join("").toUpperCase() || "•";
  const daysTxt = days => {
    const ds = String(days).split("").map(Number);
    if (ds.length === 7) return "Todos los días";
    if (ds.join("") === "56") return "Fines de semana";
    if (ds.join("") === "01234") return "Lunes a viernes";
    return ds.map(i => S.cat.days[i]).join(", ");
  };
  const store = { get: k => { try { return localStorage.getItem(k); } catch (_) { return null; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch (_) {} } };
  const ICON = {
    inicio: '<path d="M4 11l8-7 8 7v8a1 1 0 0 1-1 1h-4v-6h-6v6H5a1 1 0 0 1-1-1z"/>',
    promos: '<path d="M20 12l-8 8-8-8V4h8z"/><circle cx="8.5" cy="8.5" r="1.5"/>',
    pagar: '<path d="M12 5v14M5 12h14"/>',
    gastos: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    aprender: '<path d="M2 8l10-5 10 5-10 5z"/><path d="M6 10v5c3 2 9 2 12 0v-5"/>',
    bell: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 8 3 8H3s3-1 3-8"/><path d="M10 20a2 2 0 0 0 4 0"/>',
    pin: '<path d="M12 21s-7-6.5-7-12a7 7 0 0 1 14 0c0 5.5-7 12-7 12z"/><circle cx="12" cy="9" r="2.5"/>',
    back: '<path d="M15 18l-6-6 6-6"/>',
    chat: '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/>',
    camera: '<path d="M4 8h3l2-3h6l2 3h3v11H4z"/><circle cx="12" cy="13" r="3.5"/>',
  };
  const svg = (k, size = 20) => `<svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${ICON[k]}</svg>`;

  async function api(path, { method: m = "GET", json, form } = {}) {
    const opts = { method: m, headers: { "X-TB": "1" }, credentials: "same-origin" };
    if (json !== undefined) { opts.body = JSON.stringify(json); opts.headers["Content-Type"] = "application/json"; }
    if (form) opts.body = form;
    let r;
    try { r = await fetch(path, opts); } catch (_) { throw new Error("No hay conexión. Revisá internet y probá de nuevo."); }
    const data = r.headers.get("content-type")?.includes("json") ? await r.json() : null;
    if (r.status === 401 && path !== "/api/me") { S.me = null; renderAuth(); throw new Error("Iniciá sesión para seguir"); }
    if (!r.ok) throw new Error(data?.error || `Error ${r.status}`);
    return data;
  }

  function toast(msg, action, ms = 3200) {
    $(".toast")?.remove();
    const t = document.createElement("div");
    t.className = "toast"; t.setAttribute("role", "status");
    t.innerHTML = `<span>${esc(msg)}</span>`;
    if (action) { const b = document.createElement("button"); b.textContent = action.label; b.onclick = () => { t.remove(); action.fn(); }; t.appendChild(b); ms = 7000; }
    document.body.appendChild(t);
    setTimeout(() => t.remove(), ms);
  }

  function sheet(html, onMount) {
    const bg = document.createElement("div");
    bg.className = "sheet-bg";
    bg.innerHTML = `<div class="sheet" role="dialog" aria-modal="true"><div class="grab"></div>${html}</div>`;
    const close = () => { bg.remove(); document.removeEventListener("keydown", onKey); };
    const onKey = e => { if (e.key === "Escape") close(); };
    document.addEventListener("keydown", onKey);
    bg.addEventListener("click", e => { if (e.target === bg || e.target.closest("[data-close]")) close(); });
    document.body.appendChild(bg);
    onMount?.(bg, close);
    $("input, button:not([data-close])", $(".sheet", bg))?.focus({ preventScroll: true });
    return { bg, close };
  }

  async function busy(btn, fn) {
    if (btn.disabled) return;
    btn.disabled = true;
    try { return await fn(); } catch (e) { toast(e.message); } finally { btn.disabled = false; }
  }

  const payTag = id => { const m = method(id); return `<span class="paytag"><i style="background:${m.color}"></i>${esc(m.name)}</span>`; };
  const badges = p => `${p.is_example ? ' <span class="badge ex">ejemplo</span>' : ""}${p.habit ? ' <span class="badge habit">vas seguido</span>' : ""}${p.exclusive ? ' <span class="badge ok">tu empresa</span>' : ""}`;
  const promoRow = p => `<button class="promo" data-promo="${p.id}"><span class="logo" style="background:${colorFor(p.name)}">${esc(initials(p.name))}</span>
    <span style="min-width:0"><b>${esc(p.name)}${badges(p)}</b><span class="sub">${esc(rubro(p.rubro).name)} · ${esc(daysTxt(p.days))}</span><br>${payTag(p.method_id)}</span>
    <span class="pct">${pctTxt(p.pct)}</span></button>`;


  // ---------------------------------------------------------------- términos y privacidad
  const LEGAL = {
    terminos: { title: "Términos de uso", sections: [
      ["Qué es Tu Bolsillo", "Una app que te ayuda a elegir con qué pagar para aprovechar descuentos, a llevar la cuenta de tus gastos y de lo que ahorrás, y a aprender conceptos de finanzas personales. Está en etapa de prueba: puede tener errores y cambiar."],
      ["Las promos", "Las promociones son de bancos, billeteras y comercios, no de Tu Bolsillo. Las buscamos y verificamos lo mejor posible, pero pueden cambiar, tener condiciones o dejar de existir sin aviso. Antes de pagar, si es importante para vos, confirmá la promo con quien la ofrece. Las marcadas como «ejemplo» no son reales."],
      ["No es asesoramiento financiero", "Los contenidos de Aprender y la calculadora son información general para aprender. No son recomendaciones de inversión ni de productos. Antes de invertir, informate y verificá que la entidad esté registrada en la CNV."],
      ["Tu cuenta", "Sos responsable de cuidar tu contraseña. Tu Bolsillo nunca te va a pedir claves bancarias ni datos completos de tarjetas. Podés borrar tu cuenta cuando quieras desde Perfil."],
      ["Uso correcto", "No uses la app para cargar promos falsas ni para molestar a otras personas. Podemos suspender cuentas que lo hagan."],
      ["Cambios", "Si cambiamos estos términos, te lo vamos a avisar en la app."],
    ] },
    privacidad: { title: "Política de privacidad", sections: [
      ["Qué datos guardamos", "Tu nombre y mail, la contraseña cifrada (nadie puede verla), los medios de pago que elegís (solo el nombre: «Mercado Pago», «Galicia»; nunca números ni claves), los gastos que cargás, tus objetivos, los temas que leíste y, si lo activás, la suscripción para recibir notificaciones."],
      ["Para qué los usamos", "Para mostrarte promos que te sirvan, calcular cuánto ahorrás, aprender tus hábitos si dejás activada la personalización, y mandarte los avisos que elegiste. También miramos números generales de uso (cuántas personas la usan y vuelven) para mejorar la app."],
      ["Ubicación y fotos", "La ubicación se usa solo en tu celular, con la app abierta y si das permiso, para avisarte de comercios cerca: no guardamos tu recorrido. Las fotos de tickets se leen para completar el gasto y no se guardan. Las fotos de promos que subís se guardan para verificarlas."],
      ["Con quién los compartimos", "No vendemos tus datos. Comercios, bancos y empresas solo ven totales anónimos (por ejemplo, cuántas personas usaron una promo), nunca datos de una persona. Si la lectura de promos o tickets usa un servicio de inteligencia artificial, le mandamos solo ese texto o esa imagen."],
      ["Tus derechos", "Podés ver y descargar tus datos (Perfil → Descargar mis datos), corregirlos y borrar tu cuenta con todo lo que cargaste (Perfil → Borrar mi cuenta). Estos derechos están protegidos por la Ley 25.326 de Protección de Datos Personales; la Agencia de Acceso a la Información Pública es el organismo de control."],
      ["Contacto", "Si tenés dudas sobre tus datos, escribinos desde «Contanos qué mejorar» en la app."],
    ] },
  };
  function legalSheet(kind) {
    const L = LEGAL[kind];
    sheet(`<span class="label">Tu Bolsillo</span><h2>${esc(L.title)}</h2>
      ${L.sections.map(([h, t]) => `<section class="read"><h3>${esc(h)}</h3><p>${esc(t)}</p></section>`).join("")}
      <p class="fine">Versión de prueba · noviembre de 2026</p><button class="btn full" data-close>Cerrar</button>`);
  }

  // ---------------------------------------------------------------- arranque
  async function boot() {
    if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
    window.addEventListener("beforeinstallprompt", e => { e.preventDefault(); S.installEvt = e; });
    try {
      [S.cat, S.me] = await Promise.all([api("/api/catalog"), api("/api/me")]);
    } catch (e) {
      root.innerHTML = `<div class="auth"><h1>Tu <span>Bolsillo</span></h1><p>${esc(e.message)}</p><button class="btn" onclick="location.reload()">Reintentar</button></div>`;
      return;
    }
    if (!S.resetHook) {   // el link de recuperar contraseña puede abrirse con la app ya abierta
      S.resetHook = true;
      window.addEventListener("hashchange", () => { const r = location.hash.match(/^#reset\/([\w-]+)$/); if (r) renderReset(r[1]); });
    }
    const m = location.hash.match(/^#reset\/([\w-]+)$/);
    if (m) return renderReset(m[1]);
    if (!S.me.user) return renderAuth();
    if (S.me.user.role === "user" && !S.me.user.onboarded) return renderOnboarding();
    window.addEventListener("hashchange", route);
    route();
  }
  async function refreshMe() { S.me = await api("/api/me"); }

  // ---------------------------------------------------------------- entrar / crear cuenta
  function renderAuth(mode = "login") {
    window.removeEventListener("hashchange", route);
    root.innerHTML = `<div class="auth">
      <div class="brand"><i>$</i>Tu Bolsillo</div>
      <h1>Que tu plata <span>rinda</span>.</h1>
      <p>Te decimos con qué pagar en cada lugar para gastar menos, sumamos lo que ahorrás y te enseñamos a dar el primer paso para invertir.</p>
      <div class="seg" role="group"><button data-mode="login" aria-pressed="${mode === "login"}">Entrar</button><button data-mode="register" aria-pressed="${mode === "register"}">Crear cuenta</button></div>
      <form id="authf" class="card" novalidate>
        ${mode === "register" ? `<label class="field" for="a-name">Tu nombre<input id="a-name" autocomplete="given-name" required></label>` : ""}
        <label class="field" for="a-email">Mail<input id="a-email" type="email" autocomplete="email" inputmode="email" required></label>
        <label class="field" for="a-pass">Contraseña<input id="a-pass" type="password" autocomplete="${mode === "register" ? "new-password" : "current-password"}" required minlength="8"></label>
        ${mode === "register" ? `<p class="fine" style="margin:0">Mínimo 8 caracteres. Nunca te vamos a pedir claves de tu banco.</p>
          <label class="check"><input type="checkbox" id="a-terms"><span>Acepto los <button type="button" class="link" data-legal="terminos">términos de uso</button> y la <button type="button" class="link" data-legal="privacidad">política de privacidad</button>.</span></label>` : ""}
        <button class="btn full" type="submit">${mode === "register" ? "Crear mi cuenta" : "Entrar"}</button>
        ${mode === "login" ? `<button type="button" class="link" id="forgot" style="align-self:center">¿Te olvidaste la contraseña?</button>` : ""}
      </form>
      ${S.me?.demo ? `<div class="card"><span class="label">Probar sin crear cuenta</span><div class="sub">Cuentas de ejemplo con datos inventados:</div>
        <div class="demo-row"><button class="btn dark sm" data-demo="user">Persona</button><button class="btn ghost sm" data-demo="comercio">Comercio</button>
        <button class="btn ghost sm" data-demo="empresa">Empresa</button>${S.cat.demo_admin ? `<button class="btn ghost sm" data-demo="admin">Administración</button>` : ""}</div></div>` : ""}
    </div>`;
    $$("[data-mode]").forEach(b => b.onclick = () => renderAuth(b.dataset.mode));
    $("#authf").onsubmit = e => {
      e.preventDefault();
      busy($("#authf button[type=submit]"), async () => {
        const json = { email: $("#a-email").value, password: $("#a-pass").value };
        if (mode === "register") { json.name = $("#a-name").value; json.accept_terms = $("#a-terms").checked; }
        await api(mode === "register" ? "/api/register" : "/api/login", { method: "POST", json });
        location.hash = ""; await boot();
      });
    };
    $$("[data-demo]").forEach(b => b.onclick = () => busy(b, async () => {
      await api("/api/demo-login", { method: "POST", json: { role: b.dataset.demo } });
      location.hash = ""; await boot();
    }));
    $$("[data-legal]").forEach(b => b.onclick = () => legalSheet(b.dataset.legal));
    $("#forgot")?.addEventListener("click", () => sheet(`<h2>Recuperar la contraseña</h2>
      <div class="sub">Escribí el mail de tu cuenta y te mandamos un link para elegir una contraseña nueva.</div>
      <label class="field" for="f-email">Mail<input id="f-email" type="email" inputmode="email" autocomplete="email" value="${esc($("#a-email").value)}"></label>
      <button class="btn full" id="f-go">Mandarme el link</button><div id="f-out"></div>`, bg => {
      $("#f-go", bg).onclick = e => busy(e.currentTarget, async () => {
        const r = await api("/api/password/forgot", { method: "POST", json: { email: $("#f-email", bg).value } });
        $("#f-out", bg).innerHTML = r.dev_link
          ? `<div class="card near"><span class="sub">El envío de mails todavía no está configurado. Como estás probando en tu compu, este es el link:</span><a class="btn sm" href="${esc(r.dev_link)}">Elegir contraseña nueva</a></div>`
          : r.mail ? `<div class="card near"><span class="sub">Si hay una cuenta con ese mail, te llegó un link (mirá también en spam). Vale 2 horas.</span></div>`
          : `<div class="card near"><span class="sub">Pedile a quien administra Tu Bolsillo que te pase el link para recuperar tu contraseña.</span></div>`;
      });
    }));
  }

  function renderReset(token) {
    window.removeEventListener("hashchange", route);
    $$(".sheet-bg").forEach(x => x.remove());
    root.innerHTML = `<div class="auth"><div class="brand"><i>$</i>Tu Bolsillo</div><h2 style="font-size:28px">Elegí una contraseña nueva</h2>
      <form id="rf" class="card" novalidate><label class="field" for="r-pass">Contraseña nueva<input id="r-pass" type="password" autocomplete="new-password" minlength="8"></label>
      <p class="fine" style="margin:0">Mínimo 8 caracteres.</p><button class="btn full" type="submit">Guardar y entrar</button></form></div>`;
    $("#rf").onsubmit = e => {
      e.preventDefault();
      busy($("#rf button"), async () => {
        await api("/api/password/reset", { method: "POST", json: { token, password: $("#r-pass").value } });
        history.replaceState(null, "", "/"); toast("Listo: ya tenés contraseña nueva."); await boot();
      });
    };
  }

  // ---------------------------------------------------------------- bienvenida (primera vez)
  function renderOnboarding(step = 1, chosen = new Set(S.me.methods)) {
    const steps = `<div class="steps">${[1, 2, 3].map(i => `<i class="${i <= step ? "on" : ""}"></i>`).join("")}</div>`;
    if (step === 1) {
      root.innerHTML = `<div class="auth" style="justify-content:flex-start">${steps}
        <h2 style="font-size:28px">¿Con qué pagás?</h2>
        <p>Elegí tus billeteras, bancos y tarjetas. Así te mostramos solo las promos que podés usar. El efectivo ya está incluido.</p>
        <input class="input" id="ms-q" placeholder="Buscar (ej. Mercado Pago, Galicia…)" aria-label="Buscar medio de pago">
        <div id="ms"></div>
        <button class="btn full" id="next">Seguir</button></div>`;
      const draw = () => { $("#ms").innerHTML = methodPicker(chosen, $("#ms-q").value); bindPicker($("#ms"), chosen); };
      $("#ms-q").oninput = draw; draw();
      $("#next").onclick = () => busy($("#next"), async () => {
        if (!chosen.size) return toast("Elegí al menos uno (o seguí solo con efectivo desde Perfil)");
        await api("/api/me", { method: "PUT", json: { methods: [...chosen] } });
        renderOnboarding(2, chosen);
      });
    } else if (step === 2) {
      root.innerHTML = `<div class="auth" style="justify-content:flex-start">${steps}
        <h2 style="font-size:28px">Avisos que te ahorran plata</h2>
        <p>Te avisamos la noche anterior las mejores promos para lo que solés comprar, y cuando estás cerca de un comercio con descuento.</p>
        <div class="card">
          <label class="field" for="ob-hour">¿A qué hora te aviso?<select id="ob-hour">${[18, 19, 20, 21, 22].map(h => `<option value="${h}" ${h === S.me.user.notify_hour ? "selected" : ""}>${h}:00</option>`).join("")}</select></label>
          <button class="btn full" id="ob-push">Activar notificaciones</button>
          <button class="btn ghost full" id="ob-geo">Avisarme cuando esté cerca</button>
          <p class="fine" style="margin:0">Podés cambiarlo cuando quieras en Perfil.</p>
        </div>
        <button class="btn full dark" id="next">Seguir</button></div>`;
      $("#ob-push").onclick = () => busy($("#ob-push"), async () => { await enablePush(); $("#ob-push").textContent = "Notificaciones activadas ✓"; });
      $("#ob-geo").onclick = () => busy($("#ob-geo"), async () => { await askGeo(); $("#ob-geo").textContent = "Avisos por cercanía activados ✓"; });
      $("#next").onclick = () => busy($("#next"), async () => {
        await api("/api/me", { method: "PUT", json: { notify_hour: +$("#ob-hour").value } });
        renderOnboarding(3, chosen);
      });
    } else {
      root.innerHTML = `<div class="auth">${steps}
        <div class="medal">$</div>
        <h2 style="font-size:28px;text-align:center">¡Listo, ${esc(S.me.user.name)}!</h2>
        <p style="text-align:center">Antes de pagar, tocá el <b>+</b> de abajo: te decimos con qué te conviene pagar. Cada peso que ahorrás suma para desbloquear lecciones para aprender a invertir.</p>
        <button class="btn full" id="go">Empezar</button></div>`;
      $("#go").onclick = () => busy($("#go"), async () => {
        await api("/api/me", { method: "PUT", json: { onboarded: true } });
        await refreshMe(); location.hash = "#inicio"; window.addEventListener("hashchange", route); route();
      });
    }
  }
  function methodPicker(chosen, q = "") {
    const n = s => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
    const groups = [["billetera", "Billeteras virtuales"], ["banco", "Bancos (débito y crédito)"], ["tarjeta", "Tarjetas"]];
    return groups.map(([k, label]) => {
      const ms = S.cat.methods.filter(m => m.kind === k && (!q || n(m.name).includes(n(q))));
      if (!ms.length) return "";
      return `<div class="label" style="margin:12px 0 8px">${label}</div><div class="method-grid">${ms.map(m =>
        `<button class="method" data-m="${m.id}" aria-pressed="${chosen.has(m.id)}"><i style="background:${m.color}"></i>${esc(m.name)}</button>`).join("")}</div>`;
    }).join("") || `<div class="empty">No encontramos ese medio de pago.</div>`;
  }
  function bindPicker(el, chosen) {
    $$("[data-m]", el).forEach(b => b.onclick = () => {
      chosen.has(b.dataset.m) ? chosen.delete(b.dataset.m) : chosen.add(b.dataset.m);
      b.setAttribute("aria-pressed", String(chosen.has(b.dataset.m)));
    });
  }

  // ---------------------------------------------------------------- estructura y navegación
  const USER_TABS = [["inicio", "Inicio"], ["promos", "Promos"], ["pagar", "Pagar"], ["gastos", "Gastos"], ["aprender", "Aprender"]];
  function shell() {
    const u = S.me.user;
    const isUser = u.role === "user";
    root.innerHTML = `<div class="app">
      <header class="top"><div class="brand"><i>$</i>Tu Bolsillo</div>
        <div class="top-actions">
          ${u.role === "user" ? `<button class="icon-btn" id="fb-open" aria-label="Contanos qué mejorar">${svg("chat")}</button>` : ""}
          <button class="icon-btn" data-go="avisos" aria-label="Avisos">${svg("bell")}${S.me.unread ? `<span class="dot-badge">${S.me.unread}</span>` : ""}</button>
          <button class="avatar" data-go="perfil" aria-label="Perfil">${esc(initials(u.name))}</button></div></header>
      <main id="main"></main>
      ${isUser ? `<nav class="tabbar" aria-label="Secciones">${USER_TABS.map(([k, l]) => k === "pagar"
        ? `<button class="pay" data-go="pagar" aria-label="Antes de pagar"><span class="fab">${svg("pagar")}</span>${l}</button>`
        : `<button data-go="${k}">${svg(k)}${l}</button>`).join("")}</nav>` : ""}
    </div>`;
    $$("[data-go]", root).forEach(b => b.onclick = () => go(b.dataset.go));
    $("#fb-open")?.addEventListener("click", feedbackSheet);
  }
  function feedbackSheet() {
    let kind = "idea";
    sheet(`<h2>Contanos qué mejorar</h2><div class="sub">Lo lee una persona. Nos ayuda muchísimo para que la app te sirva más.</div>
      <div class="chips wrap" id="fb-kind">${[["idea", "💡 Una idea"], ["problema", "⚠ Algo anda mal"], ["otro", "💬 Otra cosa"]].map(([k, l]) => `<button class="chip" data-k="${k}" aria-pressed="${k === kind}">${l}</button>`).join("")}</div>
      <label class="field" for="fb-text">Contanos<textarea id="fb-text" placeholder="Ej: me gustaría que…"></textarea></label>
      <button class="btn full" id="fb-go">Enviar</button>`, (bg, close) => {
      $$("[data-k]", bg).forEach(b => b.onclick = () => { kind = b.dataset.k; $$("[data-k]", bg).forEach(x => x.setAttribute("aria-pressed", String(x === b))); });
      $("#fb-go", bg).onclick = e => busy(e.currentTarget, async () => {
        await api("/api/feedback", { method: "POST", json: { kind, text: $("#fb-text", bg).value, screen: location.hash.slice(1) } });
        close(); toast("¡Gracias! Lo vamos a leer.");
      });
    });
  }
  function go(view) { if (location.hash.slice(1) === view) route(); else location.hash = view; }
  const VIEWS = {};
  async function route() {
    if (!S.me?.user) return renderAuth();
    const u = S.me.user;
    const home = { user: "inicio", comercio: "comercio", empresa: "empresa", admin: "admin" }[u.role];
    let view = location.hash.slice(1) || home;
    if (u.role !== "user" && ["inicio", "promos", "pagar", "gastos", "aprender"].includes(view)) view = home;
    if (!$("#main")) shell();
    $$(".tabbar [data-go]").forEach(b => b.dataset.go === view ? b.setAttribute("aria-current", "page") : b.removeAttribute("aria-current"));
    const main = $("#main");
    main.innerHTML = `<div class="empty">Cargando…</div>`;
    try { await (VIEWS[view] || VIEWS[home])(main); } catch (e) { main.innerHTML = `<div class="card"><b>No se pudo cargar</b><div class="sub">${esc(e.message)}</div><button class="btn sm" onclick="location.reload()">Reintentar</button></div>`; }
    window.scrollTo(0, 0);
  }
  function setUnread(n) {
    S.me.unread = n;
    const b = $(".icon-btn[data-go=avisos]");
    if (b) { $(".dot-badge", b)?.remove(); if (n) b.insertAdjacentHTML("beforeend", `<span class="dot-badge">${n}</span>`); }
  }
  function bindCommon(el) {
    $$("[data-promo]", el).forEach(b => b.onclick = () => promoSheet(+b.dataset.promo));
    $$("[data-go]", el).forEach(b => b.onclick = () => go(b.dataset.go));
    $$("[data-lesson]", el).forEach(b => b.onclick = () => lessonSheet(b.dataset.lesson));
  }

  // ---------------------------------------------------------------- INICIO
  VIEWS.inicio = async main => {
    const h = S.home = await api("/api/home");
    const t = h.totals, goal = h.goals[0];
    const prog = goal ? Math.min(100, t.saved_total / goal.target * 100) : 0;
    const hr = new Date().getHours();
    main.innerHTML = `
      <div class="hello"><small>${esc(longDate())}</small><h1>${hr < 13 ? "Buen día" : hr < 20 ? "Buenas tardes" : "Buenas noches"}, ${esc(S.me.user.name)}</h1></div>
      <section class="hero">
        <div class="row between"><span class="label">Ahorraste en total</span><span class="chip-l">+${money(t.saved_month)} este mes</span></div>
        <div class="big num">${money(t.saved_total)}</div>
        ${goal ? `<div class="row between"><small>Objetivo: ${esc(goal.name)}</small><small>${t.saved_total >= goal.target ? "¡lo lograste!" : `te faltan <span class="num">${money(goal.target - t.saved_total)}</span>`}</small></div>
        <div class="bar"><i style="width:${prog}%"></i></div>` : `<div class="row between"><small>${t.uses} ${t.uses === 1 ? "descuento usado" : "descuentos usados"}</small><button class="chip-l" data-go="aprender" style="border:0;color:inherit">+ Ponerte un objetivo</button></div>`}
      </section>
      ${!h.has_methods ? `<button class="card near" data-go="perfil"><b>Contanos con qué pagás</b><span class="sub">Agregá tus billeteras y bancos para ver tus promos.</span></button>` : ""}
      <div id="near"></div>
      <div class="grid2"><button class="btn dark" data-go="pagar">Antes de pagar</button><button class="btn ghost" id="quick-gasto">Cargar un gasto</button></div>
      <section class="card"><div class="card-head"><h3>Para vos hoy</h3><button class="btn ghost sm" data-go="promos">Ver todas</button></div>
        ${h.today.length ? h.today.map(promoRow).join("") : `<div class="empty">Hoy no hay promos para tus medios de pago. Mirá otros días en Promos.</div>`}</section>
      ${h.insights.length ? `<section class="card"><div class="card-head"><h3>Aprendiendo de vos</h3><span class="label">${h.habits_n} gastos</span></div>
        ${h.insights.map(i => `<div class="insight"><span class="ic">${esc(i.icon)}</span><span>${i.text}</span></div>`).join("")}</section>`
        : S.me.user.personal ? `<section class="card"><h3>Aprendiendo de vos</h3><div class="sub">Cargá tus gastos (también los de efectivo) y en unos días te mostramos tus hábitos y cómo ahorrar más.</div></section>` : ""}
      ${h.goals.slice(1).map(g => `<section class="card"><div class="card-head"><h3>Objetivo: ${esc(g.name)}</h3><span class="sub num">${money(Math.min(t.saved_total, g.target))} / ${money(g.target)}</span></div>
        <div class="bar light"><i style="width:${Math.min(100, t.saved_total / g.target * 100)}%"></i></div></section>`).join("")}
      ${h.suggestion ? `<section class="card"><div class="card-head"><h3>Te puede interesar</h3><span class="label">${h.suggestion.min} min de lectura</span></div>
        <button class="article" data-lesson="${h.suggestion.id}"><b>${esc(h.suggestion.title)}</b><span class="sub">${esc(h.suggestion.summary)}</span></button></section>` : ""}
      ${installCard()}`;
    bindCommon(main);
    $("#quick-gasto").onclick = () => { S.pay = { mode: "gasto" }; go("pagar"); };
    bindInstall(main);
    if (store.get("tb_geo") === "1") showNearby();
  };

  async function showNearby() {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(async pos => {
      try {
        const list = await api(`/api/nearby?lat=${pos.coords.latitude}&lng=${pos.coords.longitude}`);
        const p = list[0], el = $("#near");
        if (!p || !el) return;
        el.innerHTML = `<button class="card near" data-promo="${p.id}"><div class="row"><span class="pin">${svg("pin", 18)}</span>
          <div class="grow"><b>Estás a ${p.distance_m} m de ${esc(p.name)}</b><div class="sub">Hoy ${pctTxt(p.pct)} con ${esc(p.method)}.${p.cap_left != null ? ` Te quedan ${money(p.cap_left)} de reintegro.` : ""}</div></div></div></button>`;
        bindCommon(el);
      } catch (_) {}
    }, () => {}, { maximumAge: 120000, timeout: 8000 });
  }
  function askGeo() {
    return new Promise((ok, fail) => {
      if (!navigator.geolocation) return fail(new Error("Este navegador no permite usar la ubicación"));
      navigator.geolocation.getCurrentPosition(() => { store.set("tb_geo", "1"); ok(); },
        () => fail(new Error("No diste permiso de ubicación. Lo podés activar en la configuración del navegador.")), { timeout: 10000 });
    });
  }

  function isIos() { return /iphone|ipad|ipod/i.test(navigator.userAgent); }
  function standalone() { return matchMedia("(display-mode: standalone)").matches || navigator.standalone; }
  function installCard() {
    if (standalone()) return "";
    if (S.installEvt) return `<section class="card"><h3>Instalá la app</h3><div class="sub">Queda en tu pantalla de inicio y te llegan los avisos.</div><button class="btn" id="install">Instalar Tu Bolsillo</button></section>`;
    if (isIos()) return `<section class="card"><h3>Instalala en tu iPhone</h3><div class="sub">Tocá <b>Compartir</b> y después <b>Agregar a inicio</b>. En iPhone, los avisos solo llegan con la app instalada.</div></section>`;
    return "";
  }
  function bindInstall(el) {
    const b = $("#install", el);
    if (b) b.onclick = async () => { S.installEvt.prompt(); await S.installEvt.userChoice; S.installEvt = null; b.closest(".card").remove(); };
  }

  // ---------------------------------------------------------------- PROMOS
  const PS = { day: null, rubro: "", q: "", all: false, saved: false };
  VIEWS.promos = async main => {
    PS.day = PS.day || todayIso();
    const days = Array.from({ length: 7 }, (_, i) => addDays(todayIso(), i));
    const qs = new URLSearchParams({ day: PS.day, rubro: PS.rubro, q: PS.q, all: PS.all ? "1" : "0", saved: PS.saved ? "1" : "0" });
    const data = await api("/api/promos?" + qs);
    main.innerHTML = `
      <div class="hello"><small>${PS.all ? "Todas las promos, aunque no tengas ese medio" : "Solo las que podés usar con tus medios de pago"}</small><h1>Promos</h1></div>
      <div class="days">${days.map(d => `<button data-day="${d}" aria-pressed="${d === PS.day}">${S.cat.days_short[wd(d)]}<span>${+d.slice(8)}</span></button>`).join("")}</div>
      <input class="input" id="pq" type="search" placeholder="Buscar comercio o medio de pago" value="${esc(PS.q)}" aria-label="Buscar promos">
      <div class="chips"><button class="chip" data-rubro="" aria-pressed="${!PS.rubro}">Todo</button>${S.cat.rubros.filter(r => r.id !== "otros").map(r =>
        `<button class="chip" data-rubro="${r.id}" aria-pressed="${PS.rubro === r.id}">${r.icon} ${esc(r.name)}</button>`).join("")}</div>
      <div class="chips"><button class="chip" id="p-saved" aria-pressed="${PS.saved}">★ Guardadas</button><button class="chip" id="p-all" aria-pressed="${PS.all}">Ver también las de otros medios</button></div>
      <section class="card" aria-live="polite">${data.promos.length ? data.promos.map(promoRow).join("") : `<div class="empty">No hay promos con estos filtros ese día.</div>`}</section>
      <section class="card"><h3>¿Viste una promo que no está?</h3><div class="sub">Sacale una foto al cartel, pegá el link o escribila. El bot la lee, la verifica y la suma para todos.</div>
        <button class="btn ghost" id="submit">Sumar una promo</button></section>`;
    bindCommon(main);
    $$("[data-day]", main).forEach(b => b.onclick = () => { PS.day = b.dataset.day; route(); });
    $$("[data-rubro]", main).forEach(b => b.onclick = () => { PS.rubro = b.dataset.rubro; route(); });
    $("#p-saved").onclick = () => { PS.saved = !PS.saved; route(); };
    $("#p-all").onclick = () => { PS.all = !PS.all; route(); };
    let t; $("#pq").oninput = e => { clearTimeout(t); t = setTimeout(() => { PS.q = e.target.value; route().then(() => { const i = $("#pq"); i.focus(); i.setSelectionRange(i.value.length, i.value.length); }); }, 350); };
    $("#submit").onclick = submitSheet;
  };

  async function promoSheet(id) {
    let p;
    try { p = await api(`/api/promos/${id}`); } catch (e) { return toast(e.message); }
    const trust = p.is_example ? `<span class="badge ex">promo de ejemplo</span>` : p.ok_count >= 3 ? `<span class="badge ok">✓ confirmada por ${p.ok_count} personas</span>`
      : p.fail_count >= 2 ? `<span class="badge warn">algunas personas dicen que no funcionó</span>` : `<span class="badge ex">${{ bot: "encontrada por el bot", comercio: "publicada por el comercio", admin: "verificada", usuario: "sumada por la comunidad" }[p.source] || ""}</span>`;
    sheet(`
      <div class="row"><span class="logo" style="background:${colorFor(p.name)}">${esc(initials(p.name))}</span><div class="grow"><h2>${esc(p.name)}</h2><div class="sub">${esc(rubro(p.rubro).name)}${p.address ? " · " + esc(p.address) : ""}</div></div><span class="pct" style="font-size:30px">${pctTxt(p.pct)}</span></div>
      <div class="row wrap">${payTag(p.method_id)} ${trust} ${p.exclusive ? '<span class="badge ok">exclusiva de tu empresa</span>' : ""}</div>
      <div class="split">
        <div class="r"><span class="sub">Días</span><b>${esc(daysTxt(p.days))}</b></div>
        ${p.cap_month ? `<div class="r"><span class="sub">Tope por mes</span><b class="num">${money(p.cap_month)}</b></div>
          <div class="r"><span class="sub">Te queda este mes</span><b class="num" style="color:var(--accent)">${money(p.cap_left ?? p.cap_month)}</b></div>` : `<div class="r"><span class="sub">Tope</span><b>${p.source === "bot" ? "No lo informa: mirá la página oficial" : "Sin tope"}</b></div>`}
        ${p.min_amount ? `<div class="r"><span class="sub">Compra mínima</span><b class="num">${money(p.min_amount)}</b></div>` : ""}
        ${p.valid_to ? `<div class="r"><span class="sub">Vence</span><b>${fdate(p.valid_to)}</b></div>` : ""}
      </div>
      ${p.conditions ? `<div class="fine">${esc(p.conditions)}</div>` : ""}
      ${p.source_url ? `<a class="fine" href="${esc(p.source_url)}" target="_blank" rel="noopener">Ver las condiciones completas en la página oficial ↗</a>` : ""}
      ${!p.mine ? `<div class="card near"><span class="sub">No tenés ${esc(p.method)} en tus medios de pago. Si lo tenés, agregalo en Perfil.</span></div>` : ""}
      <div class="grid2"><button class="btn" id="use">Usarla ahora</button><button class="btn ghost" id="save">${p.saved ? "★ Guardada" : "☆ Guardar"}</button></div>
      <div class="row between"><span class="sub">¿La usaste? ¿Te funcionó?</span><span class="row"><button class="btn ghost sm" data-fb="1">Sí</button><button class="btn ghost sm" data-fb="0">No</button></span></div>`,
      (bg, close) => {
        $("#save", bg).onclick = e => busy(e.currentTarget, async () => { const r = await api(`/api/promos/${id}/save`, { method: "POST" }); e.currentTarget.textContent = r.saved ? "★ Guardada" : "☆ Guardar"; });
        $("#use", bg).onclick = () => { close(); S.pay = { mode: "pagar", place: p.place_id ? { id: p.place_id, name: p.name, rubro: p.rubro } : { name: p.name, rubro: p.rubro } }; go("pagar"); };
        $$("[data-fb]", bg).forEach(b => b.onclick = () => busy(b, async () => {
          await api(`/api/promos/${id}/feedback`, { method: "POST", json: { ok: b.dataset.fb === "1" } });
          close(); toast(b.dataset.fb === "1" ? "¡Gracias! Así sabemos que la promo es real." : "Gracias. La revisamos y avisamos al resto si cambió.");
        }));
      });
  }

  function submitSheet() {
    sheet(`<h2>Sumar una promo</h2><div class="sub">Subí una foto del cartel o una captura, pegá el link, o escribila como la viste.</div>
      <label class="field" for="s-img">Foto o captura<input id="s-img" type="file" accept="image/*" capture="environment"></label>
      <label class="field" for="s-link">Link<input id="s-link" type="url" placeholder="https://"></label>
      <label class="field" for="s-text">O escribila<textarea id="s-text" placeholder="Ej: 20% en Panadería La Espiga los martes con MODO, tope $1.000"></textarea></label>
      <button class="btn full" id="s-go">Enviar al bot</button><div id="s-out"></div>`, (bg, close) => {
      $("#s-go", bg).onclick = e => busy(e.currentTarget, async () => {
        const fd = new FormData();
        const f = $("#s-img", bg).files[0];
        if (f) fd.append("image", f);
        fd.append("link", $("#s-link", bg).value); fd.append("text", $("#s-text", bg).value);
        $("#s-out", bg).innerHTML = `<div class="sub">El bot está leyendo la promo…</div>`;
        const r = await api("/api/promos/submit", { method: "POST", form: fd });
        $("#s-out", bg).innerHTML = r.promos.length
          ? `<div class="card" style="background:var(--surface-2)"><span class="label">Esto entendió el bot</span>${r.promos.map(p => `<div class="split">
              <div class="r"><span class="sub">Comercio</span><b>${esc(p.merchant || rubro(p.rubro).generic || "—")}</b></div>
              <div class="r"><span class="sub">Descuento</span><b>${pctTxt(p.pct)}</b></div>
              <div class="r"><span class="sub">Con</span><b>${esc(method(p.method_id).name)}</b></div>
              <div class="r"><span class="sub">Días</span><b>${esc(daysTxt(p.days.join("")))}</b></div>
              ${p.cap_month ? `<div class="r"><span class="sub">Tope</span><b>${money(p.cap_month)}</b></div>` : ""}</div>`).join("<hr>")}
              <div class="fine">La revisamos y, si está bien, aparece para todos.</div></div><button class="btn full" data-close>Listo</button>`
          : r.image_needs_review ? `<div class="card near"><span class="sub">Recibimos la foto. Una persona la va a leer y cargar. ¡Gracias!</span></div><button class="btn full" data-close>Listo</button>`
          : `<div class="card near"><span class="sub">No pudimos entender la promo. Escribila con el porcentaje, el comercio y con qué se paga.</span></div>`;
      });
    });
  }

  // ---------------------------------------------------------------- ANTES DE PAGAR / CARGAR GASTO
  VIEWS.pagar = async main => {
    const P = S.pay = { mode: "pagar", amount: "", method: null, options: null, ...S.pay };
    main.innerHTML = `
      <div class="hello"><small>Te decimos con qué te conviene pagar</small><h1>${P.mode === "gasto" ? "Cargar un gasto" : "Antes de pagar"}</h1></div>
      ${S.cat.ai ? `<label class="btn ghost" for="tk" style="cursor:pointer">${svg("camera", 18)} Completar con la foto del ticket<input type="file" id="tk" accept="image/*" capture="environment" hidden></label>` : ""}
      <section class="card">
        <label class="field" for="pl">¿Dónde?<input id="pl" autocomplete="off" placeholder="Comercio, local o lugar" value="${esc(P.place?.name || "")}"></label>
        <div id="sug"></div>
        <div id="rb-wrap" ${P.place?.id || !P.place?.name ? "hidden" : ""}><label class="field" for="rb">Rubro<select id="rb">${S.cat.rubros.map(r => `<option value="${r.id}" ${P.place?.rubro === r.id ? "selected" : ""}>${r.icon} ${esc(r.name)}</option>`).join("")}</select></label></div>
        <label class="field" for="amt">¿Cuánto vas a gastar?<input id="amt" class="amount" inputmode="numeric" placeholder="$ 0" value="${P.amount ? money(P.amount) : ""}"></label>
        <details><summary class="sub">Fue otro día</summary><label class="field" for="gday" style="margin-top:8px">Fecha<input id="gday" type="date" max="${todayIso()}" value="${P.day || todayIso()}"></label></details>
      </section>
      <section id="opts"></section>`;
    const pl = $("#pl"), amt = $("#amt");
    const loadOptions = async () => {
      if (!P.place?.name || !(P.amount > 0)) { $("#opts").innerHTML = ""; return; }
      const r = await api("/api/options", { method: "POST", json: { place_id: P.place.id, place_name: P.place.name, rubro: P.place.rubro, amount: P.amount } });
      P.options = r.options;
      if (!P.method || !r.options.some(o => o.method_id === P.method)) P.method = r.options[0]?.method_id;
      drawOptions();
    };
    const drawOptions = () => {
      const best = P.options[0];
      $("#opts").innerHTML = `<div class="card">
        <span class="label">${best.saving > 0 ? "Con qué te conviene pagar" : "¿Cómo vas a pagar?"}</span>
        ${best.saving > 0 ? `<div class="sub">Con <b>${esc(method(best.method_id).name)}</b> ahorrás <b class="num">${money(best.saving)}</b>.</div>` : `<div class="sub">No encontramos promos acá para tus medios de pago hoy. Igual cargalo: así aprendemos tus hábitos.</div>`}
        <div class="rank">${P.options.map((o, i) => `<button class="it ${i === 0 && o.saving > 0 ? "best" : ""}" data-pick="${o.method_id}" aria-pressed="${o.method_id === P.method}">
          ${payTag(o.method_id)}${o.is_example ? ' <span class="badge ex">ejemplo</span>' : ""}
          <span class="v">${o.saving > 0 ? `<b>${money(o.saving)}</b><span class="fine">${pctTxt(o.pct)}${o.capped ? " · llegás al tope" : o.cap_left != null ? ` · quedan ${money(o.cap_left - o.saving)}` : ""}</span>`
            : o.min_amount && o.pct ? `<span class="fine">${pctTxt(o.pct)} desde ${money(o.min_amount)}</span>` : `<span class="fine">sin promo</span>`}</span></button>`).join("")}</div>
        <button class="btn full dark" id="paid">Pagué con ${esc(method(P.method).name)}</button>
        ${best.conditions && best.saving > 0 ? `<div class="fine">${esc(best.conditions)}</div>` : ""}</div>`;
      $$("[data-pick]").forEach(b => b.onclick = () => { P.method = b.dataset.pick; drawOptions(); });
      $("#paid").onclick = e => busy(e.currentTarget, savePaid);
    };
    const savePaid = async () => {
      const r = await api("/api/gastos", { method: "POST", json: { place_id: P.place.id, place_name: P.place.name, rubro: P.place.rubro, method_id: P.method, amount: P.amount, day: $("#gday").value } });
      const used = r.promo_id;
      S.pay = {};
      sheet(`<div class="celebrate card" style="border:0;padding:0">
        <div class="medal" style="font-size:30px">${r.saved > 0 ? "✓" : "$"}</div>
        <h2>${r.saved > 0 ? `Ahorraste ${money(r.saved)}` : "Gasto anotado"}</h2>
        ${r.missed > 0 ? `<div class="sub">Con <b>${esc(r.best_method_name)}</b> hubieras ahorrado <b>${money(r.missed)}</b> más. La próxima te avisamos antes.</div>` : `<div class="sub">Llevás ${money(r.totals.saved_month)} ahorrados este mes.</div>`}</div>
        ${used ? `<div class="card" style="background:var(--surface-2)"><b>¿Te aplicaron el descuento?</b><div class="sub">Tu respuesta ayuda a que las promos sean siempre reales.</div>
          <div class="grid2"><button class="btn" data-fb="1">Sí, me funcionó</button><button class="btn ghost" data-fb="0">No me lo aplicaron</button></div></div>` : ""}
        <button class="btn full ${used ? "ghost" : ""}" data-close>Listo</button>`, (bg, close) => {
        $$("[data-fb]", bg).forEach(b => b.onclick = () => busy(b, async () => {
          await api(`/api/promos/${used}/feedback`, { method: "POST", json: { ok: b.dataset.fb === "1" } });
          close(); toast(b.dataset.fb === "1" ? "¡Gracias! Confirmaste la promo." : "Gracias. La vamos a revisar.");
        }));
      });
      go("inicio");
    };
    let t;
    pl.oninput = () => {
      P.place = { name: pl.value.trim(), rubro: $("#rb").value };
      clearTimeout(t);
      t = setTimeout(async () => {
        const q = pl.value.trim();
        if (!q) { $("#sug").innerHTML = ""; return; }
        const list = await api("/api/places?q=" + encodeURIComponent(q));
        const exact = list.some(x => x.name.toLowerCase() === q.toLowerCase());
        $("#sug").innerHTML = `<div class="suggest">${list.slice(0, 5).map(x => `<button data-pl="${x.id}"><span>${esc(x.name)}</span><span class="fine">${esc(rubro(x.rubro).name)}</span></button>`).join("")}
          ${exact ? "" : `<button data-new="1"><span>Usar «${esc(q)}»</span><span class="fine">lugar nuevo</span></button>`}</div>`;
        $$("[data-pl]").forEach(b => b.onclick = () => { const x = list.find(y => y.id == b.dataset.pl); P.place = { id: x.id, name: x.name, rubro: x.rubro }; pl.value = x.name; $("#sug").innerHTML = ""; $("#rb-wrap").hidden = true; loadOptions(); });
        $("[data-new]")?.addEventListener("click", () => { $("#sug").innerHTML = ""; $("#rb-wrap").hidden = false; $("#rb").value = guessRubro(q); P.place = { name: q, rubro: $("#rb").value }; loadOptions(); });
      }, 250);
    };
    $("#rb").onchange = () => { if (P.place) { P.place.rubro = $("#rb").value; loadOptions(); } };
    amt.oninput = () => {
      const v = +amt.value.replace(/\D/g, "");
      P.amount = v; amt.value = v ? money(v) : "";
      clearTimeout(t); t = setTimeout(loadOptions, 300);
    };
    $("#gday").onchange = e => { P.day = e.target.value; };
    $("#tk")?.addEventListener("change", e => {
      const f = e.target.files[0]; if (!f) return;
      const lbl = e.target.closest("label"); lbl.classList.add("loading");
      const fd = new FormData(); fd.append("image", f);
      toast("Leyendo el ticket…");
      api("/api/ticket", { method: "POST", form: fd }).then(t => {
        if (t.merchant) { P.place = { name: t.merchant, rubro: t.rubro || guessRubro(t.merchant) }; pl.value = t.merchant; $("#rb-wrap").hidden = false; $("#rb").value = P.place.rubro; }
        if (t.amount) { P.amount = Math.round(t.amount); amt.value = money(P.amount); }
        if (t.date) { P.day = t.date; $("#gday").value = t.date; $("details").open = t.date !== todayIso(); }
        if (t.method_id && S.me.methods.concat("efectivo").includes(t.method_id)) P.method = t.method_id;
        toast("Listo: revisá los datos antes de guardar.");
        loadOptions();
      }).catch(x => toast(x.message)).finally(() => { e.target.value = ""; lbl.classList.remove("loading"); });
    });
    if (P.place?.name && P.amount) loadOptions();
    (P.place?.name ? amt : pl).focus();
  };
  function guessRubro(name) {
    const n = name.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
    const r = S.cat.rubros.find(r => r.words.some(w => n.includes(w.normalize("NFD").replace(/[̀-ͯ]/g, ""))));
    return r ? r.id : "otros";
  }
  // ---------------------------------------------------------------- GASTOS
  let GM = null;
  VIEWS.gastos = async main => {
    GM = GM || todayIso().slice(0, 7);
    const [d, rec] = await Promise.all([api("/api/gastos?month=" + GM), api("/api/recurring")]);
    const [y, m] = GM.split("-").map(Number);
    const mn = new Date(y, m - 1, 1).toLocaleDateString("es-AR", { month: "long", year: "numeric" });
    const monthName = mn.charAt(0).toUpperCase() + mn.slice(1);
    const kinds = [["billetera", "Billeteras", "#0f9b8e"], ["banco", "Bancos", "#2c5fa8"], ["tarjeta", "Tarjetas", "#7a3fa0"], ["efectivo", "Efectivo", "#6b7d74"]];
    const maxS = Math.max(1, ...d.series.map(s => s.saved));
    const rub = Object.entries(d.by_rubro).sort((a, b) => b[1] - a[1]);
    main.innerHTML = `
      <div class="hello"><small>Todo lo que gastás, y lo que ahorrás</small><h1>Gastos</h1></div>
      <div class="row between"><button class="icon-btn" id="prev" aria-label="Mes anterior">${svg("back")}</button><b>${esc(monthName)}</b>
        <button class="icon-btn" id="next" aria-label="Mes siguiente" ${GM >= todayIso().slice(0, 7) ? "disabled" : ""} style="transform:scaleX(-1)">${svg("back")}</button></div>
      <div class="kpis"><div class="kpi"><b>${money(d.spent)}</b><small>gastaste</small></div><div class="kpi"><b style="color:var(--accent)">${money(d.saved)}</b><small>ahorraste</small></div>
        <div class="kpi"><b style="color:${d.missed ? "var(--crit)" : "inherit"}">${money(d.missed)}</b><small>te perdiste</small></div></div>
      ${d.missed > 0 ? `<div class="card near"><span class="sub">Pagando con el mejor medio en cada compra, este mes hubieras ahorrado <b>${money(d.missed)}</b> más. Usá «Antes de pagar» para no perderlo.</span></div>` : ""}
      <section class="card"><span class="label">Ahorro por mes</span>
        <div class="bars">${d.series.map(s => `<div><em>${s.saved >= 1000 ? (s.saved / 1000).toLocaleString("es-AR", { maximumFractionDigits: 1 }) + "k" : Math.round(s.saved)}</em><i style="height:${s.saved / maxS * 100}%"></i>
          <small>${new Date(s.month + "-15").toLocaleDateString("es-AR", { month: "short" })}</small></div>`).join("")}</div></section>
      ${d.spent ? `<section class="card"><span class="label">Cómo pagás</span>
        <div class="stack">${kinds.map(([k, , c]) => d.by_kind[k] ? `<i style="width:${d.by_kind[k] / d.spent * 100}%;background:${c}" title="${k}"></i>` : "").join("")}</div>
        <div class="legend">${kinds.filter(([k]) => d.by_kind[k]).map(([k, l, c]) => `<span><i style="background:${c}"></i>${l} <b class="num">${Math.round(d.by_kind[k] / d.spent * 100)}%</b></span>`).join("")}</div></section>
      <section class="card"><span class="label">En qué se te va</span><div class="split">${rub.map(([r, v]) => `<div class="r"><span>${rubro(r).icon} ${esc(rubro(r).name)}</span><span class="num">${money(v)}</span>
        <span class="track"><i style="width:${v / rub[0][1] * 100}%"></i></span></div>`).join("")}</div></section>` : ""}
      <section class="card"><div class="card-head"><h3>Gastos fijos</h3><button class="btn ghost sm" id="addr">+ Agregar</button></div>
        <div class="sub">Alquiler, servicios, suscripciones: se cargan solos el día que elijas, y te avisamos si hay una promo mejor.</div>
        ${rec.length ? rec.map(r => `<div class="list-row"><span class="swatch" style="background:${method(r.method_id).color}"></span>
          <div class="grow"><b style="display:block">${esc(r.place_name)}</b><span class="sub">Día ${r.day_of_month} de cada mes · ${esc(method(r.method_id).name)}</span></div>
          <div class="amt"><b class="num">${money(r.amount)}</b></div><button class="link" data-delr="${r.id}" aria-label="Borrar gasto fijo" style="color:var(--muted);padding:6px">✕</button></div>`).join("")
          : ""}</section>
      <section class="card"><div class="card-head"><span class="label">Movimientos</span><button class="btn ghost sm" id="addg">+ Cargar</button></div>
        ${d.gastos.length ? d.gastos.map(g => `<div class="list-row"><span class="swatch" style="background:${method(g.method_id).color}"></span>
          <div class="grow"><b style="display:block;overflow-wrap:anywhere">${esc(g.place_name)}</b><span class="sub">${fdate(g.day)} · ${esc(method(g.method_id).name)}</span></div>
          <div class="amt"><b class="num">${money(g.amount)}</b><div class="fine" style="color:${g.saved ? "var(--accent)" : g.missed ? "var(--crit)" : "var(--muted)"}">${g.saved ? "ahorraste " + money(g.saved) : g.missed ? "perdiste " + money(g.missed) : "sin descuento"}</div></div>
          <button class="link" data-del="${g.id}" aria-label="Borrar gasto" style="color:var(--muted);padding:6px">✕</button></div>`).join("")
          : `<div class="empty">No hay gastos este mes. Cargá el primero con el botón + de abajo.</div>`}</section>`;
    $("#prev").onclick = () => { GM = new Date(y, m - 2, 1).toISOString().slice(0, 7); route(); };
    $("#next").onclick = () => { GM = new Date(y, m, 1).toISOString().slice(0, 7); route(); };
    $("#addg").onclick = () => { S.pay = { mode: "gasto" }; go("pagar"); };
    $$("[data-delr]").forEach(b => b.onclick = () => busy(b, async () => { await api(`/api/recurring/${b.dataset.delr}`, { method: "DELETE" }); toast("Gasto fijo borrado"); route(); }));
    $("#addr").onclick = () => sheet(`<h2>Nuevo gasto fijo</h2>
      <label class="field" for="rc-name">¿Qué es?<input id="rc-name" placeholder="Ej: Alquiler, Internet, Netflix"></label>
      <div class="grid2"><label class="field" for="rc-amt">Monto<input id="rc-amt" class="amount" inputmode="numeric" placeholder="$ 0"></label>
        <label class="field" for="rc-day">Día del mes<select id="rc-day">${Array.from({ length: 31 }, (_, i) => `<option value="${i + 1}" ${i + 1 === 10 ? "selected" : ""}>${i + 1}</option>`).join("")}</select></label></div>
      <label class="field" for="rc-rubro">Rubro<select id="rc-rubro">${S.cat.rubros.map(r => `<option value="${r.id}" ${r.id === "servicios" ? "selected" : ""}>${r.icon} ${esc(r.name)}</option>`).join("")}</select></label>
      <label class="field" for="rc-m">Cómo lo pagás<select id="rc-m">${S.me.methods.concat("efectivo").map(m => `<option value="${m}">${esc(method(m).name)}</option>`).join("")}</select></label>
      <button class="btn full" id="rc-go">Guardar gasto fijo</button>`, (bg, close) => {
      $("#rc-amt", bg).oninput = e => { const v = +e.target.value.replace(/\D/g, ""); e.target.value = v ? money(v) : ""; };
      $("#rc-go", bg).onclick = e => busy(e.currentTarget, async () => {
        await api("/api/recurring", { method: "POST", json: { place_name: $("#rc-name", bg).value, amount: +$("#rc-amt", bg).value.replace(/\D/g, ""),
          day_of_month: +$("#rc-day", bg).value, rubro: $("#rc-rubro", bg).value, method_id: $("#rc-m", bg).value } });
        close(); toast("Listo: se va a cargar solo cada mes."); route();
      });
    });
    $$("[data-del]").forEach(b => b.onclick = () => sheet(`<h2>¿Borrar este gasto?</h2><div class="sub">También se resta lo que ahorraste con él.</div>
      <div class="grid2"><button class="btn ghost" data-close>Cancelar</button><button class="btn danger" id="del">Borrar</button></div>`, (bg, close) => {
      $("#del", bg).onclick = e => busy(e.currentTarget, async () => { await api(`/api/gastos/${b.dataset.del}`, { method: "DELETE" }); close(); toast("Gasto borrado"); route(); });
    }));
  };

  // ---------------------------------------------------------------- APRENDER
  VIEWS.aprender = async main => {
    const d = await api("/api/learn");
    const CS = { amount: Math.round(d.saved) || 10000, type: "pf", tna: d.rates.ref_tna_plazo_fijo, days: 30 };
    main.innerHTML = `
      <div class="hello"><small>Conceptos de plata explicados simple</small><h1>Aprender</h1></div>
      <div class="sub">Leíste ${d.read} de ${d.total} temas. Todo está disponible: empezá por el que te interese.</div>
      ${d.suggestions.length ? `<section class="card"><h3>Te puede interesar</h3>${d.suggestions.map(articleCard).join("")}</section>` : ""}
      <div class="chips" id="topic-nav">${d.topics.map(tp => `<button class="chip" data-topic="${tp.id}">${tp.icon} ${esc(tp.name)}</button>`).join("")}</div>
      ${d.topics.map(tp => `<section class="card" id="t-${tp.id}"><div><h3>${tp.icon} ${esc(tp.name)}</h3><div class="sub">${esc(tp.desc)}</div></div>
        ${tp.articles.map(articleCard).join("")}</section>`).join("")}
      <section class="card"><h3>¿Cuánto ganarías?</h3>
        <div class="seg" role="group"><button data-ct="pf" aria-pressed="true">Plazo fijo</button><button data-ct="rem" aria-pressed="false">Cuenta remunerada</button></div>
        <div class="grid2">
          <label class="field" for="c-amt">Monto<input id="c-amt" inputmode="numeric" value="${money(CS.amount)}"></label>
          <label class="field" for="c-days">Plazo<select id="c-days">${[30, 60, 90, 180, 365].map(x => `<option value="${x}">${x} días</option>`).join("")}</select></label>
          <label class="field full" for="c-tna">TNA (%)<input id="c-tna" inputmode="decimal" value="${CS.tna}"></label></div>
        <div class="result"><span class="sub">Ganarías aprox.</span><b id="c-res"></b></div>
        <div class="fine" id="c-note"></div></section>
      <section class="card"><div class="card-head"><h3>Mis objetivos</h3><button class="btn ghost sm" id="addgoal">+ Nuevo</button></div>
        ${d.goals.length ? d.goals.map(g => `<div><div class="row between"><b>${esc(g.name)}</b><span class="sub num">${money(Math.min(d.saved, g.target))} / ${money(g.target)}</span></div>
          <div class="bar light" style="margin:6px 0"><i style="width:${Math.min(100, d.saved / g.target * 100)}%"></i></div>
          <div class="row between"><span class="fine">${d.saved >= g.target ? "¡Lo lograste!" : `Te faltan ${money(g.target - d.saved)}`}</span><button class="link" data-delgoal="${g.id}" style="color:var(--muted);font-size:13px">Borrar</button></div></div>`).join("")
          : `<div class="sub">Ponete una meta (unas vacaciones, un fondo de emergencia) y mirá cómo tu ahorro se acerca.</div>`}</section>
      <section class="card"><h3>Glosario</h3>${d.glossary.map(([t, x]) => `<details><summary><b>${esc(t)}</b></summary><div class="sub" style="padding:6px 0">${esc(x)}</div></details>`).join("")}</section>
      <p class="fine">Tu Bolsillo enseña conceptos generales y no recomienda productos ni inversiones. Antes de invertir, informate y verificá que la entidad esté registrada en la CNV.</p>`;
    bindCommon(main);
    $$("[data-topic]", main).forEach(b => b.onclick = () => $("#t-" + b.dataset.topic).scrollIntoView({ behavior: "smooth", block: "start" }));
    const calc = () => {
      CS.amount = +$("#c-amt").value.replace(/\D/g, "") || 0; CS.days = +$("#c-days").value; CS.tna = parseFloat($("#c-tna").value.replace(",", ".")) || 0;
      const simple = CS.amount * CS.tna / 100 / 365 * CS.days;
      const comp = CS.type === "rem" ? CS.amount * (Math.pow(1 + CS.tna / 100 / 365, CS.days) - 1) : simple;
      $("#c-res").textContent = money(CS.type === "rem" ? comp : simple);
      $("#c-note").textContent = `Cálculo para aprender, con ${CS.type === "rem" ? "interés diario reinvertido" : "interés simple al vencimiento"}. TNA de referencia${d.rates.fecha ? " del " + fdate(d.rates.fecha) : ""}: la tasa real la ves en tu banco o billetera.`;
    };
    $("#c-amt").oninput = e => { const v = +e.target.value.replace(/\D/g, ""); e.target.value = v ? money(v) : ""; calc(); };
    $("#c-days").onchange = calc; $("#c-tna").oninput = calc;
    $$("[data-ct]").forEach(b => b.onclick = () => {
      CS.type = b.dataset.ct; $$("[data-ct]").forEach(x => x.setAttribute("aria-pressed", String(x === b)));
      $("#c-tna").value = CS.type === "rem" ? d.rates.ref_tna_remunerada : d.rates.ref_tna_plazo_fijo; calc();
    });
    calc();
    $("#addgoal").onclick = () => sheet(`<h2>Nuevo objetivo</h2>
      <label class="field" for="g-name">¿Para qué ahorrás?<input id="g-name" placeholder="Ej: Vacaciones, fondo de emergencia"></label>
      <label class="field" for="g-target">¿Cuánto necesitás?<input id="g-target" class="amount" inputmode="numeric" placeholder="$ 0"></label>
      <button class="btn full" id="g-ok">Guardar objetivo</button>`, (bg, close) => {
      $("#g-target", bg).oninput = e => { const v = +e.target.value.replace(/\D/g, ""); e.target.value = v ? money(v) : ""; };
      $("#g-ok", bg).onclick = e => busy(e.currentTarget, async () => {
        await api("/api/goals", { method: "POST", json: { name: $("#g-name", bg).value, target: +$("#g-target", bg).value.replace(/\D/g, "") } });
        close(); route();
      });
    });
    $$("[data-delgoal]").forEach(b => b.onclick = () => busy(b, async () => { await api(`/api/goals/${b.dataset.delgoal}`, { method: "DELETE" }); route(); }));
  };

  const articleCard = a => `<button class="article" data-lesson="${a.id}"><span class="row between"><b>${esc(a.title)}</b><span class="${a.read ? "ok" : "fine"}" style="white-space:nowrap">${a.read ? "✓ leído" : a.min + " min"}</span></span><span class="sub">${esc(a.summary)}</span></button>`;

  async function lessonSheet(id) {
    let x;
    try { x = await api(`/api/lessons/${id}`); } catch (e) { return toast(e.message); }
    const ex = x.example;
    const { bg, close } = sheet(`<span class="label">${esc(x.topic_name)} · ${x.min} min de lectura</span><h2>${esc(x.title)}</h2>
      <p class="lead-in">${esc(x.summary)}</p>
      ${x.sections.map(sc => `<section class="read"><h3>${esc(sc.h)}</h3>${sc.p.map(p => `<p>${esc(p)}</p>`).join("")}</section>`).join("")}
      ${ex ? `<div class="example"><span class="label">${esc(ex.title)}</span>${ex.rows.map(([k, v]) => `<div class="row between"><span class="sub">${esc(k)}</span><b class="num">${esc(v)}</b></div>`).join("")}${ex.note ? `<div class="fine">${esc(ex.note)}</div>` : ""}</div>` : ""}
      ${x.related.length ? `<div><span class="label">Seguí con</span><div class="chips wrap" style="margin-top:8px">${x.related.map(r => `<button class="chip" data-rel="${r.id}">${esc(r.title)}</button>`).join("")}</div></div>` : ""}
      <p class="fine">Información general para aprender, no es una recomendación de inversión. Antes de invertir, verificá que la entidad esté registrada en la CNV.</p>
      <button class="btn full" data-close>Listo</button>`, (bg2, close2) => {
      $$("[data-rel]", bg2).forEach(b => b.onclick = () => { close2(); lessonSheet(b.dataset.rel); });
    });
    bg.addEventListener("click", e => { if ((e.target === bg || e.target.closest("[data-close]")) && location.hash.slice(1) === "aprender") route(); });
  }

  // ---------------------------------------------------------------- AVISOS
  VIEWS.avisos = async main => {
    const d = await api("/api/notifications");
    main.innerHTML = `
      <div class="hello"><small>Lo que te avisamos</small><h1>Avisos</h1></div>
      ${d.preview ? `<section class="card near"><span class="label">El aviso de esta noche</span><b>${esc(d.preview.title)}</b><span class="sub">${esc(d.preview.body)}</span></section>` : ""}
      <section class="card">${d.items.length ? d.items.map(n => `<button class="list-row" data-url="${esc(n.url || "")}" style="border-left:0;border-right:0;border-bottom:0;background:none;text-align:left;width:100%">
        <span class="swatch" style="background:${n.read ? "var(--line)" : "var(--accent)"};width:10px;height:10px;border-radius:50%"></span>
        <div class="grow"><b style="display:block">${esc(n.title)}</b><span class="sub">${esc(n.body)}</span><div class="fine">${esc(n.created_at.slice(0, 16).replace("T", " "))}</div></div></button>`).join("")
        : `<div class="empty">Todavía no hay avisos.</div>`}</section>
      ${S.me.push_devices ? "" : `<section class="card"><h3>Recibilos en el celular</h3><div class="sub">Activá las notificaciones para que te lleguen aunque no tengas la app abierta.</div><button class="btn" id="en-push">Activar notificaciones</button></section>`}`;
    $$("[data-url]", main).forEach(b => b.onclick = () => { const u = b.dataset.url; if (u.startsWith("#")) location.hash = u; });
    $("#en-push")?.addEventListener("click", e => busy(e.currentTarget, async () => { await enablePush(); toast("Listo: te van a llegar los avisos."); route(); }));
    if (S.me.unread) { await api("/api/notifications/read", { method: "POST" }); setUnread(0); }
  };

  async function enablePush() {
    if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window))
      throw new Error(isIos() ? "En iPhone, primero instalá la app: Compartir → Agregar a inicio. Después activá los avisos desde ahí." : "Este navegador no permite notificaciones.");
    const perm = await Notification.requestPermission();
    if (perm !== "granted") throw new Error("No diste permiso para las notificaciones. Lo podés cambiar en la configuración del navegador.");
    const reg = await navigator.serviceWorker.ready;
    const key = Uint8Array.from(atob(S.me.vapid.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - S.me.vapid.length % 4) % 4)), c => c.charCodeAt(0));
    const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key });
    await api("/api/push/subscribe", { method: "POST", json: { subscription: sub.toJSON() } });
    await refreshMe();
  }
  async function disablePush() {
    const reg = await navigator.serviceWorker?.ready;
    const sub = await reg?.pushManager.getSubscription();
    if (sub) { await api("/api/push/unsubscribe", { method: "POST", json: { endpoint: sub.endpoint } }); await sub.unsubscribe(); }
    await refreshMe();
  }

  // ---------------------------------------------------------------- PERFIL
  VIEWS.perfil = async main => {
    await refreshMe();
    const u = S.me.user, chosen = new Set(S.me.methods);
    const isUser = u.role === "user";
    const home = isUser ? await api("/api/home") : null;
    main.innerHTML = `
      <div class="hello"><small>${esc(u.email)}</small><h1>${esc(u.name)}</h1></div>
      ${!isUser ? `<button class="btn dark" data-go="${u.role}">Ir al panel de ${{ comercio: "comercio", empresa: "empresa", admin: "administración" }[u.role]}</button>` : ""}
      ${isUser ? `<section class="card"><div class="card-head"><h3>Mis medios de pago</h3><span class="fine">${chosen.size} elegidos + efectivo</span></div>
        <div id="ms"></div><button class="btn" id="save-ms">Guardar medios de pago</button></section>
      <section class="card"><div class="row"><div class="grow"><b>Personalizar con mis gastos</b><div class="sub">La app aprende tus hábitos para ordenar promos y avisos.</div></div>
        <button class="switch" role="switch" id="personal" aria-checked="${!!u.personal}" aria-label="Personalizar con mis gastos"></button></div>
        ${u.personal && home.insights.length ? `<span class="label">Lo que aprendimos de vos</span><div class="chips wrap">${home.insights.map(i => `<span class="chip">${esc(i.tag)}</span>`).join("")}</div>
          <div class="fine">Se calcula con tus gastos de los últimos 90 días. Si borrás un gasto, deja de contar.</div>` : ""}</section>` : ""}
      <section class="card"><h3>Avisos</h3>
        <div class="row"><div class="grow"><b>Notificaciones en este dispositivo</b><div class="sub">${S.me.push_devices ? `Activas en ${S.me.push_devices} dispositivo${S.me.push_devices > 1 ? "s" : ""}` : "Desactivadas"}</div></div>
          <button class="switch" role="switch" id="push" aria-checked="${!!S.me.push_devices}" aria-label="Notificaciones"></button></div>
        ${isUser ? `<label class="field" for="hour">Aviso diario de promos<select id="hour">${Array.from({ length: 24 }, (_, h) => `<option value="${h}" ${h === u.notify_hour ? "selected" : ""}>${h}:00</option>`).join("")}</select></label>
        <div class="row"><div class="grow"><b>Avisos por cercanía</b><div class="sub">Cuando abrís la app cerca de un comercio con promo.</div></div>
          <button class="switch" role="switch" id="geo" aria-checked="${store.get("tb_geo") === "1"}" aria-label="Avisos por cercanía"></button></div>` : ""}
        ${S.me.push_devices ? `<button class="btn ghost sm" id="test">Mandarme un aviso de prueba</button>` : ""}</section>
      ${isUser ? `<section class="card"><h3>Beneficio de tu empresa</h3>${S.me.org ? `<div class="sub">Sos parte de <b>${esc(S.me.org.name)}</b>: tenés promos exclusivas.</div>`
        : `<div class="sub">Si tu empresa te dio un código, ingresalo para ver tus promos exclusivas.</div><div class="row"><input class="input grow" id="code" placeholder="Código" aria-label="Código de empresa"><button class="btn" id="join">Unirme</button></div>`}</section>` : ""}
      ${installCard()}
      <section class="card"><h3>Tus datos</h3><div class="sub">Tu Bolsillo no te pide claves bancarias ni números de tarjeta: alcanza con saber qué medios usás. No vendemos datos de personas.</div>
        <div class="grid2"><a class="btn ghost sm" href="/api/me/export" download>Descargar mis datos</a><button class="btn danger sm" id="delacc">Borrar mi cuenta</button></div>
        <div class="row wrap"><button class="link" data-legal="terminos">Términos de uso</button><span class="fine">·</span><button class="link" data-legal="privacidad">Política de privacidad</button></div></section>
      ${isUser ? `<button class="btn ghost" id="fb-profile">💬 Contanos qué mejorar</button>` : ""}
      <button class="btn ghost" id="logout">Cerrar sesión</button>
      <p class="fine" style="text-align:center">Tu Bolsillo · versión de prueba${S.me.demo_account ? " · cuenta de ejemplo" : ""}</p>`;
    bindCommon(main);
    if (isUser) {
      const draw = () => { $("#ms").innerHTML = methodPicker(chosen); bindPicker($("#ms"), chosen); };
      draw();
      $("#save-ms").onclick = e => busy(e.currentTarget, async () => { await api("/api/me", { method: "PUT", json: { methods: [...chosen] } }); toast("Guardado: vas a ver las promos de tus medios."); });
      $("#personal").onclick = e => busy(e.currentTarget, async () => { await api("/api/me", { method: "PUT", json: { personal: !u.personal } }); route(); });
      $("#hour").onchange = e => api("/api/me", { method: "PUT", json: { notify_hour: +e.target.value } }).then(() => toast(`Te avisamos a las ${e.target.value}:00`)).catch(x => toast(x.message));
      $("#geo").onclick = e => busy(e.currentTarget, async () => {
        if (store.get("tb_geo") === "1") { store.set("tb_geo", "0"); } else { await askGeo(); }
        e.currentTarget.setAttribute("aria-checked", String(store.get("tb_geo") === "1"));
      });
      $("#join")?.addEventListener("click", e => busy(e.currentTarget, async () => { const r = await api("/api/me/join", { method: "POST", json: { code: $("#code").value } }); toast(`¡Listo! Ahora sos parte de ${r.org}.`); route(); }));
    }
    $$("[data-legal]", main).forEach(b => b.onclick = () => legalSheet(b.dataset.legal));
    $("#fb-profile")?.addEventListener("click", feedbackSheet);
    $("#push").onclick = e => busy(e.currentTarget, async () => { S.me.push_devices ? await disablePush() : await enablePush(); route(); });
    $("#test")?.addEventListener("click", e => busy(e.currentTarget, async () => { const r = await api("/api/push/test", { method: "POST" }); toast(r.sent ? "Aviso enviado: mirá tu celular." : "No se pudo enviar. Probá desactivar y activar de nuevo."); }));
    bindInstall(main);
    $("#logout").onclick = () => busy($("#logout"), async () => { await api("/api/logout", { method: "POST" }); S.me = await api("/api/me"); location.hash = ""; renderAuth(); });
    $("#delacc").onclick = () => sheet(`<h2>¿Borrar tu cuenta?</h2><div class="sub">Se borran tus gastos, objetivos y avisos. No se puede deshacer.</div>
      <label class="field" for="dpass">Tu contraseña<input id="dpass" type="password" autocomplete="current-password"></label>
      <div class="grid2"><button class="btn ghost" data-close>Cancelar</button><button class="btn danger" id="dok">Borrar todo</button></div>`, (bg) => {
      $("#dok", bg).onclick = e => busy(e.currentTarget, async () => { await api("/api/me", { method: "DELETE", json: { password: $("#dpass", bg).value } }); location.hash = ""; location.reload(); });
    });
  };

  // ---------------------------------------------------------------- formulario de promo (comercio y empresa)
  function promoForm(prefix, extra = "") {
    return `${extra}
      <label class="field" for="${prefix}-m">Medio de pago<select id="${prefix}-m">${S.cat.methods.map(m => `<option value="${m.id}">${esc(m.name)}</option>`).join("")}</select></label>
      <div class="grid2"><label class="field" for="${prefix}-pct">Descuento (%)<input id="${prefix}-pct" inputmode="decimal" value="15"></label>
        <label class="field" for="${prefix}-cap">Tope por mes ($)<input id="${prefix}-cap" inputmode="numeric" placeholder="Sin tope"></label></div>
      <div class="field">Días<div class="chips wrap" id="${prefix}-days">${S.cat.days_short.map((d, i) => `<button type="button" class="chip" data-d="${i}" aria-pressed="false">${d}</button>`).join("")}</div></div>
      <div class="grid2"><label class="field" for="${prefix}-min">Compra mínima ($)<input id="${prefix}-min" inputmode="numeric" placeholder="Opcional"></label>
        <label class="field" for="${prefix}-vt">Vence<input id="${prefix}-vt" type="date" min="${todayIso()}"></label></div>
      <label class="field" for="${prefix}-cond">Condiciones<input id="${prefix}-cond" placeholder="Ej: pagando con QR, en una cuota"></label>`;
  }
  function bindPromoForm(el, prefix) {
    $$(`#${prefix}-days [data-d]`, el).forEach(b => b.onclick = () => b.setAttribute("aria-pressed", String(b.getAttribute("aria-pressed") !== "true")));
  }
  function readPromoForm(el, prefix) {
    const n = id => $(`#${prefix}-${id}`, el).value.replace(/\D/g, "");
    return { method_id: $(`#${prefix}-m`, el).value, pct: $(`#${prefix}-pct`, el).value.replace(",", "."), cap_month: n("cap") || null, min_amount: n("min") || null,
      days: $$(`#${prefix}-days [aria-pressed=true]`, el).map(b => +b.dataset.d), valid_to: $(`#${prefix}-vt`, el).value || null, conditions: $(`#${prefix}-cond`, el).value };
  }
  const funnel = s => { const top = Math.max(1, s.view || 0); return `<div class="funnel">${[["Vieron", s.view], ["Guardaron", s.save], ["Compraron", s.use]].map(([l, v]) =>
    `<div class="f"><span>${l}</span><i style="width:${(v || 0) / top * 100}%"></i><span class="num">${(v || 0).toLocaleString("es-AR")}</span></div>`).join("")}</div>`; };

  // ---------------------------------------------------------------- PANEL COMERCIO
  VIEWS.comercio = async main => {
    const d = await api("/api/org/comercio");
    main.innerHTML = `
      <div class="hello"><small>Panel para comercios</small><h1>${esc(d.org || "Tu comercio")}</h1></div>
      <div class="sub">Tus promos en Tu Bolsillo y cómo les va. Solo ves totales: nunca datos de personas.</div>
      <div class="kpis"><div class="kpi"><b>${(d.totals.view || 0).toLocaleString("es-AR")}</b><small>vieron tus promos</small></div><div class="kpi"><b>${(d.totals.save || 0).toLocaleString("es-AR")}</b><small>las guardaron</small></div><div class="kpi"><b>${(d.totals.use || 0).toLocaleString("es-AR")}</b><small>compraron con ellas</small></div></div>
      <section class="card"><span class="label">De verla a usarla · últimos 30 días</span>${funnel(d.totals)}</section>
      <section class="card"><h3>Tus promos</h3>${d.promos.length ? `<div class="scroll-x"><table class="table"><thead><tr><th>Promo</th><th>Días</th><th style="text-align:right">Usos</th><th></th></tr></thead><tbody>
        ${d.promos.map(p => `<tr><td><b>${pctTxt(p.pct)}</b> con ${esc(p.method)}<div class="fine">${esc(p.name)}</div></td><td>${esc(daysTxt(p.days))}</td><td class="n">${p.stats.use}</td>
          <td>${p.status === "publicada" ? `<button class="btn ghost sm" data-end="${p.id}">Terminar</button>` : `<span class="badge ex">${esc(p.status)}</span>`}</td></tr>`).join("")}</tbody></table></div>`
        : `<div class="empty">Todavía no publicaste promos.</div>`}</section>
      <section class="card" id="pf"><h3>Publicar una promo</h3>${d.places.length ? promoForm("cp", `<label class="field" for="cp-place">Local<select id="cp-place">${d.places.map(p => `<option value="${p.id}">${esc(p.name)}</option>`).join("")}</select></label>`)
        + `<button class="btn full" id="cp-go">Publicar promo</button><div class="fine">Se publica al instante. Les avisamos a las personas que suelen comprar en tu rubro.</div>` : `<div class="sub">Primero agregá tu local.</div>`}</section>
      <section class="card"><h3>Agregar un local</h3>
        <label class="field" for="lp-name">Nombre<input id="lp-name"></label>
        <label class="field" for="lp-rubro">Rubro<select id="lp-rubro">${S.cat.rubros.map(r => `<option value="${r.id}">${esc(r.name)}</option>`).join("")}</select></label>
        <label class="field" for="lp-addr">Dirección<input id="lp-addr"></label>
        <button class="btn ghost" id="lp-loc">Usar mi ubicación actual</button><span class="fine" id="lp-coords"></span>
        <button class="btn" id="lp-go">Agregar local</button></section>`;
    bindCommon(main);
    if (d.places.length) {
      bindPromoForm(main, "cp");
      $("#cp-go").onclick = e => busy(e.currentTarget, async () => { await api("/api/org/comercio/promos", { method: "POST", json: { ...readPromoForm(main, "cp"), place_id: $("#cp-place").value } }); toast("Promo publicada"); route(); });
    }
    $$("[data-end]").forEach(b => b.onclick = () => busy(b, async () => { await api(`/api/org/comercio/promos/${b.dataset.end}/end`, { method: "POST" }); toast("Promo terminada"); route(); }));
    let coords = {};
    $("#lp-loc").onclick = () => navigator.geolocation?.getCurrentPosition(p => { coords = { lat: p.coords.latitude, lng: p.coords.longitude }; $("#lp-coords").textContent = "Ubicación tomada ✓"; }, () => toast("No se pudo tomar la ubicación"));
    $("#lp-go").onclick = e => busy(e.currentTarget, async () => { await api("/api/org/comercio/places", { method: "POST", json: { name: $("#lp-name").value, rubro: $("#lp-rubro").value, address: $("#lp-addr").value, ...coords } }); toast("Local agregado"); route(); });
  };

  // ---------------------------------------------------------------- PANEL EMPRESA
  VIEWS.empresa = async main => {
    const d = await api("/api/org/empresa");
    main.innerHTML = `
      <div class="hello"><small>Beneficio de bienestar financiero</small><h1>${esc(d.org)}</h1></div>
      <section class="card"><span class="label">Código para tus empleados</span>
        <div class="row between"><b class="num" style="font-size:24px">${esc(d.code || "—")}</b><span class="row"><button class="btn ghost sm" id="copy">Copiar</button><button class="btn ghost sm" id="regen">Cambiar</button></span></div>
        <div class="fine">Cada persona lo ingresa en Perfil → Beneficio de tu empresa.</div></section>
      ${d.visible ? `<div class="kpis"><div class="kpi"><b>${d.members}</b><small>personas sumadas</small></div><div class="kpi"><b>${d.active_month}</b><small>activas este mes</small></div><div class="kpi"><b>${d.articles_read}</b><small>temas leídos</small></div></div>
        <section class="card"><span class="label">Ahorro de tu equipo</span><div class="row between"><span class="sub">Este mes</span><b class="num">${money(d.saved_month)}</b></div><div class="row between"><span class="sub">Desde que empezaron</span><b class="num">${money(d.saved_total)}</b></div>
        <div class="fine">Son totales del grupo. Nunca mostramos datos de una persona.</div></section>`
        : `<section class="card"><div class="sub">Hay ${d.members} persona${d.members === 1 ? "" : "s"} sumada${d.members === 1 ? "" : "s"}. Los totales aparecen cuando sean al menos ${d.min_group}, para que nadie sea identificable.</div></section>`}
      <section class="card"><h3>Promos exclusivas para tu equipo</h3>${d.promos.length ? d.promos.map(p => `<div class="list-row"><div class="grow"><b>${pctTxt(p.pct)} en ${esc(p.name)}</b><div class="sub">${esc(p.method)} · ${esc(daysTxt(p.days))}</div></div><span class="badge ${p.status === "publicada" ? "ok" : "ex"}">${esc(p.status)}</span></div>`).join("")
        : `<div class="empty">Todavía no hay promos exclusivas.</div>`}</section>
      <section class="card"><h3>Sumar una promo exclusiva</h3>${promoForm("ep", `<label class="field" for="ep-place">Comercio<select id="ep-place"><option value="">Todo un rubro</option>${d.places.map(p => `<option value="${p.id}">${esc(p.name)}</option>`).join("")}</select></label>
        <label class="field" for="ep-rubro">Rubro (si es para todo el rubro)<select id="ep-rubro">${S.cat.rubros.map(r => `<option value="${r.id}">${esc(r.name)}</option>`).join("")}</select></label>`)}
        <button class="btn full" id="ep-go">Publicar para mi equipo</button></section>`;
    bindPromoForm(main, "ep");
    $("#copy").onclick = () => navigator.clipboard?.writeText(d.code).then(() => toast("Código copiado"), () => toast("Copialo a mano: " + d.code));
    $("#regen").onclick = e => busy(e.currentTarget, async () => { await api("/api/org/empresa/code", { method: "POST" }); toast("Código nuevo creado. El anterior ya no sirve."); route(); });
    $("#ep-go").onclick = e => busy(e.currentTarget, async () => {
      await api("/api/org/empresa/promos", { method: "POST", json: { ...readPromoForm(main, "ep"), place_id: $("#ep-place").value || null, rubro: $("#ep-rubro").value } });
      toast("Promo publicada para tu equipo"); route();
    });
  };

  // ---------------------------------------------------------------- PANEL ADMINISTRACIÓN
  VIEWS.admin = async main => {
    S.adminSrc = S.adminSrc || "";
    const [d, mt] = await Promise.all([api("/api/admin" + (S.adminSrc ? "?source=" + S.adminSrc : "")), api("/api/admin/metrics")]);
    const st = d.stats;
    const maxW = Math.max(1, ...mt.weeks.map(w => w.active));
    const top = Math.max(1, mt.funnel[0].n);
    main.innerHTML = `
      <div class="hello"><small>Administración</small><h1>Tu Bolsillo</h1></div>
      <div class="kpis"><div class="kpi"><b>${st.usuarios}</b><small>usuarios</small></div><div class="kpi"><b>${st.promos_publicadas}</b><small>promos publicadas</small></div><div class="kpi"><b>${st.en_revision}</b><small>para revisar</small></div>
        <div class="kpi"><b>${st.gastos_mes}</b><small>gastos este mes</small></div><div class="kpi"><b>${money(st.ahorro_total)}</b><small>ahorrado en total</small></div><div class="kpi"><b>${st.dispositivos_push}</b><small>celulares con avisos</small></div></div>
      <section class="card"><h3>¿La usan y vuelven?</h3>
        <div class="kpis"><div class="kpi"><b>${mt.active_7d}</b><small>activos esta semana</small></div><div class="kpi"><b>${mt.new_7d}</b><small>nuevos en 7 días</small></div>
          <div class="kpi"><b>${mt.retention.pct == null ? "—" : mt.retention.pct + "%"}</b><small>volvieron la semana siguiente</small></div></div>
        <span class="label">Personas activas por semana</span>
        <div class="bars" style="grid-template-columns:repeat(8,1fr)">${mt.weeks.map(w => `<div><em>${w.active}</em><i style="height:${w.active / maxW * 100}%"></i><small>${fdate(w.week)}</small></div>`).join("")}</div>
        <span class="label">De registrarse a usarla seguido</span>
        <div class="funnel">${mt.funnel.map(f => `<div class="f" style="grid-template-columns:150px 1fr 40px"><span class="fine">${esc(f.step)}</span><i style="width:${f.n / top * 100}%"></i><span class="num">${f.n}</span></div>`).join("")}</div></section>
      <section class="card"><div class="card-head"><h3>Comentarios de la gente</h3>${mt.feedback_new ? `<span class="badge warn">${mt.feedback_new} nuevos</span>` : ""}</div>
        ${mt.feedback.length ? mt.feedback.map(f => `<div class="queue-item" style="${f.status === "visto" ? "opacity:.65" : ""}"><div class="row between"><span class="badge ${f.kind === "problema" ? "warn" : "ok"}">${{ idea: "idea", problema: "problema", otro: "comentario" }[f.kind]}</span><span class="fine">${esc((f.created_at || "").slice(0, 16))}</span></div>
          <div>${esc(f.text)}</div><div class="fine">${esc(f.user_name || "Cuenta borrada")}${f.user_email ? " · " + esc(f.user_email) : ""}${f.screen ? " · en " + esc(f.screen) : ""}</div>
          ${f.status === "nuevo" ? `<button class="btn ghost sm" data-seen="${f.id}">Marcar como visto</button>` : ""}</div>`).join("") : `<div class="empty">Todavía no hay comentarios.</div>`}</section>
      <section class="card"><h3>Recuperar la contraseña de alguien</h3>
        <div class="sub">${S.cat.mail ? "Las personas pueden recuperarla solas por mail. Si no les llega, generá el link acá." : "El envío de mails no está configurado: generá el link acá y mandáselo a la persona (por ejemplo, por WhatsApp)."}</div>
        <div class="row"><input class="input grow" id="rl-email" type="email" placeholder="Mail de la cuenta" aria-label="Mail de la cuenta"><button class="btn" id="rl-go">Generar link</button></div><div id="rl-out"></div></section>
      <section class="card"><div class="card-head"><h3>Bot de promos</h3><button class="btn sm" id="runbot">Correr ahora</button></div>
        <div class="sub">Entiende las promos con ${d.ai ? "<b>IA (Claude)</b> y reglas" : "<b>reglas</b>. Para que entienda textos difíciles y fotos de carteles, configurá la clave de la API de Anthropic (ver LEEME)"}.</div>
        ${d.runs.length ? `<div class="scroll-x"><table class="table"><thead><tr><th>Cuándo</th><th style="text-align:right">Encontró</th><th style="text-align:right">Nuevas</th><th style="text-align:right">A revisar</th></tr></thead><tbody>
          ${d.runs.map(r => `<tr><td>${esc(r.started.replace("T", " ").slice(0, 16))}<div class="fine">${esc(r.extractor || "")}${r.errors && r.errors !== "[]" ? " · con errores" : ""}</div></td><td class="n">${r.found}</td><td class="n">${r.new}</td><td class="n">${r.queued}</td></tr>`).join("")}</tbody></table></div>` : ""}</section>
      <section class="card"><h3>Para revisar (${d.queue.length})</h3>
        <label class="field" for="q-src">Ver las de<select id="q-src"><option value="">Todas las fuentes</option>${d.sources.filter(x => x.pending || String(x.id) === S.adminSrc).map(x => `<option value="${x.id}" ${String(x.id) === S.adminSrc ? "selected" : ""}>${esc(x.name)} (${x.pending})</option>`).join("")}</select></label>
        ${d.queue.length ? d.queue.map(p => `<div class="queue-item" data-q="${p.id}">
        <div class="row between"><b>${esc(p.name)}</b><span class="row">${p.fail_count ? `<span class="badge warn">${p.fail_count} quejas</span>` : ""}<span class="badge ex">${esc(p.source_name || p.source)}</span></span></div>
        ${p.source_url ? `<a class="fine" href="${esc(p.source_url)}" target="_blank" rel="noopener">Ver la página original ↗</a>` : ""}
        ${p.raw_text ? `<div class="raw">${esc(p.raw_text)}</div>` : ""}
        <div class="grid2"><label class="field">Comercio<input data-f="merchant" value="${esc(p.name)}"></label><label class="field">Medio<select data-f="method_id">${S.cat.methods.map(m => `<option value="${m.id}" ${m.id === p.method_id ? "selected" : ""}>${esc(m.name)}</option>`).join("")}</select></label>
          <label class="field">%<input data-f="pct" inputmode="decimal" value="${p.pct || ""}"></label><label class="field">Tope<input data-f="cap_month" inputmode="numeric" value="${p.cap_month || ""}"></label></div>
        <div class="chips wrap">${S.cat.days_short.map((x, i) => `<button type="button" class="chip" data-d="${i}" aria-pressed="${String(p.days).includes(String(i))}">${x}</button>`).join("")}</div>
        <div class="grid2"><button class="btn sm" data-ap="${p.id}">Aprobar y publicar</button><button class="btn danger sm" data-rj="${p.id}">Rechazar</button></div></div>`).join("")
        : `<div class="empty">No hay nada para revisar.</div>`}</section>
      <section class="card"><h3>Fuentes del bot</h3>
        ${d.recommended_missing ? `<div class="card near"><b>Fuentes recomendadas</b><div class="sub">Páginas oficiales de beneficios (MODO, Brubank, Personal Pay, Cuenta DNI, Ualá, Macro, American Express, Banco Ciudad) que el bot puede leer.</div>
          <button class="btn sm" id="src-rec">Agregar las ${d.recommended_missing} recomendadas</button></div>` : ""}
        ${d.sources.map(s => `<div class="queue-item"><div class="row between"><b>${esc(s.name)}</b><span class="fine">confianza ${Math.round(s.trust * 100)}%</span></div>
          <div class="fine" style="overflow-wrap:anywhere">${esc(s.url)}${s.kind === "navegador" ? " · con navegador" : ""}</div><div class="fine">${esc(s.last_status || "Sin correr todavía")}</div>
          ${s.kind !== "fixture" ? `<div class="fine">${s.published} publicadas · ${s.pending} para revisar${s.notes ? " · " + esc(s.notes) : ""}</div>
          <label class="field">Medio de pago de esta página<select data-sm="${s.id}"><option value="">— lo dice cada promo —</option>${S.cat.methods.map(m => `<option value="${m.id}" ${m.id === s.method_id ? "selected" : ""}>${esc(m.name)}</option>`).join("")}</select></label>
          ${s.pending ? `<button class="btn ghost sm" data-apall="${s.id}" data-n="${s.pending}">Aprobar las ${s.pending} pendientes de esta fuente</button>` : ""}` : ""}
          <div class="row"><div class="grow sub">Revisé sus términos de uso</div><button class="switch" role="switch" data-tos="${s.id}" aria-checked="${!!s.tos_ok}" aria-label="Términos revisados"></button></div>
          <div class="row"><div class="grow sub">Activa</div><button class="switch" role="switch" data-en="${s.id}" aria-checked="${!!s.enabled}" aria-label="Fuente activa"></button></div></div>`).join("")}
        <div class="sub">Agregá páginas de promos públicas (bancos, billeteras, comercios). Antes de activarlas, revisá que sus términos permitan leerlas automáticamente; el bot además respeta el robots.txt de cada sitio.</div>
        <label class="field" for="src-name">Nombre<input id="src-name" placeholder="Ej: Promos de tal banco"></label>
        <label class="field" for="src-url">Dirección (https://…)<input id="src-url" type="url"></label>
        <label class="field" for="src-method">Medio de pago de la página (si es de un banco o billetera)<select id="src-method"><option value="">— lo dice cada promo —</option>${S.cat.methods.map(m => `<option value="${m.id}">${esc(m.name)}</option>`).join("")}</select></label>
        <label class="row"><input type="checkbox" id="src-browser"> <span class="sub">La página arma las promos al abrirse (leerla con navegador)</span></label>
        <button class="btn ghost" id="src-add">Agregar fuente</button>
        <details class="fine"><summary>Páginas que el bot todavía no puede leer</summary>${Object.entries(d.not_readable || {}).map(([k, v]) => `<div><b>${esc(k)}:</b> ${esc(v)}</div>`).join("")}</details></section>
      <section class="card"><h3>Ajustes</h3>
        <div class="grid2"><label class="field" for="s-pf">TNA plazo fijo (%)<input id="s-pf" inputmode="decimal" value="${esc(d.settings.ref_tna_plazo_fijo)}"></label>
          <label class="field" for="s-rem">TNA remunerada (%)<input id="s-rem" inputmode="decimal" value="${esc(d.settings.ref_tna_remunerada)}"></label>
          <label class="field" for="s-th">Confianza para publicar sola (0,5 a 1)<input id="s-th" inputmode="decimal" value="${esc(d.settings.publish_threshold)}"></label>
          <label class="field" for="s-h">Correr el bot cada (horas)<input id="s-h" inputmode="numeric" value="${esc(d.settings.bot_every_hours)}"></label></div>
        <div class="fine">Tasas actualizadas ${d.settings.ref_tna_fecha ? "el " + fdate(d.settings.ref_tna_fecha) : "nunca"}. Se muestran en la calculadora como referencia.</div>
        <button class="btn" id="s-save">Guardar ajustes</button></section>`;
    $("#q-src").onchange = e => { S.adminSrc = e.target.value; route(); };
    $$("[data-seen]").forEach(b => b.onclick = () => busy(b, async () => { await api(`/api/admin/feedback/${b.dataset.seen}`, { method: "PUT", json: { seen: true } }); route(); }));
    $("#rl-go").onclick = e => busy(e.currentTarget, async () => {
      const r = await api("/api/admin/reset-link", { method: "POST", json: { email: $("#rl-email").value } });
      $("#rl-out").innerHTML = `<div class="card near"><span class="sub">Mandale este link. Vale ${r.hours} horas y se puede usar una sola vez.</span><div class="raw">${esc(r.link)}</div><button class="btn sm" id="rl-copy">Copiar link</button></div>`;
      $("#rl-copy").onclick = () => navigator.clipboard?.writeText(r.link).then(() => toast("Link copiado"), () => toast("Copialo a mano"));
    });
    $("#runbot").onclick = e => busy(e.currentTarget, async () => { const r = await api("/api/admin/bot/run", { method: "POST" }); toast(`Listo: ${r.found} encontradas, ${r.new} nuevas, ${r.queued} para revisar.`); route(); });
    $$(".queue-item [data-d]").forEach(b => b.onclick = () => b.setAttribute("aria-pressed", String(b.getAttribute("aria-pressed") !== "true")));
    $$("[data-ap]").forEach(b => b.onclick = () => busy(b, async () => {
      const q = b.closest("[data-q]");
      const f = k => $(`[data-f=${k}]`, q).value;
      await api(`/api/admin/promos/${b.dataset.ap}`, { method: "POST", json: { action: "approve", merchant: f("merchant"), method_id: f("method_id"), pct: f("pct").replace(",", "."),
        cap_month: f("cap_month").replace(/\D/g, "") || null, days: $$("[data-d][aria-pressed=true]", q).map(x => +x.dataset.d) } });
      toast("Publicada"); route();
    }));
    $$("[data-rj]").forEach(b => b.onclick = () => busy(b, async () => { await api(`/api/admin/promos/${b.dataset.rj}`, { method: "POST", json: { action: "reject" } }); toast("Rechazada"); route(); }));
    $$("[data-tos]").forEach(b => b.onclick = () => busy(b, async () => { await api(`/api/admin/sources/${b.dataset.tos}`, { method: "PUT", json: { tos_ok: b.getAttribute("aria-checked") !== "true" } }); route(); }));
    $$("[data-en]").forEach(b => b.onclick = () => busy(b, async () => { await api(`/api/admin/sources/${b.dataset.en}`, { method: "PUT", json: { enabled: b.getAttribute("aria-checked") !== "true" } }); route(); }));
    $("#src-add").onclick = e => busy(e.currentTarget, async () => { await api("/api/admin/sources", { method: "POST", json: { name: $("#src-name").value, url: $("#src-url").value, method_id: $("#src-method").value, browser: $("#src-browser").checked } }); toast("Fuente agregada (apagada hasta que la revises)"); route(); });
    $("#src-rec") && ($("#src-rec").onclick = e => busy(e.currentTarget, async () => {
      const r = await api("/api/admin/sources/recommended", { method: "POST" });
      toast(`Agregué ${r.added} fuentes. Tocá «Correr ahora» para buscar promos.`); route();
    }));
    $$("[data-sm]").forEach(s => s.onchange = async () => { await api(`/api/admin/sources/${s.dataset.sm}`, { method: "PUT", json: { method_id: s.value } }); toast("Guardado"); });
    $$("[data-apall]").forEach(b => b.onclick = () => busy(b, async () => {
      if (b.dataset.sure !== "1") { b.dataset.sure = "1"; b.textContent = `¿Seguro? Tocá de nuevo para publicar las ${b.dataset.n}`; return; }
      const r = await api(`/api/admin/sources/${b.dataset.apall}/approve-all`, { method: "POST" });
      toast(`Publicadas: ${r.approved}`); route();
    }));
    $("#s-save").onclick = e => busy(e.currentTarget, async () => {
      const v = id => $(id).value.replace(",", ".");
      await api("/api/admin/settings", { method: "PUT", json: { ref_tna_plazo_fijo: v("#s-pf"), ref_tna_remunerada: v("#s-rem"), publish_threshold: v("#s-th"), bot_every_hours: v("#s-h") } });
      toast("Ajustes guardados");
    });
  };

  boot();
})();
