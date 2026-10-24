import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { Allowlist, KnownSeller, Layer1Context } from "./types.ts";

export const DEFAULT_CONTRACTS = new URL("../../../contracts/", import.meta.url);

export function loadContext(contractsDir: string | URL = DEFAULT_CONTRACTS): Layer1Context {
  const read = (name: string) =>
    JSON.parse(readFileSync(contractsDir instanceof URL ? new URL(name, contractsDir) : join(contractsDir, name), "utf8"));
  const knownSellers = (read("known_sellers.json") as { sellers: KnownSeller[] }).sellers;
  const allowlist = read("allowlist.json") as Allowlist;
  return { knownSellers, allowlist };
}
