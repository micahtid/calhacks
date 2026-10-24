import type { Metadata } from "next";
import type { Item, Store } from "./types";

export function getItem(store: Store, id: string): Item | undefined {
  return store.items.find((item) => item.id === id);
}

export function byId(store: Store, id: string): Item {
  const item = getItem(store, id);
  if (!item) throw new Error(`Unknown item: ${id}`);
  return item;
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
