// Tu Bolsillo: trabajador de fondo. Guarda la app para abrir rápido y recibe las notificaciones.
const CACHE = "tubolsillo-v1";
const SHELL = ["/", "/static/style.css", "/static/app.js", "/manifest.webmanifest", "/static/icons/icon-192.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});

// la app: primero la red (para tener lo último), y si no hay conexión, lo guardado.
// los datos (/api) nunca se guardan: siempre van a la red.
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.pathname.startsWith("/api/") || url.origin !== location.origin) return;
  e.respondWith(
    fetch(e.request).then(r => {
      const copy = r.clone();
      caches.open(CACHE).then(c => c.put(e.request, copy));
      return r;
    }).catch(() => caches.match(e.request).then(r => r || caches.match("/")))
  );
});

self.addEventListener("push", e => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (_) { d = { title: "Tu Bolsillo", body: e.data && e.data.text() }; }
  e.waitUntil(self.registration.showNotification(d.title || "Tu Bolsillo", {
    body: d.body || "", tag: d.tag || "tubolsillo", icon: "/static/icons/icon-192.png", badge: "/static/icons/badge-96.png",
    data: { url: d.url || "/#inicio" }, lang: "es-AR",
  }));
});

self.addEventListener("notificationclick", e => {
  e.notification.close();
  const target = new URL(e.notification.data && e.notification.data.url || "/#inicio", self.location.origin).href;
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(cs => {
    for (const c of cs) { if ("focus" in c) { c.navigate(target); return c.focus(); } }
    return self.clients.openWindow(target);
  }));
});
