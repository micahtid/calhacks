import "server-only";
import { NextResponse, connection, type NextRequest } from "next/server";
import { withX402, x402ResourceServer } from "@x402/next";
import { HTTPFacilitatorClient } from "@x402/core/server";
import { ExactEvmScheme } from "@x402/evm/exact/server";
import { formatUsd } from "./format";

// Every store takes USDC on the Base Sepolia testnet, and the x402.org facilitator checks and settles each payment.
export const PAYMENT = {
  network: "eip155:84532",
  networkName: "Base Sepolia",
  currency: "USDC",
  usdc: "0x036CbD53842c5426634e7929541eC2318f3dCF7e", // This is Circle's USDC contract on Base Sepolia.
  explorer: "https://sepolia.basescan.org",
} as const;

// A listing is a store item reduced to what checkout needs. The key is the ID the store already puts in its item URLs.
export type Listing = {
  key: string;
  title: string;
  price: number;
  inStock: boolean;
  seller: string;
  path: string;
};

// Each store describes itself once, and the same checkout runs on top of it.
export type Merchant = {
  name: string;
  listings: Listing[];
};

type ShipTo = { name: string; address: string };

const facilitator = new HTTPFacilitatorClient({
  url: process.env.X402_FACILITATOR_URL ?? "https://x402.org/facilitator",
});

const paymentServer = new x402ResourceServer(facilitator).register(PAYMENT.network, new ExactEvmScheme());

export function payTo(): string {
  const address = process.env.STORE_PAY_TO;
  if (!address) throw new Error("STORE_PAY_TO is not set");
  return address;
}

function checkoutUrl(listing: Listing): string {
  return `/api/checkout/${encodeURIComponent(listing.key)}`;
}

function listingAt(merchant: Merchant, path: string): Listing | undefined {
  const key = decodeURIComponent(path.split("/").filter(Boolean).pop() ?? "");
  return merchant.listings.find((listing) => listing.key === key);
}

function isShipTo(value: unknown): value is ShipTo {
  const v = value as ShipTo;
  return typeof v?.name === "string" && v.name.trim() !== "" && typeof v?.address === "string" && v.address.trim() !== "";
}

// This is the lowest and highest price among the listings in stock.
function priceRange(listings: Listing[]) {
  const prices = listings.filter((listing) => listing.inStock).map((listing) => listing.price);
  return { min: Math.min(...prices), max: Math.max(...prices) };
}

// POST /api/checkout/{key} answers 402 with the price and wallet, then 200 with the order once paid.
export function checkoutRoute(merchant: Merchant) {
  // This runs only after the payment is verified. The payment settles only if this returns a status below 400.
  async function placeOrder(req: NextRequest): Promise<NextResponse<unknown>> {
    const listing = listingAt(merchant, req.nextUrl.pathname)!;
    const body = await req.json().catch(() => null);
    if (!isShipTo(body?.shipTo)) {
      return NextResponse.json({ error: "A shipTo name and address are required." }, { status: 400 });
    }

    return NextResponse.json({
      orderId: `ord_${crypto.randomUUID()}`,
      status: "confirmed",
      item: { key: listing.key, title: listing.title },
      amount: listing.price,
      currency: PAYMENT.currency,
      store: merchant.name,
      seller: listing.seller,
      shipTo: body.shipTo,
    });
  }

  const paidCheckout = withX402(
    placeOrder,
    {
      "/api/checkout/[id]": {
        accepts: {
          scheme: "exact",
          network: PAYMENT.network,
          payTo: () => payTo(),
          price: (ctx) => formatUsd(listingAt(merchant, ctx.path)!.price),
          maxTimeoutSeconds: 120,
        },
        description: `${merchant.name} checkout`,
        mimeType: "application/json",
      },
    },
    paymentServer,
  );

  return async function POST(req: NextRequest) {
    const listing = listingAt(merchant, req.nextUrl.pathname);
    if (!listing) return NextResponse.json({ error: "Item not found." }, { status: 404 });
    if (!listing.inStock) return NextResponse.json({ error: "Item is out of stock." }, { status: 409 });
    return paidCheckout(req);
  };
}

// GET /api/catalog lists every listing with where to view it and where to buy it.
export function catalogRoute(merchant: Merchant) {
  return async function GET() {
    return Response.json({
      store: merchant.name,
      currency: PAYMENT.currency,
      items: merchant.listings.map((listing) => ({ ...listing, checkoutUrl: checkoutUrl(listing) })),
    });
  };
}

// GET /.well-known/store.json tells an agent who it is paying and where the endpoints are.
export function storeInfoRoute(merchant: Merchant) {
  return async function GET() {
    // The wallet comes from the environment, so this runs per request instead of at build time.
    await connection();
    return Response.json({
      name: merchant.name,
      sellers: [...new Set(merchant.listings.map((listing) => listing.seller))],
      payTo: payTo(),
      network: PAYMENT.network,
      currency: PAYMENT.currency,
      priceRange: priceRange(merchant.listings),
      endpoints: {
        catalog: "/api/catalog",
        checkout: "/api/checkout/{key}",
      },
    });
  };
}
