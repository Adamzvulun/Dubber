// Stand-in for Cloudflare, to try the phone version on one machine (no account, no internet):
//   node tools/phone_dev.mjs [PC_PORT=7871]
//   - :8787  the mailbox worker (cloud/worker/worker.js) with the built phone app (python cloud/build.py) and an
//            in-memory KV — what https://dubber.<name>.workers.dev is
//   - :7872  the "tunnel": forwards to the PC on PC_PORT and adds Cf-Ray, as Cloudflare does
// Start the PC with: STUB_MAILBOX=http://127.0.0.1:8787 STUB_TUNNEL=http://127.0.0.1:7872 \
//   .venv/bin/python tools/stub_server.py /tmp/stub 7871
// The phone app is then http://127.0.0.1:8787/p/<token>/ (the token is in the stub data folder's .env).
import http from "node:http";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import worker from "../cloud/worker/worker.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const PUBLIC = path.join(here, "..", "cloud", "worker", "public");
const PC_PORT = Number(process.argv[2] || 7871);
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css",
  ".png": "image/png", ".webmanifest": "application/manifest+json" };

const store = new Map();
const env = {
  BOX: {
    async get(key, type) { const v = store.get(key); return v === undefined ? null : type === "json" ? JSON.parse(v) : v; },
    async put(key, value) { store.set(key, value); },
    async delete(key) { store.delete(key); },
    async list({ prefix }) { return { keys: [...store.keys()].filter((k) => k.startsWith(prefix)).map((name) => ({ name })), list_complete: true }; },
  },
  ASSETS: {
    async fetch(request) {
      const file = path.join(PUBLIC, decodeURIComponent(new URL(request.url).pathname));
      if (!file.startsWith(PUBLIC)) return new Response("no", { status: 404 });
      try { return new Response(await readFile(file), { headers: { "Content-Type": TYPES[path.extname(file)] || "application/octet-stream" } }); }
      catch (_) { return new Response("not found", { status: 404 }); }
    },
  },
};

http.createServer(async (req, res) => {
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  const body = ["GET", "HEAD"].includes(req.method) ? undefined : Buffer.concat(chunks);
  const response = await worker.fetch(new Request(`http://127.0.0.1:8787${req.url}`, { method: req.method, headers: req.headers, body }), env);
  res.writeHead(response.status, Object.fromEntries(response.headers));
  res.end(Buffer.from(await response.arrayBuffer()));
}).listen(8787, "127.0.0.1");

http.createServer((req, res) => {
  const upstream = http.request({ host: "127.0.0.1", port: PC_PORT, path: req.url, method: req.method,
    headers: { ...req.headers, "cf-ray": "dev-0000", "cf-connecting-ip": req.socket.remoteAddress } }, (up) => {
    res.writeHead(up.statusCode, up.headers);
    up.pipe(res);
  });
  upstream.on("error", () => { res.writeHead(502); res.end("PC off"); });
  req.pipe(upstream);
}).listen(7872, "127.0.0.1");

console.log("mailbox http://127.0.0.1:8787  tunnel http://127.0.0.1:7872 → PC :" + PC_PORT);
