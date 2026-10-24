import { EXPLORER } from "./data";

// Everything the demo run shows is scripted here. Nothing is fetched, scraped, or paid for real.

export const DEMO_PROMPT = "Find me a working Pokémon Red cartridge for my Game Boy. Don't pay more than $10.";
export const DEMO_TITLE = "Pokémon Red Under $10";

export const THOUGHTS = [
  "You want Pokémon Red for the Game Boy.",
  "It must work, so I’ll look for tested copies.",
  "Your limit is $10.",
  "I’ll search online stores.",
];

export const INSTRUCTION = { item: "Pokémon Red (Game Boy)", limit: "$10.00" };

export type Reason = "Fake Store Website" | "Too Cheap to Be Real" | "Wrong Payment Address" | "Hidden Instructions" | "Fake Reviews" | "Unknown Seller";

export type Listing = { id: number; title: string; store: string; price: number; condition: string; reason?: Reason };

type Source = { store: string; count: number; scamRate: number; reasons: Reason[] };

export const SOURCES: Source[] = [
  { store: "by", count: 71, scamRate: 0.18, reasons: ["Unknown Seller", "Too Cheap to Be Real", "Fake Reviews"] },
  { store: "mzn", count: 46, scamRate: 0, reasons: [] },
  { store: "Mercari", count: 34, scamRate: 0.2, reasons: ["Fake Reviews", "Unknown Seller"] },
  { store: "Lukie Games", count: 22, scamRate: 0, reasons: [] },
  { store: "Craigslist", count: 18, scamRate: 0.35, reasons: ["Hidden Instructions", "Unknown Seller"] },
  { store: "DKOldies", count: 15, scamRate: 0, reasons: [] },
  { store: "mzn Official Outlet", count: 14, scamRate: 1, reasons: ["Fake Store Website", "Fake Reviews"] },
  { store: "Pixel Cart Retro", count: 12, scamRate: 0, reasons: [] },
  { store: "pixelcart-retro.co", count: 9, scamRate: 1, reasons: ["Wrong Payment Address", "Fake Store Website"] },
  { store: "gameboy-deals.shop", count: 7, scamRate: 1, reasons: ["Too Cheap to Be Real"] },
];

const TITLES = [
  "Pokémon Red Version for Game Boy",
  "Pokemon Red GB Cartridge, Authentic",
  "Pokémon Red (Game Boy, 1998) Cart Only",
  "Pokemon Red Version Nintendo Game Boy Tested",
  "Pokémon Red, Saves Work, Original Cartridge",
  "Pokemon Red Game Boy Original Authentic Cart",
  "Pokémon Red Version GB, New Save Battery",
  "Pokemon Red Version Gameboy Game",
];

const CONDITIONS = ["Good", "Like New", "Fair", "Good · Cart Only", "Complete in Box", "Good · Tested"];

// A seeded generator keeps the "scraped" list identical on every run.
function random(seed: number) {
  return () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// The three best verified listings, placed at fixed spots in the scrape.
export const PICKS: (Listing & { note: string })[] = [
  { id: -1, title: "Pokémon Red Version, Tested With New Save Battery", store: "mzn", price: 8.5, condition: "Good · Tested", note: "Tested, with a new save battery." },
  { id: -2, title: "Pokemon Red Version Nintendo Game Boy Tested", store: "Lukie Games", price: 8.99, condition: "Good · Tested", note: "Tested, with the original battery." },
  { id: -3, title: "Pokémon Red (Game Boy, 1998) Cart Only", store: "by", price: 7.75, condition: "Fair", note: "Cheapest, but the label is torn and saves aren’t tested." },
];

function buildListings(): Listing[] {
  const next = random(13);
  const pick = <T,>(items: T[]) => items[Math.floor(next() * items.length)];
  const pools = SOURCES.map((source) =>
    Array.from({ length: source.count }, () => {
      const scam = next() < source.scamRate;
      const reason = scam ? pick(source.reasons) : undefined;
      const price = reason === "Too Cheap to Be Real" ? 1.49 + next() * 1.8 : 5.25 + next() * 4.74;
      return { title: pick(TITLES), store: source.store, price: Math.round(price * 100) / 100, condition: pick(CONDITIONS), reason };
    }),
  );

  // Interleave the sources as if every store were crawled at once.
  const merged: Omit<Listing, "id">[] = [];
  while (pools.some((pool) => pool.length)) {
    const pool = pools.filter((p) => p.length);
    merged.push(pick(pool).shift()!);
  }
  merged.splice(37, 0, PICKS[2]);
  merged.splice(112, 0, PICKS[0]);
  merged.splice(186, 0, PICKS[1]);
  return merged.map((listing, id) => ({ ...listing, id }));
}

export const LISTINGS = buildListings();

export const REJECTED = LISTINGS.filter((listing) => listing.reason);



export const STORE_WALLET = "0x7a3f9c2e81b4d65f0a9e3c17b52d8f4e6a01c91e";

export const CHECKOUT = [
  { label: "Start Checkout at mzn", detail: "Asked mzn to sell this exact listing." },
  { label: "Get the Price and Payment Address", detail: "mzn asked for 8.50 USDC to its verified wallet." },
  { label: "Double-Check Before Paying", detail: "The store, price, wallet and your $10.00 limit all match." },
  { label: "Approve the Exact Amount", detail: "8.50 USDC from your Hunter wallet, nothing more." },
  { label: "Send the Payment", detail: "The USDC transfer was confirmed on Base Sepolia." },
  { label: "Order Confirmed", detail: "mzn confirmed order MZN-114-8273615." },
];

export const RECEIPT = {
  item: INSTRUCTION.item,
  note: PICKS[0].note,
  store: "mzn",
  amount: "8.50 USDC",
  network: "Base Sepolia",
  order: "MZN-114-8273615",
  paid: "Oct 23, 2026 · 4:42 PM",
  arrives: "Mon, Oct 27",
  txHash: "0x3b7e9d10c4a25f86e1d3b0a97c64e2f58d1a0b3c7e92f46d85a1c0e3b7f29d64",
};

export const EXPLORER_TX = `${EXPLORER}/tx/${RECEIPT.txHash}`;
