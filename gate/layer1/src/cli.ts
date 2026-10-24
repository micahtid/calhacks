// gate-l1: JSONL Snapshots on stdin -> one Layer1Result per line on stdout, same order.
// Usage: node gate/layer1/src/cli.ts [--contracts contracts/] < snapshots.jsonl
import { createInterface } from "node:readline";
import { loadContext } from "./context.ts";
import { checkLayer1 } from "./rules.ts";
import type { Snapshot } from "./types.ts";

const i = process.argv.indexOf("--contracts");
const ctx = loadContext(i > 0 ? process.argv[i + 1] : undefined);

const rl = createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of rl) {
  if (!line.trim()) continue;
  const s = JSON.parse(line) as Snapshot;
  process.stdout.write(JSON.stringify(checkLayer1(s, ctx)) + "\n");
}
