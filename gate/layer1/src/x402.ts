import type { PaymentRequired } from "./types.ts";

interface PaymentRequiredHeader {
  x402Version: number;
  accepts: PaymentRequired[];
}

// Decode a PAYMENT-REQUIRED header (base64 JSON, x402 v2) into the terms the Gate checks: accepts[0].
export function decodePaymentRequired(header: string): PaymentRequired {
  const body = JSON.parse(Buffer.from(header, "base64").toString("utf8")) as PaymentRequiredHeader;
  const first = body.accepts?.[0];
  if (!first) throw new Error("PAYMENT-REQUIRED header has no accepts[] entry");
  const { scheme, network, amount, asset, payTo, maxTimeoutSeconds } = first;
  return { scheme, network, amount: String(amount), asset, payTo, maxTimeoutSeconds };
}
