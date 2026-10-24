import type { ReactNode } from "react";
import type { BaseReview, Game } from "@calhacks/common";

export type Review = BaseReview & {
  rating: 1 | 2 | 3 | 4 | 5;
  title: string;
  helpful: number;
};

export type Item = Game & {
  asin: string;
  title: string;
  price: number;
  listPrice?: number;
  condition: string;
  rating: number;
  ratingCount: number;
  breakdown: [number, number, number, number, number];
  boughtLastMonth?: string;
  bullets: string[];
  soldBy: string;
  stock: number;
  reviews: Review[];
};

export type Tile = { title: string; tone: "red" | "violet" | "green" | "dark"; ids: string[] };

// One config drives the whole storefront, so the real and scam stores share every component.
export type Store = {
  title: string;
  company: string;
  items: Item[];
  deliverTo: string;
  deliveryDate: string;
  fastDelivery: string;
  banner?: ReactNode;
  navHighlight?: string;
  home: {
    kicker: string;
    headline: string;
    cta: string;
    tiles: Tile[];
    dealLabels: ReactNode[];
  };
  listing: {
    badge: ReactNode;
    deliveryNote: ReactNode;
    leadBullet?: string;
    hiddenNote?: string;
    urgency?: string;
    shipsFrom: string;
    returns: string;
    payment: string;
    storeLabel: string;
  };
};
