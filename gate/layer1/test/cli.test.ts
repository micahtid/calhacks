import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const EXAMPLES = new URL("../../../contracts/examples/", import.meta.url);
const CLI = fileURLToPath(new URL("../src/cli.ts", import.meta.url));

test("cli maps JSONL in to JSONL out, same order", () => {
  const files = readdirSync(EXAMPLES).sort();
  const lines = files.map((f) => JSON.stringify(JSON.parse(readFileSync(new URL(f, EXAMPLES), "utf8"))));
  const out = spawnSync(process.execPath, [CLI], { input: lines.join("\n") + "\n\n", encoding: "utf8" });
  assert.equal(out.status, 0, out.stderr);
  const results = out.stdout.trim().split("\n").map((l) => JSON.parse(l));
  assert.deepEqual(results.map((r) => r.id), files.map((f) => f.replace(/\.json$/, "")));
  assert.ok(results.every((r) => typeof r.pass === "boolean" && Array.isArray(r.failures)));
});
