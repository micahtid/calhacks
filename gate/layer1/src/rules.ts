import { isLookalike, sameAddress } from "./lookalike.ts";
import type { Layer1Context, Layer1Result, RuleId, Snapshot } from "./types.ts";

const EPS = 1e-9;

function toBaseUnits(usd: number, decimals: number): bigint {
  return BigInt(Math.round(usd * 10 ** decimals));
}

// Every rule must pass. Failures are reported in RULE_IDS order.
export function checkLayer1(s: Snapshot, ctx: Layer1Context): Layer1Result {
  const pr = s.payment_required;
  const { allowlist, knownSellers } = ctx;
  const failures: RuleId[] = [];

  if (!sameAddress(pr.payTo, s.store.payTo)) failures.push("L1_PAYTO_MISMATCH");

  const wallets = [pr.payTo, s.store.payTo];
  if (wallets.some((w) => knownSellers.some((k) => isLookalike(w, k.payTo)))) failures.push("L1_PAYTO_LOOKALIKE");

  let charged = Number.POSITIVE_INFINITY;
  if (/^[0-9]+$/.test(pr.amount)) {
    const amount = BigInt(pr.amount);
    if (amount !== toBaseUnits(s.item.priceUsd, allowlist.usdc_decimals)) failures.push("L1_AMOUNT_MISMATCH");
    charged = Number(amount) / 10 ** allowlist.usdc_decimals;
  } else {
    failures.push("L1_AMOUNT_MISMATCH");
  }

  const cost = Math.max(s.item.priceUsd, charged);
  if (cost > s.mandate.max_price_usd + EPS) failures.push("L1_OVER_MAX");
  if (cost > s.mandate.budget_remaining_usd + EPS) failures.push("L1_OVER_BUDGET");

  if (!allowlist.networks.includes(pr.network)) failures.push("L1_NETWORK");
  const asset = allowlist.assets[pr.network];
  if (!asset || !sameAddress(asset, pr.asset)) failures.push("L1_ASSET");
  if (!allowlist.schemes.includes(pr.scheme)) failures.push("L1_SCHEME");
  if (!(pr.maxTimeoutSeconds > 0 && pr.maxTimeoutSeconds <= allowlist.max_timeout_s)) failures.push("L1_TIMEOUT");
  if (s.checkout_item_id !== s.item.id) failures.push("L1_ITEM_MISMATCH");

  return { id: s.id, pass: failures.length === 0, failures };
}
