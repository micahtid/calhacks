// Mirrors contracts/snapshot.schema.json. Keep in sync with gatepy/contracts.py.

export type Label = "scam" | "legit" | "unknown";

export interface Mandate {
  query: string;
  max_price_usd: number;
  budget_remaining_usd: number;
}

export interface Store {
  name: string;
  sellerId: string;
  payTo: string;
  network: string;
  currency: string;
  sellingSince: number;
  rating: number;
  reviewCount: number;
  domain: string;
}

export interface Item {
  id: string;
  title: string;
  platform: string;
  condition: "Fair" | "Good" | "Like New" | "New";
  priceUsd: number;
  description: string;
  inStock: boolean;
}

export interface Review {
  author: string;
  rating: number;
  date: string;
  verifiedPurchase: boolean;
  body: string;
}

export interface PaymentRequired {
  scheme: string;
  network: string;
  amount: string;
  asset: string;
  payTo: string;
  maxTimeoutSeconds: number;
}

export interface Snapshot {
  id: string;
  family: string;
  label: Label;
  gen: { model: string; temperature: number; batch_id: string; round: number } | null;
  mandate: Mandate;
  store: Store;
  item: Item;
  reviews: Review[];
  payment_required: PaymentRequired;
  checkout_item_id: string;
  tactic_evidence: string | null;
}

export interface KnownSeller {
  sellerId: string;
  name: string;
  payTo: string;
  domain: string;
}

export interface Allowlist {
  networks: string[];
  assets: Record<string, string>;
  schemes: string[];
  max_timeout_s: number;
  usdc_decimals: number;
}

export interface Layer1Context {
  knownSellers: KnownSeller[];
  allowlist: Allowlist;
}

export const RULE_IDS = [
  "L1_PAYTO_MISMATCH",
  "L1_PAYTO_LOOKALIKE",
  "L1_AMOUNT_MISMATCH",
  "L1_OVER_MAX",
  "L1_OVER_BUDGET",
  "L1_NETWORK",
  "L1_ASSET",
  "L1_SCHEME",
  "L1_TIMEOUT",
  "L1_ITEM_MISMATCH",
] as const;

export type RuleId = (typeof RULE_IDS)[number];

export interface Layer1Result {
  id: string;
  pass: boolean;
  failures: RuleId[];
}
