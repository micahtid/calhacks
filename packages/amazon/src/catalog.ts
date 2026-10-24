import type { Metadata } from "next";
import { findOrThrow } from "@calhacks/common";
import type { Merchant } from "@calhacks/common/x402";
import type { Item, Store } from "./types";

export function getItem(store: Store, id: string): Item | undefined {
  return store.items.find((item) => item.id === id);
}

export function byId(store: Store, id: string): Item {
  return findOrThrow(store.items, (item) => item.id === id, `item: ${id}`);
}

export function byIds(store: Store, ids: string[]): Item[] {
  return ids.map((id) => byId(store, id));
}

export function itemPath(item: Item): string {
  return `/dp/${item.id}`;
}

export function itemParams(store: Store) {
  return store.items.map((item) => ({ id: item.id }));
}

export function itemMetadata(store: Store, id: string): Metadata {
  const item = getItem(store, id);
  return { title: item ? `Amazon.com: ${item.title} : Video Games` : "Amazon.com" };
}

// The real and scam stores sell through the same x402 checkout. The company on the page is who gets paid.
export function merchantOf(store: Store): Merchant {
  return {
    name: store.company,
    listings: store.items.map((item) => ({ key: item.id, title: item.title, price: item.price, inStock: item.stock > 0, seller: item.soldBy, path: itemPath(item) })),
  };
}
