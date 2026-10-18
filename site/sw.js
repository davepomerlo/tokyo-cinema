/* Offline support for the installed app.
 *
 * - App files (page, script, styles, icons): served from cache instantly, refreshed in
 *   the background, so the app opens with no connection.
 * - Listings (data/showtimes.json): network first, so you get the morning's scan when
 *   online; falls back to the last saved copy offline.
 * - Fonts and posters: cached as you see them.
 *
 * BUILD is replaced with the commit id at deploy time, so each release installs cleanly.
 */
const BUILD = "__BUILD__";
const SHELL = `shell-${BUILD}`;
const DATA = "data-v1";
const MEDIA = "media-v1";
const MEDIA_MAX = 250;

const SHELL_FILES = [
  "./",
  "index.html",
  "app.js",
  "style.css",
  "manifest.webmanifest",
  "icons/icon-192.png",
  "icons/icon-512.png",
  "icons/favicon-64.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(SHELL)
      .then((c) => c.addAll(SHELL_FILES.map((u) => new Request(u, { cache: "reload" }))))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const keep = new Set([SHELL, DATA, MEDIA]);
    for (const key of await caches.keys()) if (!keep.has(key)) await caches.delete(key);
    await self.clients.claim();
  })());
});

async function networkFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  try {
    const res = await fetch(request, { cache: "no-cache" });
    if (res.ok) cache.put(request, res.clone());
    return res;
  } catch (err) {
    const hit = await cache.match(request, { ignoreSearch: true });
    if (hit) return hit;
    throw err;
  }
}

async function staleWhileRevalidate(request, cacheName, event) {
  const cache = await caches.open(cacheName);
  const hit = await cache.match(request, { ignoreSearch: cacheName === SHELL });
  const update = fetch(request).then((res) => {
    if (res.ok || res.type === "opaque") cache.put(request, res.clone());
    return res;
  }).catch(() => null);
  if (hit) {
    event.waitUntil(update);
    return hit;
  }
  const res = await update;
  return res || Response.error();
}

async function trimMedia() {
  const cache = await caches.open(MEDIA);
  const keys = await cache.keys();
  for (const k of keys.slice(0, Math.max(0, keys.length - MEDIA_MAX))) await cache.delete(k);
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);

  // Listings
  if (url.origin === location.origin && url.pathname.endsWith("/data/showtimes.json")) {
    event.respondWith(networkFirst(req, DATA));
    return;
  }

  // Opening the app: try the network briefly, fall back to the cached page.
  if (req.mode === "navigate") {
    event.respondWith((async () => {
      try {
        const res = await Promise.race([
          fetch(req),
          new Promise((_, reject) => setTimeout(() => reject(new Error("slow")), 3000)),
        ]);
        if (res.ok) (await caches.open(SHELL)).put("index.html", res.clone());
        return res;
      } catch {
        const cache = await caches.open(SHELL);
        return (await cache.match("index.html")) || (await cache.match("./")) || Response.error();
      }
    })());
    return;
  }

  // App files
  if (url.origin === location.origin) {
    event.respondWith(staleWhileRevalidate(req, SHELL, event));
    return;
  }

  // Fonts and posters
  if (/fonts\.(googleapis|gstatic)\.com$/.test(url.hostname) || req.destination === "image") {
    event.respondWith(staleWhileRevalidate(req, MEDIA, event).finally(() => event.waitUntil(trimMedia())));
  }
});

self.addEventListener("message", (event) => {
  if (event.data === "skip-waiting") self.skipWaiting();
});
