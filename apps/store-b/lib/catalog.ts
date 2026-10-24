import { listingFor, type BaseReview, type Game } from "@calhacks/common";

export type Feedback = BaseReview & {
  authorScore: number;
  itemTitle: string;
};

export type Item = Game & {
  itemNumber: string;
  title: string;
  price: number;
  wasPrice?: number;
  condition: "Very Good" | "Good" | "Acceptable" | "Like New";
  sellerNotes: string;
  available: number;
  sold: number;
  watchers: number;
  inCarts?: number;
  mpn: string;
  description: string;
  updated: string;
};

export const SELLER = {
  name: "pixelcart_retro",
  feedbackScore: 1006,
  positive: "99.4%",
  itemsSold: "3.2K",
  joined: "Jun 2019",
  location: "Columbus, Ohio, United States",
  ratings: [
    { label: "Accurate Description", value: 4.9 },
    { label: "Reasonable Shipping Cost", value: 5.0 },
    { label: "Shipping Speed", value: 5.0 },
    { label: "Communication", value: 4.9 },
  ],
};

export const DELIVERY = "Estimated between Thu, Oct 29 and Mon, Nov 2 to 68508";

export const FEEDBACK: Feedback[] = [
  { author: "m***b", authorScore: 112, date: "Past month", body: "Save battery really was replaced. Saved a game, left it overnight, file was still there. Exactly as described.", itemTitle: "Pokemon Red Version (Nintendo Game Boy, 1998) Authentic Tested Cartridge" },
  { author: "d***z", authorScore: 48, date: "Past month", body: "Plays perfectly on my original Game Boy. Contacts were clean. Fast shipping, well packed.", itemTitle: "The Legend of Zelda: Link's Awakening (Game Boy, 1993) Tested Authentic" },
  { author: "a***n", authorScore: 1210, date: "Past 6 months", body: "Label colors are bright and the shell has no yellowing. Great seller, would buy again.", itemTitle: "Super Mario World (Super Nintendo SNES, 1991) Cartridge Only Tested" },
  { author: "k***u", authorScore: 5255, date: "Past 6 months", body: "Item as described. Found it a little cheaper elsewhere later, but the cartridge matched the listing exactly.", itemTitle: "Super Mario World (Super Nintendo SNES, 1991) Cartridge Only Tested" },
  { author: "j***p", authorScore: 2279, date: "Past 6 months", body: "Cleaned and tested as promised. Four player battle mode for hours with no freezes. Recommended seller.", itemTitle: "Mario Kart 64 (Nintendo 64, 1997) N64 Authentic Cartridge Tested" },
];

const listing = listingFor<Item>();

