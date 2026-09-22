// Input checks and content types, kept apart from the server so they can be tested
// without starting it.

// "/api/slides/view/<token>/": absolute, slash-terminated, no dots or odd characters.
export function isSafeBase(base) {
  return typeof base === "string" && /^\/(?:[A-Za-z0-9_-]+\/)+$/.test(base);
}

// "slides/<owner>/<deck>": relative S3 key prefix, no traversal, no trailing slash.
export function isSafePrefix(prefix) {
  return typeof prefix === "string" && /^[A-Za-z0-9_-]+(?:\/[A-Za-z0-9_-]+)*$/.test(prefix);
}

const TYPES = {
  html: "text/html; charset=utf-8",
  js: "text/javascript; charset=utf-8",
  mjs: "text/javascript; charset=utf-8",
  css: "text/css; charset=utf-8",
  json: "application/json",
  svg: "image/svg+xml",
  png: "image/png",
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  gif: "image/gif",
  webp: "image/webp",
  ico: "image/x-icon",
  woff: "font/woff",
  woff2: "font/woff2",
  ttf: "font/ttf",
  txt: "text/plain; charset=utf-8",
  map: "application/json",
  webmanifest: "application/manifest+json",
};

export function contentType(path) {
  const extension = path.slice(path.lastIndexOf(".") + 1).toLowerCase();
  return TYPES[extension] ?? "application/octet-stream";
}
