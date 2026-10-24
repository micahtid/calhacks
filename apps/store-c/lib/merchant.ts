import type { Merchant } from "@calhacks/common/x402";
import { ITEMS, itemPath } from "./catalog";

// Checkout uses the Depop slug, the same ID that is in each item URL. Every listing is a single item that is still for sale.
export const merchant: Merchant = {
  name: "Depop",
  listings: ITEMS.map((item) => ({ key: item.slug, title: item.title, price: item.price, inStock: true, seller: item.sellerHandle, path: itemPath(item) })),
};
