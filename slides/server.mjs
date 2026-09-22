// Slidev render service.
//
// Spring Boot posts the markdown the AI service generated. This service builds it
// into a static site (served back to students by the API) and exports a PDF, then
// uploads both, plus the markdown, to RustFS under the prefix Spring chose. Like
// the AI service it is internal: it trusts its caller, and the X-Internal-Key
// header only keeps other containers on the network from using it.

import { execFile } from "node:child_process";
import { mkdtemp, readdir, readFile, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:http";
import { join, relative, sep } from "node:path";
import { PutObjectCommand, S3Client } from "@aws-sdk/client-s3";
import { contentType, isSafeBase, isSafePrefix } from "./paths.mjs";

const PORT = Number(process.env.PORT ?? 3030);
const INTERNAL_KEY = process.env.INTERNAL_API_KEY ?? "dev-internal-key-change-me";
const BUCKET = process.env.S3_BUCKET ?? "lecture-uploads";
const SLIDEV = join(import.meta.dirname, "node_modules", ".bin", "slidev");
const WORK_ROOT = join(import.meta.dirname, "work");
const MAX_BODY_BYTES = 2 * 1024 * 1024;
const STEP_TIMEOUT_MS = 5 * 60 * 1000;

const s3 = new S3Client({
  endpoint: process.env.S3_ENDPOINT ?? "http://rustfs:9000",
  region: process.env.S3_REGION ?? "us-east-1",
  // RustFS is not AWS: virtual-host addressing would try to resolve bucket.rustfs.
  forcePathStyle: true,
  credentials: {
    accessKeyId: process.env.S3_ACCESS_KEY ?? "rustfsadmin",
    secretAccessKey: process.env.S3_SECRET_KEY ?? "rustfsadmin",
  },
});

function run(args, cwd) {
  // Slidev decides its own mode per command. An inherited NODE_ENV=production breaks
  // `export`, whose Vite dev server then never mounts the deck.
  const { NODE_ENV: _ignored, ...env } = process.env;
  return new Promise((resolve, reject) => {
    execFile(
      SLIDEV,
      args,
      // CI=1 keeps Slidev from ever prompting (e.g. to install a missing theme).
      { cwd, timeout: STEP_TIMEOUT_MS, maxBuffer: 16 * 1024 * 1024, env: { ...env, CI: "1" } },
      (error, stdout, stderr) => {
        if (error) {
          const tail = `${stdout}\n${stderr}`.trim().split("\n").slice(-8).join("\n");
          reject(new Error(`slidev ${args[0]} failed: ${tail}`));
        } else {
          resolve();
        }
      },
    );
  });
}

async function* walk(dir) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) yield* walk(path);
    else yield path;
  }
}

async function put(key, body, type) {
  await s3.send(new PutObjectCommand({ Bucket: BUCKET, Key: key, Body: body, ContentType: type }));
}

async function render({ markdown, base, prefix }) {
  const dir = await mkdtemp(join(WORK_ROOT, "deck-"));
  try {
    await writeFile(join(dir, "slides.md"), markdown, "utf8");
    await run(["build", "slides.md", "--base", base, "--out", "dist"], dir);

    let files = 0;
    const dist = join(dir, "dist");
    for await (const path of walk(dist)) {
      const rel = relative(dist, path).split(sep).join("/");
      await put(`${prefix}/site/${rel}`, await readFile(path), contentType(rel));
      files++;
    }
    await put(`${prefix}/slides.md`, markdown, "text/markdown; charset=utf-8");

    // The PDF is a convenience; a deck that built but failed to export is still usable.
    let pdf = false;
    try {
      await run(["export", "slides.md", "--output", "deck.pdf", "--timeout", "60000"], dir);
      await put(`${prefix}/deck.pdf`, await readFile(join(dir, "deck.pdf")), "application/pdf");
      pdf = true;
    } catch (error) {
      console.warn(`PDF export failed for ${prefix}: ${error.message}`);
    }
    return { files, pdf };
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
}

// One render at a time: each spawns Vite, and export runs a headless Chromium.
let queue = Promise.resolve();
function enqueue(job) {
  const result = queue.then(job, job);
  queue = result.catch(() => {});
  return result;
}

function send(res, status, body) {
  res.writeHead(status, { "content-type": "application/json" });
  res.end(JSON.stringify(body));
}

async function readJson(req) {
  let size = 0;
  const chunks = [];
  for await (const chunk of req) {
    size += chunk.length;
    if (size > MAX_BODY_BYTES) throw new Error("request too large");
    chunks.push(chunk);
  }
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

createServer(async (req, res) => {
  if (req.method === "GET" && req.url === "/health") {
    return send(res, 200, { status: "ok", service: "slides" });
  }
  if (req.method !== "POST" || req.url !== "/render") {
    return send(res, 404, { detail: "not found" });
  }
  if (req.headers["x-internal-key"] !== INTERNAL_KEY) {
    return send(res, 401, { detail: "bad internal key" });
  }

  let body;
  try {
    body = await readJson(req);
  } catch (error) {
    return send(res, 400, { detail: error.message });
  }
  const { markdown, base, prefix } = body ?? {};
  // The base is baked into every asset URL of the build, and the prefix becomes S3
  // keys, so both are checked against a strict shape rather than trusted.
  if (typeof markdown !== "string" || !markdown || !isSafeBase(base) || !isSafePrefix(prefix)) {
    return send(res, 422, { detail: "markdown, base and prefix are required" });
  }

  const started = Date.now();
  try {
    const result = await enqueue(() => render({ markdown, base, prefix }));
    console.log(`Rendered ${prefix}: ${result.files} files, pdf=${result.pdf}, ${Date.now() - started} ms`);
    send(res, 200, result);
  } catch (error) {
    console.error(`Render failed for ${prefix}: ${error.message}`);
    send(res, 500, { detail: error.message });
  }
}).listen(PORT, () => console.log(`slides service listening on :${PORT}`));
