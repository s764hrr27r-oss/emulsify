/* EMULSIFY service worker — CDN only, on purpose.
 *
 * Every cold launch downloads and parses Pyodide plus numpy, scipy and pillow
 * from jsdelivr. Those URLs are version-pinned and immutable, so they are the
 * one thing here that is safe to keep. This worker caches them and nothing
 * else.
 *
 * SAME-ORIGIN IS NEVER TOUCHED. Not cache-first, not stale-while-revalidate,
 * not network-first — the fetch handler returns without calling respondWith,
 * so the browser behaves exactly as it does with no service worker installed.
 * That is deliberate and it is the whole safety argument:
 *
 *   - index.html and lab-worker.js must arrive fresh or the upload ritual
 *     breaks, and caching has always been the thing that bit, never uploads.
 *   - lab-worker.js fetches emulsify2.py, honey_sr.py and canon_profiles.py
 *     same-origin at boot. Cache those and an edit to canon would never land,
 *     with no error to notice.
 *   - a broken service worker therefore cannot brick the app. The page still
 *     comes from the network, so the worst case is a slow launch.
 *
 * This does NOT make the app work offline, and should not. Offline capability
 * would mean caching the page, which is the one thing forbidden here.
 *
 * The cache is keyed to the Pyodide version, NOT to the app build. Bumping
 * BUILD must not throw away 50 MB of runtime — that would invert the point.
 * When Pyodide is upgraded in lab-worker.js, change PYODIDE here to match and
 * the old cache is dropped on activate.
 */

const PYODIDE = "v0.26.1";                 // must match lab-worker.js line 98
const CACHE = "emulsify-cdn-" + PYODIDE;
const CDN = "https://cdn.jsdelivr.net";

self.addEventListener("install", () => self.skipWaiting());

self.addEventListener("activate", e => e.waitUntil((async () => {
  for (const k of await caches.keys()) {
    if (k.startsWith("emulsify-cdn-") && k !== CACHE) await caches.delete(k);
  }
  await self.clients.claim();
})()));

self.addEventListener("fetch", e => {
  const r = e.request;
  if (r.method !== "GET") return;
  let u;
  try { u = new URL(r.url); } catch (err) { return; }
  if (u.origin === self.location.origin) return;   /* the page, the worker, canon */
  if (u.origin !== CDN) return;                    /* nothing else is ours to hold */

  e.respondWith((async () => {
    const c = await caches.open(CACHE);
    const hit = await c.match(r);
    if (hit) return hit;
    const res = await fetch(r);
    /* 200 only. A 206 partial cannot be replayed as a whole response and
       cache.put rejects it; an opaque response has status 0 but is still
       replayable, which is what a no-cors wasm fetch looks like. */
    if (res && (res.status === 200 || res.type === "opaque")) {
      try { await c.put(r, res.clone()); } catch (err) { /* quota, ignore */ }
    }
    return res;
  })());
});

/* Escape hatch. From the page console:
     navigator.serviceWorker.controller.postMessage("purge-cdn")
   Useful if jsdelivr ever serves a bad body under a pinned URL, which cannot
   be fixed by bumping BUILD because BUILD does not key this cache. */
self.addEventListener("message", e => {
  if (e.data === "purge-cdn") e.waitUntil(caches.delete(CACHE));
});