export const ITEMS: Item[] = [
  listing({
    id: "pokemon-red-gb",
    itemNumber: "206644004313",
    title: "Pokemon Red Version (Nintendo Game Boy, 1998) Authentic Tested Cartridge",
    price: 8.75,
    wasPrice: 9.99,
    condition: "Very Good",
    sellerNotes: "New save battery installed. Light label wear on one edge.",
    available: 4,
    sold: 31,
    watchers: 10,
    inCarts: 5,
    mpn: "DMG-APAE-USA",
    description: "Original Pokemon Red cartridge for the Nintendo Game Boy. The save battery was replaced, so new save files hold after the console is turned off. The label has light wear on one edge and the contacts are clean. Cartridge only, no box or manual. Tested on an original Game Boy and a Game Boy Color.",
    updated: "Oct 23, 2026 01:31:39 PDT",
  }),
  listing({
    id: "zelda-links-awakening-gb",
    itemNumber: "206644004427",
    title: "The Legend of Zelda: Link's Awakening (Game Boy, 1993) Tested Authentic",
    price: 7.49,
    condition: "Good",
    sellerNotes: "Cartridge only. Tested and works.",
    available: 7,
    sold: 22,
    watchers: 6,
    mpn: "DMG-ZLE-USA",
    description: "Original black cartridge release of Link's Awakening. Tested and works, saves hold. Cartridge only. The contacts were cleaned before listing.",
    updated: "Oct 21, 2026 18:04:12 PDT",
  }),
  listing({
    id: "tetris-gb",
    itemNumber: "206644004538",
    title: "Tetris (Nintendo Game Boy, 1989) Cartridge Only Tested Works",
    price: 2.49,
    condition: "Acceptable",
    sellerNotes: "Label is scuffed but it plays perfectly.",
    available: 12,
    sold: 64,
    watchers: 3,
    mpn: "DMG-TRA-USA",
    description: "Original 1989 Tetris cartridge. The label is scuffed, see photos, but the game plays perfectly. Cleaned and tested. Cartridge only.",
    updated: "Oct 19, 2026 09:22:51 PDT",
  }),
  listing({
    id: "super-mario-world-snes",
    itemNumber: "206644004649",
    title: "Super Mario World (Super Nintendo SNES, 1991) Cartridge Only Tested",
    price: 6.99,
    wasPrice: 7.99,
    condition: "Like New",
    sellerNotes: "Bright label, no shell yellowing.",
    available: 5,
    sold: 48,
    watchers: 14,
    inCarts: 3,
    mpn: "SNS-MW-USA",
    description: "Super Mario World for the Super Nintendo. Contacts are clean and the label is bright with no shell yellowing. Battery save tested and working. Cartridge only.",
    updated: "Oct 22, 2026 14:10:05 PDT",
  }),
  listing({
    id: "donkey-kong-country-snes",
    itemNumber: "206644004750",
    title: "Donkey Kong Country (SNES, 1994) Authentic Cartridge Saves Work",
    price: 5.49,
    condition: "Good",
    sellerNotes: "Saves work. Small sticker residue on the back.",
    available: 3,
    sold: 19,
    watchers: 8,
    mpn: "SNS-8X-USA",
    description: "Donkey Kong Country cartridge. Saves still work. There is a little sticker residue on the back of the cartridge. Cleaned and tested.",
    updated: "Oct 20, 2026 11:45:30 PDT",
  }),
  listing({
    id: "mario-kart-64-n64",
    itemNumber: "206644004861",
    title: "Mario Kart 64 (Nintendo 64, 1997) N64 Authentic Cartridge Tested",
    price: 9.25,
    wasPrice: 10.49,
    condition: "Good",
    sellerNotes: "Cleaned and tested. Small scuff on the shell corner.",
    available: 6,
    sold: 57,
    watchers: 21,
    inCarts: 7,
    mpn: "NUS-NKTE-USA",
    description: "Mario Kart 64 cartridge, cleaned and tested. Four player mode tested with no freezes. Small scuff on one corner of the shell, shown in photos. Cartridge only.",
    updated: "Oct 23, 2026 07:58:44 PDT",
  }),
  listing({
    id: "goldeneye-007-n64",
    itemNumber: "206644004972",
    title: "GoldenEye 007 (Nintendo 64, 1997) N64 Cartridge Faded Label Works",
    price: 4.99,
    condition: "Acceptable",
    sellerNotes: "Faded label, works perfectly.",
    available: 2,
    sold: 26,
    watchers: 9,
    mpn: "NUS-NGEE-USA",
    description: "GoldenEye 007 cartridge. The label is faded but the game works perfectly, multiplayer included. Cartridge only.",
    updated: "Oct 18, 2026 16:33:09 PDT",
  }),
  listing({
    id: "sonic-2-genesis",
    itemNumber: "206644005083",
    title: "Sonic the Hedgehog 2 (Sega Genesis, 1992) Complete in Box with Manual CIB",
    price: 3.49,
    condition: "Very Good",
    sellerNotes: "Complete in box with manual. Case hinges intact.",
    available: 8,
    sold: 40,
    watchers: 5,
    mpn: "1051",
    description: "Sonic the Hedgehog 2 for the Sega Genesis, complete in the original case with the manual. Case hinges are intact. Cleaned and tested.",
    updated: "Oct 17, 2026 20:12:47 PDT",
  }),
  listing({
    id: "kirbys-dream-land-gb",
    itemNumber: "206644005194",
    title: "Kirby's Dream Land (Nintendo Game Boy, 1992) Tested Authentic Cart",
    price: 2.99,
    condition: "Good",
    sellerNotes: "Tested and works. Minor shelf wear.",
    available: 9,
    sold: 17,
    watchers: 4,
    mpn: "DMG-KYE-USA",
    description: "Kirby's Dream Land cartridge, tested and works. Clean label with minor shelf wear. A great first game for a new Game Boy owner. Cartridge only.",
    updated: "Oct 22, 2026 10:05:18 PDT",
  }),
  listing({
    id: "star-fox-snes",
    itemNumber: "206644005205",
    title: "Star Fox (Super Nintendo SNES, 1993) Super FX Cartridge Torn Label",
    price: 1.99,
    condition: "Acceptable",
    sellerNotes: "Label is a little torn. Plays fine.",
    available: 1,
    sold: 12,
    watchers: 2,
    mpn: "SNS-FO-USA",
    description: "Star Fox cartridge with the Super FX chip. The label is a little torn, shown in photos. Cleaned and tested, plays fine. Cartridge only.",
    updated: "Oct 16, 2026 13:27:02 PDT",
  }),
];

export function byId(id: string): Item {
  const item = ITEMS.find((entry) => entry.id === id);
  if (!item) throw new Error(`Unknown item: ${id}`);
  return item;
}

export function getItem(itemNumber: string): Item | undefined {
  return ITEMS.find((item) => item.itemNumber === itemNumber);
}

export function itemPath(item: Item): string {
  return `/itm/${item.itemNumber}`;
}
