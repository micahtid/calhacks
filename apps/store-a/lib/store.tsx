import { LISTINGS, type Store } from "@calhacks/amazon";

export const store: Store = {
  title: "Amazon.com. Spend less. Smile more.",
  company: "Amazon.com, Inc.",
  items: LISTINGS,
  deliverTo: "Lincoln 68508",
  deliveryDate: "Wed, Oct 28",
  fastDelivery: "Tomorrow, Oct 24",
  home: {
    kicker: "Get Game Night Ready",
    headline: "Retro Classics from $2",
    cta: "Shop Now",
    tiles: [
      { title: "Game Boy Classics Under $10", tone: "red", ids: ["pokemon-red-gb", "zelda-links-awakening-gb", "tetris-gb", "kirbys-dream-land-gb"] },
      { title: "Top Rated on Super Nintendo", tone: "violet", ids: ["super-mario-world-snes", "donkey-kong-country-snes", "star-fox-snes", "pokemon-red-gb"] },
      { title: "Party Picks for Game Night", tone: "green", ids: ["mario-kart-64-n64", "goldeneye-007-n64", "super-mario-world-snes", "sonic-2-genesis"] },
      { title: "Renewed and Ready to Play", tone: "dark", ids: ["sonic-2-genesis", "tetris-gb", "donkey-kong-country-snes", "zelda-links-awakening-gb"] },
    ],
    dealLabels: ["Limited Time Deal", "Limited Time Deal", "Ends in 05:33:58", "Limited Time Deal"],
  },
  listing: {
    badge: <span className="badge-outline">Renewed</span>,
    deliveryNote: (
      <>
        . Order within <span className="green">3 hrs 36 mins</span>
      </>
    ),
    shipsFrom: "Amazon",
    returns: "FREE 90-Day Refund/Replacement",
    payment: "Secure Transaction",
    storeLabel: "Amazon Renewed",
  },
};
