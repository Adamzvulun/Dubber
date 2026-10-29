/* The phone app's service worker (phone mode only, registered by app.js under /p/<token>/): the app opens even
   without the PC or the mailbox answering — network first, the last copy when there is none. Requests to the PC
   (another address) and to the mailbox's /api/ are never cached. */
"use strict";

const CACHE = "dubber";

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(caches.open(CACHE).then((cache) => cache.add("./")).catch(() => {}));
});

self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== location.origin || url.pathname.includes("/api/")) return;
  event.respondWith(fetch(event.request).then((response) => {
    if (response.ok) {
      const copy = response.clone();
      caches.open(CACHE).then((cache) => cache.put(event.request, copy));
    }
    return response;
  }).catch(async () => (await caches.match(event.request)) || (await caches.match("./")) || Response.error()));
});
