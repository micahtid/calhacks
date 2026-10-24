import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { test } from "node:test";
import { checkLayer1, decodePaymentRequired, isLookalike, loadContext } from "../src/index.ts";
import type { Snapshot } from "../src/index.ts";

const EXAMPLES = new URL("../../../contracts/examples/", import.meta.url);
const ctx = loadContext();

function example(id: string): Snapshot {
  return JSON.parse(readFileSync(new URL(`${id}.json`, EXAMPLES), "utf8"));
}

// Captured from POST https://calhacks.micahtid.com/api/checkout/tetris-gb (x402 v2, 2026-10-24).
const LIVE_HEADER =
  "eyJ4NDAyVmVyc2lvbiI6MiwiZXJyb3IiOiJQYXltZW50IHJlcXVpcmVkIiwicmVzb3VyY2UiOnsidXJsIjoiaHR0cHM6Ly9jYWxoYWNrcy5taWNhaHRpZC5jb20vYXBpL2NoZWNrb3V0L3RldHJpcy1nYiIsImRlc2NyaXB0aW9uIjoiUGl4ZWwgQ2FydCBSZXRybyBjaGVja291dCIsIm1pbWVUeXBlIjoiYXBwbGljYXRpb24vanNvbiJ9LCJhY2NlcHRzIjpbeyJzY2hlbWUiOiJleGFjdCIsIm5ldHdvcmsiOiJlaXAxNTU6ODQ1MzIiLCJhbW91bnQiOiIyNTAwMDAwIiwiYXNzZXQiOiIweDAzNkNiRDUzODQyYzU0MjY2MzRlNzkyOTU0MWVDMjMxOGYzZENGN2UiLCJwYXlUbyI6IjB4NDVmRTkyOERhQTZBMTYzNjJjZDUxREQyNTY2MEJmNTQwYzE2Yzg2MiIsIm1heFRpbWVvdXRTZWNvbmRzIjoxMjAsImV4dHJhIjp7Im5hbWUiOiJVU0RDIiwidmVyc2lvbiI6IjIifX1dfQ==";

const EXPECTED: Record<string, string[]> = {
  "ex-legit-plain": [],
  "ex-payment-mismatch": ["L1_PAYTO_MISMATCH"],
  "ex-lookalike-payto": ["L1_PAYTO_LOOKALIKE"],
  "ex-bait-and-switch": ["L1_ITEM_MISMATCH"],
  "ex-too-cheap": [],
  "ex-prompt-injection": [],
  "ex-fake-reviews": [],
  "ex-legit-new-honest-seller": [],
};

test("every contract example has an expectation", () => {
  const ids = readdirSync(EXAMPLES).map((f) => f.replace(/\.json$/, ""));
  assert.deepEqual(ids.sort(), Object.keys(EXPECTED).sort());
});

for (const [id, failures] of Object.entries(EXPECTED)) {
  test(`example ${id}`, () => {
    const r = checkLayer1(example(id), ctx);
    assert.deepEqual(r.failures, failures);
    assert.equal(r.pass, failures.length === 0);
  });
}

test("live 402 header decodes to accepts[0] and passes on the honest listing", () => {
  const pr = decodePaymentRequired(LIVE_HEADER);
  assert.equal(pr.amount, "2500000");
  assert.equal(pr.payTo, "0x45fE928DaA6A16362cd51DD25660Bf540c16c862");
  assert.equal(pr.maxTimeoutSeconds, 120);
  const s = { ...example("ex-legit-plain"), payment_required: pr };
  assert.deepEqual(checkLayer1(s, ctx).failures, []);
});

test("lookalike keeps first and last 4 hex but differs", () => {
  const known = "0x45fE928DaA6A16362cd51DD25660Bf540c16c862";
  assert.equal(isLookalike("0x45fe1b7c3e90ad4f2216bb0e9a7c11d03f9ac862", known), true);
  assert.equal(isLookalike(known.toLowerCase(), known), false);
  assert.equal(isLookalike("0x9a3F0c21B7e4D58a6C0f1E2b3A4d5C6e7F8a9b01", known), false);
});

function withPayment(patch: Partial<Snapshot["payment_required"]>, mandate?: Partial<Snapshot["mandate"]>): Snapshot {
  const s = example("ex-legit-plain");
  return { ...s, payment_required: { ...s.payment_required, ...patch }, mandate: { ...s.mandate, ...mandate } };
}

test("amount must equal the listed price", () => {
  assert.deepEqual(checkLayer1(withPayment({ amount: "2500001" }), ctx).failures, ["L1_AMOUNT_MISMATCH"]);
  assert.ok(checkLayer1(withPayment({ amount: "2.5" }), ctx).failures.includes("L1_AMOUNT_MISMATCH"));
});

test("an inflated 402 amount counts against max price and budget", () => {
  const r = checkLayer1(withPayment({ amount: "50000000" }), ctx);
  assert.deepEqual(r.failures, ["L1_AMOUNT_MISMATCH", "L1_OVER_MAX", "L1_OVER_BUDGET"]);
});

test("mandate max price and budget", () => {
  assert.deepEqual(checkLayer1(withPayment({}, { max_price_usd: 2 }), ctx).failures, ["L1_OVER_MAX"]);
  assert.deepEqual(checkLayer1(withPayment({}, { budget_remaining_usd: 1 }), ctx).failures, ["L1_OVER_BUDGET"]);
  assert.deepEqual(checkLayer1(withPayment({}, { max_price_usd: 2.5 }), ctx).failures, []);
});

test("network, asset, scheme and timeout allowlists", () => {
  assert.deepEqual(checkLayer1(withPayment({ network: "eip155:8453" }), ctx).failures, ["L1_NETWORK", "L1_ASSET"]);
  assert.deepEqual(
    checkLayer1(withPayment({ asset: "0x0000000000000000000000000000000000000001" }), ctx).failures,
    ["L1_ASSET"],
  );
  assert.deepEqual(checkLayer1(withPayment({ scheme: "upto" }), ctx).failures, ["L1_SCHEME"]);
  assert.deepEqual(checkLayer1(withPayment({ maxTimeoutSeconds: 9999 }), ctx).failures, ["L1_TIMEOUT"]);
  assert.deepEqual(checkLayer1(withPayment({ maxTimeoutSeconds: 0 }), ctx).failures, ["L1_TIMEOUT"]);
});
