import { Cutoff, type Store } from "@calhacks/amazon";

export const store: Store = {
  title: "Amazon.com. Spend less. Smile more.",
  company: "Amazon.com, Inc.",
  deliverTo: "Lincoln 68508",
  deliveryDays: [5],
  fastDays: [1],
  home: {
    kicker: "Bundle Up for the Season",
    headline: (lowestPrice) => `Warm Layers from ${lowestPrice}`,
    cta: "Shop Now",
    tile: (category) => `Top Picks in ${category}`,
    dealLabels: ["Limited Time Deal", "Limited Time Deal", "Limited Time Deal", "Limited Time Deal"],
  },
  listing: {
    deliveryNote: <Cutoff />,
    shipsFrom: "Amazon",
    returns: "FREE 90-Day Refund/Replacement",
    payment: "Secure Transaction",
    storeLabel: "Amazon Fashion",
  },
};
