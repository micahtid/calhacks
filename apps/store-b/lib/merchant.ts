import type { Merchant } from "@calhacks/common/x402";
import { ITEMS, SELLER, itemPath } from "./catalog";

// Checkout uses the eBay item number, the same ID that is in each item URL.
export const merchant: Merchant = {
  name: "eBay Inc.",
  listings: ITEMS.map((item) => ({ key: item.itemNumber, title: item.title, price: item.price, inStock: item.available > 0, seller: SELLER.name, path: itemPath(item) })),
};
