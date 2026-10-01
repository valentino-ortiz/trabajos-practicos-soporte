/**
 * sw.js — Service Worker de ChefVoz (PWA)
 *
 * Estrategia: Cache-first para assets estáticos,
 * Network-first para llamadas a la API.
 */

'use strict';

const NOMBRE_CACHE = 'chefvoz-v5';

/** Assets estáticos a pre-cachear */
const ASSETS_ESTATICOS = [
    '/',
    '/editor',
    '/static/css/style.css',
    '/static/js/editor.js',
    '/static/js/cocina.js?v=5',
    '/static/manifest.json',
];

/* ── Instalación: pre-cacheo de assets ──────────────────────────────────── */
self.addEventListener('install', (evento) => {
    evento.waitUntil(
        caches.open(NOMBRE_CACHE).then((cache) => {
            return cache.addAll(ASSETS_ESTATICOS);
        }).then(() => self.skipWaiting())
    );
});

/* ── Activación: limpiar caches viejas ───────────────────────────────────── */
self.addEventListener('activate', (evento) => {
    evento.waitUntil(
        caches.keys().then((nombres) =>
            Promise.all(
                nombres
                    .filter(nombre => nombre !== NOMBRE_CACHE)
                    .map(nombre => caches.delete(nombre))
            )
        ).then(() => self.clients.claim())
    );
});

/* ── Fetch: estrategia híbrida ───────────────────────────────────────────── */
self.addEventListener('fetch', (evento) => {
    const url = new URL(evento.request.url);

    // API y audio: siempre red (no cachear)
    if (url.pathname.startsWith('/api/')) {
        evento.respondWith(fetch(evento.request));
        return;
    }

    // Assets estáticos: cache-first
    evento.respondWith(
        caches.match(evento.request).then((respuestaCacheada) => {
            if (respuestaCacheada) return respuestaCacheada;

            // Si no está en caché, buscar en red y guardar
            return fetch(evento.request).then((respuestaRed) => {
                if (!respuestaRed || respuestaRed.status !== 200) {
                    return respuestaRed;
                }
                const respuestaClonada = respuestaRed.clone();
                caches.open(NOMBRE_CACHE).then((cache) => {
                    cache.put(evento.request, respuestaClonada);
                });
                return respuestaRed;
            }).catch(() => {
                // Offline fallback: devolver la página del editor si existe
                if (evento.request.destination === 'document') {
                    return caches.match('/editor');
                }
            });
        })
    );
});
