// node --test cloud/worker   (no Cloudflare needed: KV and the static files are faked)
import { test } from "node:test";
import assert from "node:assert/strict";
import worker from "./worker.js";

function fakeEnv() {
  const store = new Map();
  return {
    store,
    BOX: {
      async get(key, type) { const v = store.get(key); return v === undefined ? null : type === "json" ? JSON.parse(v) : v; },
      async put(key, value, options) { assert.ok(options?.expirationTtl > 0); store.set(key, value); },
      async delete(key) { store.delete(key); },
      async list({ prefix }) {
        return { keys: [...store.keys()].filter((k) => k.startsWith(prefix)).map((name) => ({ name })), list_complete: true };
      },
    },
    ASSETS: { async fetch(req) { const p = new URL(req.url).pathname; return new Response(`asset ${p}`, { status: p === "/missing" ? 404 : 200 }); } },
  };
}

const TOKEN = "a".repeat(43), OTHER = "b".repeat(43);
const call = (env, method, path, { token = TOKEN, body } = {}) => worker.fetch(new Request(`https://dubber.example.workers.dev${path}`, {
  method, headers: { "X-Dubber-Token": token, "Content-Type": "application/json" }, body: body && JSON.stringify(body) }), env);

test("a box needs a valid token", async () => {
  const env = fakeEnv();
  assert.equal((await call(env, "GET", "/api/box", { token: "" })).status, 401);
  assert.equal((await call(env, "GET", "/api/box", { token: "short" })).status, 401);
  assert.deepEqual(await (await call(env, "GET", "/api/box")).json(), { pc: null, links: [] });
});

test("the PC's address is stored per household, never the token itself", async () => {
  const env = fakeEnv();
  const res = await call(env, "PUT", "/api/box/pc", { body: { url: "https://abc-def.trycloudflare.com/", version: "0.10.0" } });
  assert.equal(res.status, 200);
  const box = await (await call(env, "GET", "/api/box")).json();
  assert.equal(box.pc.url, "https://abc-def.trycloudflare.com");
  assert.equal(box.pc.version, "0.10.0");
  assert.equal((await (await call(env, "GET", "/api/box", { token: OTHER })).json()).pc, null);
  assert.ok(![...env.store.keys(), ...env.store.values()].some((s) => s.includes(TOKEN)));
  assert.equal((await call(env, "PUT", "/api/box/pc", { body: { url: "http://plain.example" } })).status, 422);
});

test("links are queued, listed oldest first, cleaned and deleted", async () => {
  const env = fakeEnv();
  const a = await (await call(env, "POST", "/api/box/links", { body: { url: "https://www.tiktok.com/@x/video/1", lang: "he", voice: "female", background: false } })).json();
  const b = await (await call(env, "POST", "/api/box/links", { body: { url: "https://youtu.be/abc", lang: "<bad>", voice: "robot" } })).json();
  assert.equal(a.lang, "he"); assert.equal(a.voice, "female"); assert.equal(a.background, false);
  assert.equal(b.lang, "ru"); assert.equal(b.voice, "male"); assert.equal(b.background, true); assert.equal(b.remove_voice, false);
  const box = await (await call(env, "GET", "/api/box")).json();
  assert.deepEqual(box.links.map((l) => l.id), [a.id, b.id]);
  assert.equal((await (await call(env, "GET", "/api/box", { token: OTHER })).json()).links.length, 0);
  await call(env, "DELETE", `/api/box/links/${a.id}`);
  assert.deepEqual((await (await call(env, "GET", "/api/box")).json()).links.map((l) => l.id), [b.id]);
  assert.equal((await call(env, "POST", "/api/box/links", { body: { url: "javascript:alert(1)" } })).status, 422);
});

test("a box holds at most 50 links", async () => {
  const env = fakeEnv();
  for (let i = 0; i < 50; i++) assert.equal((await call(env, "POST", "/api/box/links", { body: { url: `https://youtu.be/${i}` } })).status, 201);
  assert.equal((await call(env, "POST", "/api/box/links", { body: { url: "https://youtu.be/x" } })).status, 429);
});

test("the phone app is served under /p/<token>/ without leaking the token", async () => {
  const env = fakeEnv();
  const index = await call(env, "GET", `/p/${TOKEN}/`);
  assert.equal(await index.text(), "asset /index.html");
  assert.equal(index.headers.get("Referrer-Policy"), "no-referrer");
  assert.equal(await (await call(env, "GET", `/p/${TOKEN}/app.js?v=1`)).text(), "asset /app.js");
  const bare = await call(env, "GET", `/p/${TOKEN}`);
  assert.equal(bare.status, 301);
  assert.match(await (await call(env, "GET", "/")).text(), /Настройки → Телефон/);
});
