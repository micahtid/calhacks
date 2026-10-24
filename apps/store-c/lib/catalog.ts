import { findOrThrow, listingFor, type BaseReview, type Game } from "@calhacks/common";

export type Seller = {
  handle: string;
  initials: string;
  sold: number;
  active: string;
  rating: number;
  reviewCount: number;
  location: string;
};

export type Review = BaseReview & {
  rating: number;
};

export type Item = Game & {
  slug: string;
  title: string;
  price: number;
  originalPrice?: number;
  condition: "Brand New" | "Like New" | "Used - Excellent" | "Used - Good" | "Used - Fair";
  sellerHandle: string;
  description: string;
  likes: number;
  listed: string;
};

export const SELLERS: Seller[] = [
  { handle: "pixelcartretro", initials: "PC", sold: 1312, active: "Active today", rating: 5, reviewCount: 418, location: "Columbus, United States" },
  { handle: "cartridgecloset", initials: "CC", sold: 486, active: "Active this week", rating: 4.8, reviewCount: 151, location: "Portland, United States" },
  { handle: "savefilestudio", initials: "SF", sold: 207, active: "Active today", rating: 4.9, reviewCount: 73, location: "Austin, United States" },
];

export const REVIEWS: Review[] = [
  { author: "marcus.webb", date: "2 weeks ago", rating: 5, body: "Exactly as described and shipped the next day. The save battery holds." },
  { author: "hannahkim", date: "1 month ago", rating: 5, body: "Well packed and the cartridge was cleaned. Would buy again." },
  { author: "kevinlu_", date: "2 months ago", rating: 4, body: "Good copy and fair price. Label a little more worn than the photo." },
];

const listing = listingFor<Item>();

export const ITEMS: Item[] = [
  listing({ id: "pokemon-red-gb", slug: "pixelcartretro-pokemon-red-game-boy", title: "Pokémon Red Game Boy Cartridge", price: 8.0, originalPrice: 10.0, condition: "Used - Excellent", sellerHandle: "pixelcartretro", likes: 64, listed: "Listed 2 days ago", description: "Original Pokémon Red cartridge for the Game Boy. Save battery replaced, so saves hold after the console is off. Light label wear on one edge. Cartridge only." }),
  listing({ id: "zelda-links-awakening-gb", slug: "cartridgecloset-zelda-links-awakening", title: "Zelda Link's Awakening Game Boy", price: 7.5, condition: "Used - Good", sellerHandle: "cartridgecloset", likes: 38, listed: "Listed 5 days ago", description: "Black cartridge release of Link's Awakening. Tested and saves work. Contacts cleaned before shipping. Cartridge only." }),
  listing({ id: "tetris-gb", slug: "savefilestudio-tetris-game-boy", title: "Tetris Game Boy 1989", price: 2.5, condition: "Used - Fair", sellerHandle: "savefilestudio", likes: 12, listed: "Listed 1 week ago", description: "The classic. Label is scuffed but it plays perfectly. Cleaned and tested. Cartridge only." }),
  listing({ id: "super-mario-world-snes", slug: "pixelcartretro-super-mario-world-snes", title: "Super Mario World SNES", price: 6.5, originalPrice: 8.0, condition: "Like New", sellerHandle: "pixelcartretro", likes: 91, listed: "Listed 3 days ago", description: "Bright label and no shell yellowing. Battery save tested and working. Cartridge only." }),
  listing({ id: "donkey-kong-country-snes", slug: "cartridgecloset-donkey-kong-country-snes", title: "Donkey Kong Country SNES", price: 5.5, condition: "Used - Good", sellerHandle: "cartridgecloset", likes: 27, listed: "Listed 4 days ago", description: "Saves still work. A little sticker residue on the back, shown in the photo. Cleaned and tested." }),
  listing({ id: "mario-kart-64-n64", slug: "savefilestudio-mario-kart-64", title: "Mario Kart 64 N64 Cartridge", price: 9.0, originalPrice: 12.0, condition: "Used - Good", sellerHandle: "savefilestudio", likes: 120, listed: "Listed 1 day ago", description: "Cleaned and tested, four player mode works with no freezes. Small scuff on one corner of the shell." }),
  listing({ id: "goldeneye-007-n64", slug: "pixelcartretro-goldeneye-007-n64", title: "GoldenEye 007 N64", price: 4.75, condition: "Used - Fair", sellerHandle: "pixelcartretro", likes: 44, listed: "Listed 6 days ago", description: "Faded label but works perfectly, multiplayer included. Cartridge only." }),
  listing({ id: "sonic-2-genesis", slug: "cartridgecloset-sonic-2-genesis-cib", title: "Sonic 2 Sega Genesis Complete in Box", price: 3.5, condition: "Used - Excellent", sellerHandle: "cartridgecloset", likes: 52, listed: "Listed 2 days ago", description: "Complete in the original case with the manual. Case hinges intact. Cleaned and tested." }),
  listing({ id: "kirbys-dream-land-gb", slug: "savefilestudio-kirbys-dream-land", title: "Kirby's Dream Land Game Boy", price: 3.0, condition: "Used - Good", sellerHandle: "savefilestudio", likes: 19, listed: "Listed 1 week ago", description: "Tested and works. Clean label with minor shelf wear. Great first game. Cartridge only." }),
  listing({ id: "star-fox-snes", slug: "pixelcartretro-star-fox-snes", title: "Star Fox SNES Super FX", price: 2.0, condition: "Used - Fair", sellerHandle: "pixelcartretro", likes: 9, listed: "Listed 2 weeks ago", description: "Label is a little torn, shown in the photo. Cleaned and tested, plays fine. Cartridge only." }),
];

export const PLATFORMS = [
  { label: "Game Boy", id: "pokemon-red-gb" },
  { label: "SNES", id: "super-mario-world-snes" },
  { label: "Nintendo 64", id: "mario-kart-64-n64" },
  { label: "Sega Genesis", id: "sonic-2-genesis" },
  { label: "Puzzle", id: "tetris-gb" },
  { label: "Platformers", id: "kirbys-dream-land-gb" },
];

export function byId(id: string): Item {
  return findOrThrow(ITEMS, (item) => item.id === id, `item: ${id}`);
}

export function getItem(slug: string): Item | undefined {
  return ITEMS.find((item) => item.slug === slug);
}

export function sellerOf(item: Item): Seller {
  return findOrThrow(SELLERS, (seller) => seller.handle === item.sellerHandle, `seller: ${item.sellerHandle}`);
}

export function itemPath(item: Item): string {
  return `/products/${item.slug}`;
}
