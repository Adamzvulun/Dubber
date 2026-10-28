/* Dubber's phone mailbox: a Cloudflare Worker (free plan) on Adam's account, shared by every household.

   - /p/<token>/…   the phone app (the website's own files, built into ./public by cloud/build.py). The household's
                    secret token is part of the address, so the home-screen icon (Android and iPhone) keeps it.
   - /api/box…      the household's box, every call with the header X-Dubber-Token: <token>
       GET    /api/box                → {pc: {url, version, seen} | null, links: [{id, url, lang, …, added}]}
       PUT    /api/box/pc {url, version}   (the PC, at start and every few minutes: where its tunnel is now)
       POST   /api/box/links {url, lang, voice, background, remove_voice} → {id}   (the phone, PC switched off)
       DELETE /api/box/links/<id>     (the PC, once it has started the dub)

   Storage (KV binding BOX): keys "pc:<hash>" and "link:<hash>:<id>", where <hash> = SHA-256 of the token: the token
   itself is never stored. Links are kept for 30 days, the PC's address for 60. */

const TOKEN = /^[A-Za-z0-9_-]{32,64}$/;
const LINK_DAYS = 30, PC_DAYS = 60, MAX_LINKS = 50, MAX_URL = 2000;
const VOICES = new Set(["male", "female", "original"]);

const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" } });

async function hashOf(token) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(token));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function httpUrl(text) {
  try {
    const url = new URL(String(text));
    return ["http:", "https:"].includes(url.protocol) && url.href.length <= MAX_URL ? url.href : null;
  } catch (_) {
    return null;
  }
}

async function readJson(request) {
  try { return await request.json(); } catch (_) { return null; }
}

async function listLinks(env, hash) {
  const links = [];
  let cursor;
  do {
    const page = await env.BOX.list({ prefix: `link:${hash}:`, cursor });
    for (const key of page.keys) {
      const link = await env.BOX.get(key.name, "json");
      if (link) links.push(link);
    }
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor);
  return links.sort((a, b) => a.added.localeCompare(b.added));
}

async function box(request, env, path) {
  const token = request.headers.get("X-Dubber-Token") || "";
  if (!TOKEN.test(token)) return json({ error: "token" }, 401);
  const hash = await hashOf(token);

  if (path === "/api/box" && request.method === "GET") {
    return json({ pc: await env.BOX.get(`pc:${hash}`, "json"), links: await listLinks(env, hash) });
  }
  if (path === "/api/box/pc" && request.method === "PUT") {
    const body = await readJson(request);
    const url = httpUrl(body?.url);
    if (!url || !url.startsWith("https://")) return json({ error: "url" }, 422);
    const pc = { url: url.replace(/\/$/, ""), version: String(body.version || "").slice(0, 20),
                 seen: new Date().toISOString() };
    await env.BOX.put(`pc:${hash}`, JSON.stringify(pc), { expirationTtl: PC_DAYS * 86400 });
    return json(pc);
  }
  if (path === "/api/box/links" && request.method === "POST") {
    const body = await readJson(request);
    const url = httpUrl(body?.url);
    if (!url) return json({ error: "url" }, 422);
    if ((await listLinks(env, hash)).length >= MAX_LINKS) return json({ error: "full" }, 429);
    const link = {
      id: crypto.randomUUID(), url, added: new Date().toISOString(),
      lang: /^[a-z]{2,3}$/.test(body.lang || "") ? body.lang : "ru",
      voice: VOICES.has(body.voice) ? body.voice : "male",
      background: body.background !== false, remove_voice: body.remove_voice === true,
    };
    await env.BOX.put(`link:${hash}:${link.id}`, JSON.stringify(link), { expirationTtl: LINK_DAYS * 86400 });
    return json(link, 201);
  }
  const one = path.match(/^\/api\/box\/links\/([0-9a-f-]{36})$/);
  if (one && request.method === "DELETE") {
    await env.BOX.delete(`link:${hash}:${one[1]}`);
    return json({ deleted: one[1] });
  }
  return json({ error: "not found" }, 404);
}

const LANDING = `<!doctype html><html lang="ru"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Дубляж</title>
<body style="font:17px/1.5 system-ui,sans-serif;max-width:32rem;margin:15vh auto;padding:0 20px;color:#111827">
<h1 style="font-size:24px">Дубляж на телефоне</h1>
<p>Откройте программу «Дубляж» на компьютере: <b>Настройки → Телефон</b>, и наведите камеру телефона на QR-код.</p>
<p lang="en" style="color:#4B5563">Open Dubber on your computer: <b>Settings → Phone</b>, and point the phone's
camera at the QR code.</p></body></html>`;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname.startsWith("/api/")) return box(request, env, url.pathname);

    const app = url.pathname.match(/^\/p\/([A-Za-z0-9_-]{32,64})(\/.*)?$/);
    if (app) {
      if (!app[2]) return Response.redirect(`${url.origin}${url.pathname}/${url.search}`, 301);
      const file = app[2] === "/" ? "/index.html" : app[2];
      const asset = await env.ASSETS.fetch(new Request(new URL(file, url.origin), request));
      // The token is in the address: never let it leak to another site through the Referer header.
      const response = new Response(asset.body, asset);
      response.headers.set("Referrer-Policy", "no-referrer");
      response.headers.set("Cache-Control", "no-cache");
      return response;
    }
    return new Response(LANDING, { headers: { "Content-Type": "text/html; charset=utf-8" } });
  },
};
