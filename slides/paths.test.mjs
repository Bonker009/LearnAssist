import assert from "node:assert/strict";
import { test } from "node:test";
import { contentType, isSafeBase, isSafePrefix } from "./paths.mjs";

test("accepts the base the API serves decks under", () => {
  assert.ok(isSafeBase("/api/slides/view/Ab3_x-9/"));
});

test("rejects bases that could escape or break the build", () => {
  for (const base of ["", "/", "api/slides/", "/api/slides", "/api/../x/", "/a b/", "//evil.com/", null]) {
    assert.equal(isSafeBase(base), false, String(base));
  }
});

test("accepts owner/deck key prefixes only", () => {
  assert.ok(isSafePrefix("slides/0f8c/1a2b"));
  for (const prefix of ["", "/slides/x", "slides/x/", "slides/../x", "slides//x", "a b", undefined]) {
    assert.equal(isSafePrefix(prefix), false, String(prefix));
  }
});

test("serves built assets with the right content type", () => {
  assert.equal(contentType("index.html"), "text/html; charset=utf-8");
  assert.equal(contentType("assets/index-abc.JS"), "text/javascript; charset=utf-8");
  assert.equal(contentType("assets/font.woff2"), "font/woff2");
  assert.equal(contentType("assets/unknown.xyz"), "application/octet-stream");
});
